#!/usr/bin/env python3
# Worker v6 - unified #1 default, auto fallback to v2 if unified not in onnx-asr

import sys
import sysconfig
import os
import gc
import time
import traceback
import logging
from pathlib import Path

if sysconfig.get_config_var("Py_GIL_DISABLED") == 1:
    sys.exit(1)

logger = logging.getLogger("dusky_worker")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s [WORKER] %(message)s'))
logger.addHandler(ch)

import onnxruntime as rt
import numpy as np
import soundfile as sf

def detect_vram():
    try:
        import subprocess, shutil
        if shutil.which("nvidia-smi"):
            out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3)
            if out.returncode == 0:
                return int(out.stdout.strip().splitlines()[0].strip())
    except Exception:
        pass
    return None

class PatchedSession(rt.InferenceSession):
    def __init__(self, path_or_bytes, sess_options=None, providers=None, **kwargs):
        if sess_options is None:
            sess_options = rt.SessionOptions()
        available = set(rt.get_available_providers())
        vram = detect_vram()
        gpu_limit = int((vram * 0.8 * 1024 * 1024) if vram else 2.5 * 1024 * 1024 * 1024)
        gpu_limit = max(1 * 1024**3, min(gpu_limit, 6 * 1024**3))

        p_names = []
        p_opts = []
        if 'CUDAExecutionProvider' in available:
            p_names.append('CUDAExecutionProvider')
            p_opts.append({'device_id': 0, 'arena_extend_strategy': 'kSameAsRequested', 'gpu_mem_limit': gpu_limit, 'cudnn_conv_algo_search': 'HEURISTIC', 'do_copy_in_default_stream': True})
        elif 'MIGraphXExecutionProvider' in available:
            p_names.append('MIGraphXExecutionProvider')
            p_opts.append({'device_id': 0})
        elif 'ROCmExecutionProvider' in available:
            p_names.append('ROCmExecutionProvider')
            p_opts.append({'device_id': 0, 'arena_extend_strategy': 'kSameAsRequested', 'gpu_mem_limit': gpu_limit})
        p_names.append('CPUExecutionProvider')
        p_opts.append({})
        sess_options.graph_optimization_level = rt.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.log_severity_level = 3
        if any("CUDA" in p or "ROCM" in p or "MIGraphX" in p for p in p_names):
            sess_options.enable_mem_pattern = False
            sess_options.enable_cpu_mem_arena = False
        super().__init__(path_or_bytes, sess_options, providers=p_names, provider_options=p_opts, **kwargs)

rt.InferenceSession = PatchedSession

import onnx_asr

def transcribe_chunk(model, audio: np.ndarray, tmp_dir: Path) -> str:
    try:
        res = model.recognize(audio)
        return (res[0] if isinstance(res, list) else res).strip() if res else ""
    except Exception:
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=str(tmp_dir)) as tf:
                sf.write(tf.name, audio, 16000)
                res = model.recognize(tf.name)
                Path(tf.name).unlink(missing_ok=True)
                return (res[0] if isinstance(res, list) else res).strip() if res else ""
        except Exception as e:
            logger.error(f"chunk fail {e}")
            return ""

def worker_main(task_q, result_q, config: dict):
    model_name = config.get("model", "nemo-parakeet-unified-en-0.6b")
    quant = config.get("quantization", "int8")
    idle_timeout = config.get("idle_timeout", 30)

    runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "dusky_stt"
    runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    logger.info(f"Worker loading {model_name} quant={quant} (auto fallback to v2 if unified missing)")
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

    model = None
    # Try unified, fallback to v2 if not available in onnx-asr
    for try_model in [model_name, "nemo-parakeet-tdt-0.6b-v2", "nemo-parakeet-tdt-0.6b-v3"]:
        try:
            model = onnx_asr.load_model(try_model, quantization=quant)
            logger.info(f"Loaded {try_model}")
            break
        except Exception as e:
            logger.warning(f"Failed to load {try_model}: {e}, trying next")
            continue

    if model is None:
        result_q.put({"error": "model_load_failed"})
        return

    last = time.time()
    while True:
        try:
            try:
                task = task_q.get(timeout=1.0)
            except Exception:
                if time.time() - last > idle_timeout:
                    logger.info(f"Idle {idle_timeout}s exiting for D3 cold")
                    break
                continue
            last = time.time()
            if task.get("type") == "stop":
                break
            if task.get("type") == "audio":
                audio = task["audio"]
                idx = task.get("index", 0)
                start_sec = task.get("start_sec", 0.0)
                text = transcribe_chunk(model, audio, runtime_dir)
                result_q.put({"type": "audio", "index": idx, "start_sec": start_sec, "text": text})
        except Exception as e:
            logger.error(f"worker loop {e}\n{traceback.format_exc()}")

    try:
        del model
    except Exception:
        pass
    gc.collect()
    logger.info("Worker exit, GPU D3 cold")
