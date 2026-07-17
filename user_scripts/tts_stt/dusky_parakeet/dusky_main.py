#!/usr/bin/env python3
# Dusky Main v6 - CPU-only, D3-cold safe, Realtime typing via wtype
# Python 3.14.6 only, unified #1 default, 64GB RAM optimized

import os
import sys
import sysconfig
import time
import signal
import threading
import subprocess
import shutil
import json
import logging
from pathlib import Path

if sys.version_info < (3, 14, 6):
    print(f"Need 3.14.6+, got {sys.version}", file=sys.stderr)
    sys.exit(1)
if sysconfig.get_config_var("Py_GIL_DISABLED") == 1:
    print("Need GIL build", file=sys.stderr)
    sys.exit(1)

logger = logging.getLogger("dusky_main")
logger.setLevel(logging.INFO)
try:
    from rich.logging import RichHandler
    logger.handlers.clear()
    logger.addHandler(RichHandler(rich_tracebacks=False, show_time=False))
except Exception:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    logger.addHandler(ch)

# No onnxruntime import here!

try:
    import numpy as np
    import soundfile as sf
    import sounddevice as sd
    HAS_SD = True
except ImportError:
    HAS_SD = False
    import numpy as np
    import soundfile as sf

try:
    from silero_vad import load_silero_vad, get_speech_timestamps
    HAS_SILERO = True
except ImportError:
    HAS_SILERO = False

def get_runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    if not Path(base).exists():
        base = "/tmp"
    p = Path(base) / "dusky_stt"
    p.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        p.chmod(0o700)
    except Exception:
        pass
    return p

RUNTIME_DIR = get_runtime_dir()
FIFO_PATH = RUNTIME_DIR / "fifo"
PID_FILE = RUNTIME_DIR / "pid"
READY_FILE = RUNTIME_DIR / "ready"
TRANSCRIPT_DIR = Path.home() / "Transcripts" / "DuskySTT"
TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = Path.home() / "contained_apps" / "uv" / "dusky_stt_v2" / "install_config.json"

def notify(t, m, critical=False):
    if not shutil.which("notify-send"):
        return
    cmd = ["notify-send", "-a", "Dusky STT", "-t", "4000"]
    if critical:
        cmd += ["-u", "critical"]
    cmd += [t, m[:400]]
    try:
        subprocess.run(cmd, check=False, timeout=2)
    except Exception:
        pass

def type_into_focused(text: str):
    """Type text into focused window via wtype (Wayland) or ydotool"""
    if not text:
        return
    # Prefer wtype for Wayland
    if shutil.which("wtype"):
        try:
            # wtype types directly, use -s delay for natural
            subprocess.run(["wtype", text], check=False, timeout=5)
            return
        except Exception as e:
            logger.warning(f"wtype failed {e}")
    # Fallback ydotool
    if shutil.which("ydotool"):
        try:
            subprocess.run(["ydotool", "type", text], check=False, timeout=5)
            return
        except Exception:
            pass
    logger.warning("No wtype/ydotool found, cannot realtime type")

class VADProcessor:
    def __init__(self, sr=16000):
        self.sr = sr
        self.model = None
        if HAS_SILERO:
            try:
                self.model = load_silero_vad()
            except Exception:
                self.model = None

    def is_speech(self, audio: np.ndarray) -> bool:
        if audio.size == 0:
            return False
        rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
        return rms > 0.015

    def get_segments(self, audio: np.ndarray, max_sec=25) -> list[tuple[int,int]]:
        sr = self.sr
        max_samples = max_sec * sr
        if self.model is None:
            overlap = int(0.5 * sr)
            step = max_samples - overlap
            segs = []
            for start in range(0, len(audio), step):
                end = min(start + max_samples, len(audio))
                segs.append((start, end))
                if end == len(audio):
                    break
            return segs
        try:
            import torch
            wav = torch.from_numpy(audio.astype(np.float32))
            ts = get_speech_timestamps(wav, self.model, threshold=0.5, min_speech_duration_ms=250, min_silence_duration_ms=800, window_size_samples=512)
            if not ts:
                return []
            merged = []
            cur_s = None
            cur_e = None
            pad = int(0.2 * sr)
            for t in ts:
                s, e = int(t['start']), int(t['end'])
                if cur_s is None:
                    cur_s, cur_e = s, e
                elif (e - cur_s) <= max_samples:
                    cur_e = e
                else:
                    merged.append((max(0, cur_s - pad), min(len(audio), cur_e + pad)))
                    cur_s, cur_e = s, e
            if cur_s is not None:
                merged.append((max(0, cur_s - pad), min(len(audio), cur_e + pad)))
            return merged if merged else [(0, len(audio))]
        except Exception:
            overlap = int(0.5 * sr)
            step = max_samples - overlap
            segs = []
            for start in range(0, len(audio), step):
                end = min(start + max_samples, len(audio))
                segs.append((start, end))
                if end == len(audio):
                    break
            return segs

class WorkerManager:
    def __init__(self, config: dict):
        self.config = config
        self.task_q = None
        self.result_q = None
        self.proc = None
        self.lock = threading.Lock()

    def ensure(self):
        with self.lock:
            if self.proc and self.proc.is_alive():
                return
            if self.proc:
                try:
                    self.proc.terminate()
                    self.proc.join(timeout=2)
                except Exception:
                    pass
            import multiprocessing
            ctx = multiprocessing.get_context("spawn")
            self.task_q = ctx.Queue()
            self.result_q = ctx.Queue()
            from dusky_worker import worker_main
            self.proc = ctx.Process(target=worker_main, args=(self.task_q, self.result_q, self.config), daemon=False)
            self.proc.start()
            logger.info(f"GPU worker spawned PID {self.proc.pid}")

    def submit(self, audio: np.ndarray, idx: int, start_sec: float):
        self.ensure()
        self.task_q.put({"type": "audio", "audio": audio.astype(np.float32), "index": idx, "start_sec": start_sec})

    def get_all(self) -> list[dict]:
        res = []
        if not self.result_q:
            return res
        try:
            while True:
                res.append(self.result_q.get_nowait())
        except Exception:
            pass
        return res

    def stop(self):
        with self.lock:
            if self.task_q:
                try:
                    self.task_q.put({"type": "stop"})
                except Exception:
                    pass
            if self.proc:
                try:
                    self.proc.join(timeout=5)
                    if self.proc.is_alive():
                        self.proc.terminate()
                        self.proc.join(timeout=2)
                except Exception:
                    pass
            self.proc = None
            self.task_q = None
            self.result_q = None

class DuskyDaemon:
    def __init__(self, config: dict):
        self.config = config
        self.chunk_seconds = config.get("chunk_seconds", 25)
        self.realtime = config.get("realtime", True)
        self.realtime_chunk = config.get("realtime_chunk", 1.2)
        self.transcript_output = config.get("transcript_output", "both")
        self.idle_timeout = config.get("idle_timeout", 30)
        self.model_name = config.get("model", "nemo-parakeet-unified-en-0.6b")

        self.running = True
        self.is_recording = False
        self.is_realtime = False
        self.audio_q = None
        self.acc_chunks: list = []
        self.typed_text = ""  # for realtime diff
        self.worker = WorkerManager(config)
        self.vad = VADProcessor()
        logger.info(f"Main v6 CPU-only model={self.model_name} realtime={self.realtime} chunk={self.chunk_seconds}s")

    def start_recording(self, realtime: bool = False):
        if self.is_recording:
            return
        self.is_recording = True
        self.is_realtime = realtime
        self.acc_chunks = []
        self.typed_text = ""
        import queue
        try:
            self.audio_q = queue.SimpleQueue()
        except Exception:
            self.audio_q = queue.Queue()

        threading.Thread(target=self._record_loop, daemon=True).start()
        threading.Thread(target=self._transcribe_loop, daemon=True).start()
        mode = "REALTIME typing" if realtime else "push-to-talk"
        logger.info(f"Recording started {mode}")
        notify("Listening...", f"{mode} - speak now" if realtime else "Speak now")

    def _record_loop(self):
        sr = 16000
        def cb(indata, frames, time_info, status):
            if status:
                logger.warning(f"Audio status {status}")
            try:
                data = indata.copy().flatten().astype(np.float32)
                try:
                    self.audio_q.put_nowait(data)
                except AttributeError:
                    self.audio_q.put(data)
            except Exception as e:
                logger.error(f"cb error {e}")

        try:
            with sd.InputStream(samplerate=sr, channels=1, callback=cb, blocksize=1024, dtype='float32'):
                while self.is_recording and self.running:
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"sounddevice failed {e}")
            self.is_recording = False

    def _transcribe_loop(self):
        sr = 16000
        buffer = np.array([], dtype=np.float32)
        chunk_idx = 0
        last_typed_idx = -1

        # For realtime, smaller chunk
        chunk_sec = self.realtime_chunk if self.is_realtime else self.chunk_seconds

        while (self.is_recording or not self.audio_q.empty()) and self.running:
            try:
                import queue
                try:
                    data = self.audio_q.get(timeout=0.2)
                except queue.Empty:
                    data = None

                if data is not None:
                    buffer = np.concatenate([buffer, data]) if buffer.size else data

                    # Auto-chunk on silence or max size
                    if len(buffer) >= chunk_sec * sr:
                        # For realtime, we send even if speech
                        to_send = buffer.copy()
                        buffer = np.array([], dtype=np.float32) if self.is_realtime else buffer[int(chunk_sec*sr*0.5):]  # keep overlap for offline
                        if self.is_realtime:
                            # In realtime, send whole buffer as chunk
                            self.worker.submit(to_send, chunk_idx, chunk_idx*chunk_sec)
                        else:
                            self.worker.submit(to_send, chunk_idx, chunk_idx*chunk_sec)
                        chunk_idx += 1

                # Collect results
                for res in self.worker.get_all():
                    text = res.get("text", "")
                    if not text:
                        continue
                    idx = res.get("index", 0)
                    # For realtime typing
                    if self.is_realtime:
                        # Only type new suffix to avoid retyping
                        # Simplest: type full text if new, but diff
                        if idx > last_typed_idx:
                            # Type new chunk with space
                            to_type = text.strip() + " "
                            if to_type not in self.typed_text:
                                type_into_focused(to_type)
                                self.typed_text += to_type
                            last_typed_idx = idx
                    # Accumulate for final
                    self.acc_chunks.append({"index": idx, "text": text, "start_sec": res.get("start_sec", 0)})

            except Exception as e:
                logger.error(f"transcribe loop {e}")
                time.sleep(0.1)

        # Flush
        if buffer.size > 0:
            self.worker.submit(buffer, chunk_idx, chunk_idx*chunk_sec)

    def stop_recording(self) -> str:
        if not self.is_recording:
            return ""
        self.is_recording = False
        time.sleep(0.5)
        # Collect remaining
        for res in self.worker.get_all():
            if res.get("text"):
                self.acc_chunks.append({"index": res.get("index", 0), "text": res["text"], "start_sec": res.get("start_sec", 0)})

        # Sort by index
        self.acc_chunks = sorted(self.acc_chunks, key=lambda x: x["index"])
        full_text = " ".join([c["text"] for c in self.acc_chunks if c["text"]]).strip()

        if not full_text:
            notify("No speech", "No speech detected")
            return ""

        # If realtime, we already typed, but also save and clipboard
        ts = int(time.time())
        out_path = TRANSCRIPT_DIR / f"{'realtime' if self.is_realtime else 'live'}_{ts}.txt"
        out_path.write_text(full_text, encoding="utf-8")
        try:
            out_path.chmod(0o600)
        except Exception:
            pass

        if self.transcript_output in ("clipboard", "both") and not self.is_realtime:
            # In realtime we already typed, don't double paste via clipboard to avoid duplicate
            if shutil.which("wl-copy"):
                try:
                    subprocess.run(["wl-copy"], input=full_text.encode(), check=True, timeout=5)
                except Exception:
                    pass
            notify("Transcription Complete", full_text[:200])

        logger.info(f"Saved {out_path} {len(full_text)} chars")
        return full_text

    def transcribe_file(self, filepath: str):
        path = Path(filepath).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(str(path))
        logger.info(f"File transcribe {path}")
        notify("Transcribing", f"{path.name}")

        tmp_wav = RUNTIME_DIR / f"transcode_{int(time.time())}_{path.stem}.wav"
        try:
            cmd = ["ffmpeg", "-y", "-i", str(path), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(tmp_wav)]
            subprocess.run(cmd, check=True, capture_output=True, timeout=600)

            data, sr = sf.read(str(tmp_wav), dtype='float32', always_2d=False)
            assert sr == 16000
            if data.ndim > 1:
                data = data.mean(axis=1)

            segments = self.vad.get_segments(data, max_sec=self.chunk_seconds)
            if not segments:
                notify("No speech", f"No speech in {path.name}")
                return ""

            incremental = TRANSCRIPT_DIR / f"{path.stem}_incremental.txt"
            incremental.write_text("", encoding="utf-8")
            full_parts = []

            self.worker.ensure()

            for idx, (s, e) in enumerate(segments):
                chunk = data[s:e].astype(np.float32)
                self.worker.submit(chunk, idx, s/16000)
                # Wait for result
                waited = 0
                result_text = ""
                while waited < 60:
                    for res in self.worker.get_all():
                        if res.get("index") == idx:
                            result_text = res.get("text", "")
                            break
                    if result_text:
                        break
                    time.sleep(0.1)
                    waited += 0.1
                if result_text:
                    full_parts.append(result_text)
                    with open(incremental, "a", encoding="utf-8") as f:
                        f.write(result_text + "\n")

            full_text = " ".join(full_parts).strip()
            if full_text:
                final_path = TRANSCRIPT_DIR / f"{path.stem}_{int(time.time())}.txt"
                final_path.write_text(full_text, encoding="utf-8")
                if shutil.which("wl-copy"):
                    try:
                        subprocess.run(["wl-copy"], input=full_text.encode(), check=True, timeout=5)
                    except Exception:
                        pass
                notify("Complete", f"{path.name}: {len(full_text)} chars")
            return full_text
        finally:
            try:
                tmp_wav.unlink(missing_ok=True)
            except Exception:
                pass

    def fifo_loop(self):
        if FIFO_PATH.exists() and not FIFO_PATH.is_fifo():
            FIFO_PATH.unlink(missing_ok=True)
        if not FIFO_PATH.exists():
            os.mkfifo(FIFO_PATH, mode=0o600)
        try:
            FIFO_PATH.chmod(0o600)
        except Exception:
            pass

        fd = os.open(FIFO_PATH, os.O_RDWR | os.O_NONBLOCK)
        import select
        poll = select.poll()
        poll.register(fd, select.POLLIN)
        logger.info(f"FIFO at {FIFO_PATH}")

        while self.running:
            if not poll.poll(500):
                continue
            try:
                data = b""
                while True:
                    try:
                        chunk = os.read(fd, 4096)
                        if not chunk:
                            break
                        data += chunk
                    except BlockingIOError:
                        break
                if not data:
                    continue
                for line in data.decode('utf-8', errors='ignore').splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    logger.info(f"FIFO {line}")
                    if line == "START":
                        self.start_recording(realtime=False)
                    elif line == "START_REALTIME":
                        self.start_recording(realtime=True)
                    elif line == "STOP":
                        self.stop_recording()
                    elif line.startswith("FILE:"):
                        fpath = line[5:].strip()
                        import threading
                        threading.Thread(target=self.transcribe_file, args=(fpath,), daemon=True).start()
            except Exception as e:
                logger.error(f"FIFO {e}")
                time.sleep(0.5)
        try:
            os.close(fd)
        except Exception:
            pass

    def start(self):
        def handle_sig(s, f):
            self.running = False
        signal.signal(signal.SIGTERM, handle_sig)
        signal.signal(signal.SIGINT, handle_sig)

        PID_FILE.write_text(str(os.getpid()))
        try:
            PID_FILE.chmod(0o600)
        except Exception:
            pass
        READY_FILE.touch()
        try:
            READY_FILE.chmod(0o600)
        except Exception:
            pass
        logger.info(f"Daemon v6 CPU-only ready PID {os.getpid()} realtime default, model={self.config.get('model')}")

        threading.Thread(target=self.fifo_loop, daemon=True).start()

        try:
            while self.running:
                time.sleep(1)
        finally:
            self.worker.stop()
            for p in (FIFO_PATH, PID_FILE, READY_FILE):
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass

def load_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {"model": "nemo-parakeet-unified-en-0.6b", "quantization": "int8", "chunk_seconds": 25, "enable_vad": True, "transcript_output": "both", "realtime": True, "realtime_chunk": 1.2, "idle_timeout": 30}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--file", type=str)
    args = parser.parse_args()

    cfg = load_config()
    daemon = DuskyDaemon(cfg)

    if args.file:
        print(daemon.transcribe_file(args.file))
        return
    if args.daemon:
        daemon.start()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
