```markdown
# Dusky STT v7.0 FIXED - Unified Default, Realtime Typing, & D3-cold Safe

**Stack July 2026:** Python 3.14.6 only, Arch bleeding, systemd 261, Pure pip CUDA 12.6 (STABLE), 3050 Ti 4GB, 12700H 64GB RAM, PipeWire, Wayland, uv, Parakeet Unified 5.91% WER, wtype, ffmpeg (soxr)

### What's New in v7.0 FIXED

- **Pure pip CUDA 12.6 Isolation:** Completely mitigates the `libcublas.so.12` corruption caused by mixed `cu12`/`cu13` system dependencies.
- **`hf_xet` Integration:** Replaces the deprecated `hf_transfer` with `HF_XET_HIGH_PERFORMANCE=1` for rapid model prefetching.
- **Strict D3-Cold Safety:** The main daemon is now 100% torch-free and uses an ONNX-only Silero VAD CPU inference. The GPU worker strictly limits VRAM headroom (`0.7` clamp for 4GB cards) and aggressively forces garbage collection and `empty_cache()` to guarantee 0.5W D3-cold suspension when idle.
- **Secure FIFO IPC:** Re-engineered the trigger pipe to use `O_RDWR | O_NONBLOCK` descriptors, enforcing `0600` permissions with TOCTOU symlink protection so the daemon writers never block.
- **PipeWire Audio Fix:** Implements C-level blocking reads via a dedicated audio thread, requesting stereo and downmixing to mono via numpy to bypass PipeWire front-left channel linking bugs.

### Files (this is all you need)

```text
dusky_installer.py - Rich installer, auto pacman+uv, pure pip CUDA 12.6 resolution
dusky_main.py      - CPU-only main, realtime typing via wtype, blocking audio thread
dusky_worker.py    - GPU worker, dynamic LD_LIBRARY_PATH discovery, D3-cold cleanup
dusky-trigger      - Toggle, secure FIFO trigger, systemd-enforced env tracking
dusky-stt.service  - systemd user service (Type=exec), memory clamps
README.md          - This file

```

### Install

Place all 6 files into a single directory (e.g., `~/Downloads/dusky-v7`), then run:

```bash
cd ~/Downloads/dusky-v7
chmod +x dusky-trigger

uv python install 3.14.6
uv run --python 3.14.6 dusky_installer.py

# Installer will:
# - Check pacman deps and auto install missing: pipewire wl-clipboard wtype ffmpeg libnotify yad uv base-devel
# - Ask hardware: 1=CUDA12 pip STABLE (RECOMMENDED for 4GB), 2=CUDA13 system, 3=AMD, 4=CPU
# - Ask model: [1] unified-en-0.6b DEFAULT 5.91% WER, [2] v2 EN 6.05% WER, [3] v3 25 langs 6.34%
# - Setup isolated venv at ~/contained_apps/uv/dusky_stt_v2/.venv via `uv pip` (no seed pollution)
# - Discover pip CUDA paths and generate `.env` for systemd LD_LIBRARY_PATH injection
# - Prefetch models via `hf_xet`
# - Copy files, install trigger to ~/.local/bin/dusky-trigger, and service to ~/.config/systemd/user/

# Enable service
systemctl --user daemon-reload
loginctl enable-linger $USER
systemctl --user enable --now dusky-stt.service
journalctl --user -u dusky-stt -f

# Bind hotkey to: ~/.local/bin/dusky-trigger

```

### Usage - Realtime Default

**Realtime typing into focused window (neovim, notepad):**

```bash
# Focus neovim / text editor, then press hotkey
dusky-trigger  # shows "REALTIME typing - focus editor and speak"
# Speak. It types live into the focused window via wtype.
# "hello world this is realtime"
dusky-trigger  # stop

# Force push-to-talk (paste at end)
dusky-trigger --push  

# Force realtime (if config defaulted to push)
dusky-trigger --realtime

```

How realtime works:

* Main daemon (CPU-only) captures mic via sounddevice on a dedicated thread, chunking every 1.2s.
* Submits chunk to GPU worker (spawned on demand).
* Worker transcribes 1.2s chunk with the unified model.
* Main diffs new text vs already typed, and executes `wtype "new words "` to type suffix-only into the focused window.

**Podcast / Long File (High Quality / No OOM):**

```bash
dusky-trigger --file ~/Downloads/podcast.mp3
# Transcodes via ffmpeg using soxr:precision=28 to 16k mono.
# VAD splits, incremental save to ~/Transcripts/DuskySTT/

```

**Status/logs:**

```bash
dusky-trigger --status
dusky-trigger --logs
dusky-trigger --restart
dusky-trigger --kill

```

### D3-Cold / Battery Verification

Main daemon never imports CUDA (<50MB RAM). Worker is spawned on demand and exits after 30s idle -> Memory collected -> CUDA context destroyed -> GPU enters `D3cold` at 0.5W.

Check state:

```bash
cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status  # suspended
cat /sys/bus/pci/devices/0000:01:00.0/power_state           # D3cold

```

### Troubleshooting

* **No wtype / Virtual Keyboard blocked:** `sudo pacman -S wtype` (Wayland). Ensure your Wayland compositor allows virtual keyboard protocols.
* **Audio failing (xrun/PipeWire):** Ensure `pipewire-pulse` is running. Check `pavucontrol`.
* **Worker fails to load ONNX / CUDA:** Run `dusky-trigger --logs`. Ensure you aren't mixing pacman `cuda` with pip `nvidia-*-cu12`. The v7.0 installer isolates this via the `.env` file it generates.
* **Service fails to start:** `systemctl --user status dusky-stt -l`. The service uses `Type=exec` to accurately report crash loops.

### Uninstall

```bash
systemctl --user disable --now dusky-stt.service
rm -rf ~/contained_apps/uv/dusky_stt_v2 ~/.config/systemd/user/dusky-stt.service $XDG_RUNTIME_DIR/dusky_stt ~/Transcripts/DuskySTT
rm ~/.local/bin/dusky-trigger

```

```

```
