# Dusky STT v6 - Unified #1 Default (5.91% WER) + Realtime Typing

**Stack July 2026:** Python 3.14.6 only, Arch bleeding, systemd 261, CUDA 12/13.3.1, 3050 Ti 4GB, 12700H 64GB RAM, PipeWire, Wayland, uv, Rich 15, Parakeet Unified 5.91% WER, wtype, ffmpeg

### What's New in v6

- **[1] is now unified-en-0.6b** (5.91% WER) - best accuracy, was #3 before. English only, 160ms-2s streaming latency. Made default because you said EN only is fine and WER better.
- **Realtime typing as you speak** into focused neovim/notepad/text field via `wtype` (Wayland). Old push-to-talk still works with `--push`
- **Auto pacman+uv deps:** installer checks `pipewire`, `wl-clipboard`, `wtype`, `ffmpeg`, `libnotify`, `yad`, `uv` and auto `sudo pacman -S` if missing. Then `uv add` all python deps cached at `~/.cache/uv`

### Files (this is all you need)

```
dusky_installer.py - Rich installer, auto pacman+uv, unified #1 default
dusky_main.py - CPU-only main, realtime typing via wtype, D3-cold safe
dusky_worker.py - GPU worker, auto fallback unified->v2 if unified not in onnx-asr yet
dusky-trigger - Toggle, --realtime (default) vs --push, --file podcast
dusky-stt.service - systemd user service fixed
README.md - this file
```

### Install

```bash
cd ~/Downloads/dusky-v5  # your folder with 5 files
chmod +x dusky-trigger

uv python install 3.14.6
uv run --python 3.14.6 dusky_installer.py

# Installer will:
# - Check pacman deps and auto install missing: pipewire wl-clipboard wtype ffmpeg libnotify yad uv base-devel
# - Ask hardware: 1=CUDA12 pip STABLE (your driver 610.43.03), 2=CUDA13 system (needs pacman cuda 13.3.1), 3=AMD, 4=CPU
# - Ask model: [1] unified-en-0.6b DEFAULT 5.91% WER realtime, [2] v2 EN 6.05% WER, [3] v3 25 langs 6.34%
# - Quant: int8 recommended for 4GB VRAM
# - VAD yes, chunk 25s, realtime? yes
# - Output both clipboard+file
# - Creates venv at ~/contained_apps/uv/dusky_stt_v2/.venv
# - uv add all deps (cached shared)
# - Prefetches model via hf_transfer (auto download)
# - Copies files, installs trigger to ~/.local/bin/dusky-trigger, service to ~/.config/systemd/user/

# Enable service
systemctl --user daemon-reload
loginctl enable-linger $USER
systemctl --user enable --now dusky-stt.service
journalctl --user -u dusky-stt -f

# Bind hotkey to: dusky-trigger (or ~/.local/bin/dusky-trigger)
```

### Usage - Realtime is now default

**Realtime typing into focused window (neovim, notepad):**
```bash
# Focus neovim / text editor, then press hotkey
dusky-trigger  # shows "REALTIME typing - focus editor and speak"
# Now speak - as you speak, it types live into focused window via wtype
# "hello world this is realtime"
dusky-trigger  # stop

# Force push-to-talk (old behavior, paste at end)
dusky-trigger --push  # or toggle will use config default

# Force realtime
dusky-trigger --realtime
```

How realtime works:
- Main daemon CPU-only, captures mic via sounddevice, chunks every 1.2s (configurable)
- Submits chunk to GPU worker (spawned on demand)
- Worker transcribes 1.2s chunk with unified model (5.91% WER)
- Main diffs new text vs already typed, calls `wtype "new words "` to type into focused window
- No retyping, only suffix

**Podcast / long file (no OOM):**
```bash
dusky-trigger --file ~/Downloads/podcast.mp3
# Transcodes via ffmpeg to 16k mono first (460MB for 2h, not 5GB), VAD splits, incremental save to ~/Transcripts/DuskySTT/
```

**Status/logs:**
```bash
dusky-trigger --status
dusky-trigger --logs
dusky-trigger --restart
dusky-trigger --kill
```

### Why unified #1 is better WER

- v2 EN: 6.05% WER, TDT, offline only
- v3 MULTI 25 langs: 6.34% WER, TDT, auto-detect, multilingual
- unified EN: 5.91% WER, RNNT, unified offline+streaming, 160ms-2s latency, EN only

If EN only is fine (you said it is), unified is objectively best accuracy + enables realtime.

Note: `onnx-asr` as of July 2026 may not yet have unified int8 ONNX. Worker has auto fallback: tries unified, if fails tries v2, then v3. So install will still work even if unified not in hub yet, will use v2 with same realtime typing logic (just slightly worse WER).

### D3 cold / Battery

Main daemon never imports CUDA, <50MB. Worker spawned on demand, exits after 30s idle -> CUDA context destroyed -> GPU goes D3cold 0.5W.

Check:
```bash
cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status  # suspended
cat /sys/bus/pci/devices/0000:01:00.0/power_state  # D3cold
```

### Troubleshooting

- No wtype: `sudo pacman -S wtype` (Wayland) or `ydotool` fallback. Installer auto-installs.
- No typing: check focused window supports wtype, try `wtype "hello"` manually, check Wayland compositor allows virtual keyboard
- No audio: `pavucontrol`, `python -m sounddevice`
- CUDA fail: `nvidia-smi`, driver 610.43.03 OK for CUDA12 pip, for CUDA13 system need pacman cuda 13.3.1
- Service fail: `systemctl --user status dusky-stt -l`, `journalctl --user -u dusky-stt -n 100`

### Uninstall

```bash
systemctl --user disable --now dusky-stt.service
rm -rf ~/contained_apps/uv/dusky_stt_v2 ~/.config/systemd/user/dusky-stt.service $XDG_RUNTIME_DIR/dusky_stt ~/Transcripts/DuskySTT
rm ~/.local/bin/dusky-trigger
```

v6 - Unified #1 default, realtime typing, auto pacman+uv, Python 3.14.6 only.
