#!/usr/bin/env python3
"""
Dusky STT Installer v8.1 BLEEDING EDGE FIX - July 17 2026
Arch bleeding, Python 3.14.6, systemd 261, driver 610.43.03, 4GB VRAM
Fixes v8.0:
- torch==2.13.0 torchaudio==2.13.0 DOES NOT EXIST on cu130/cu128 - removed pin
- Use known-good stable: torch==2.11.0 torchaudio==2.11.0 cu130 (Python 3.14 supported)
  fallback to unpinned torch torchaudio from same index
- Abort on true failure, no silent mixed env
- Pure pip isolation, robust lib discovery
"""
import sys
import sysconfig
import os
import subprocess
import shutil
import json
import time
from pathlib import Path
import platform

if sys.version_info < (3, 14, 6):
    print(f"ERROR: Need Python 3.14.6+, got {sys.version}", file=sys.stderr)
    sys.exit(1)
if sysconfig.get_config_var("Py_GIL_DISABLED") == 1:
    print("ERROR: free-threaded 3.14t build, need GIL: uv python install 3.14.6", file=sys.stderr)
    sys.exit(1)
try:
    if not sys._is_gil_enabled():
        print("ERROR: GIL disabled at runtime", file=sys.stderr)
        sys.exit(1)
except AttributeError:
    pass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich import box
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "rich", "-q"], check=False)
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich import box

console = Console()
APP_DIR = Path.home() / "contained_apps" / "uv" / "dusky_stt_v2"
BIN_DIR = Path.home() / ".local" / "bin"
SYSTEMD_DIR = Path.home() / ".config" / "systemd" / "user"
TRANSCRIPT_DIR = Path.home() / "Transcripts" / "DuskySTT"
for p in [APP_DIR, BIN_DIR, SYSTEMD_DIR, TRANSCRIPT_DIR]:
    p.mkdir(parents=True, exist_ok=True)
TRIGGER_PATH = BIN_DIR / "dusky-trigger"

def run(cmd, timeout=None, capture_output=True, env=None, cwd=None):
    try:
        res = subprocess.run(cmd, text=True, capture_output=capture_output, timeout=timeout, env=env, cwd=cwd)
        if not capture_output:
            res.stdout = res.stdout or ""
            res.stderr = res.stderr or ""
        return res
    except Exception as e:
        class R:
            returncode=1; stdout=""; stderr=str(e)
        return R()

def run_with_retry(cmd, max_retries=2, delay=3, **kwargs):
    last=None
    for attempt in range(1, max_retries+1):
        if attempt>1:
            console.print(f"[yellow]Retry {attempt}/{max_retries} in {delay}s...[/]")
            time.sleep(delay)
        last=run(cmd, **kwargs)
        if last.returncode==0:
            return last
        console.print(f"[red]Failed ({last.returncode}): {' '.join(cmd)}[/]")
        if last.stderr:
            console.print(f"[dim]{last.stderr[-800:]}[/]")
    return last

def check_pacman_deps():
    need={"pipewire":"pipewire","pipewire-pulse":"pipewire-pulse","wl-copy":"wl-clipboard",
          "wtype":"wtype","ffmpeg":"ffmpeg","notify-send":"libnotify","yad":"yad","uv":"uv"}
    missing=[]
    for bin_,pkg in need.items():
        if not shutil.which(bin_):
            missing.append(pkg)
    if not shutil.which("gcc"):
        missing.append("base-devel")
    if missing:
        pkgs=sorted(set(missing))
        console.print(f"[yellow]Missing: {', '.join(pkgs)}[/]")
        if Confirm.ask("Auto-install via sudo pacman -S --needed?", default=True):
            subprocess.run(["sudo","pacman","-S","--needed","--noconfirm"]+pkgs)

def detect_hardware():
    info={"nvidia":False,"amd":False,"cuda_pacman":None,"cudnn_pacman":None,
          "driver":None,"driver_major":0,"vram_mb":None,"cpu":platform.processor()}
    if shutil.which("nvidia-smi"):
        out=run(["nvidia-smi","--query-gpu=name,driver_version,memory.total","--format=csv,noheader,nounits"],timeout=5)
        if out.returncode==0 and out.stdout.strip():
            parts=[p.strip() for p in out.stdout.strip().splitlines()[0].split(",")]
            if len(parts)>=3:
                info["nvidia"]=True
                info["driver"]=parts[1]
                try: info["driver_major"]=int(parts[1].split(".")[0])
                except: pass
                info["vram_mb"]=parts[2]
    if Path("/opt/rocm").exists() or Path("/dev/kfd").exists():
        info["amd"]=True
    return info

def get_pip_cuda_lib_paths(venv_python: Path):
    code="""
import sys, sysconfig, pathlib
sp=pathlib.Path(sysconfig.get_paths()["purelib"])
nd=sp/"nvidia"
libs=[]
if nd.exists():
    for child in nd.iterdir():
        if not child.is_dir() or child.name.startswith("__"):
            continue
        for sub in ("lib","lib64"):
            d=child/sub
            if d.is_dir():
                try:
                    has=any(f.suffix==".so" or ".so." in f.name for f in d.iterdir())
                except:
                    has=True
                if has:
                    libs.append(str(d))
for mod in ("torch","torchaudio"):
    try:
        import importlib.util
        spec=importlib.util.find_spec(mod)
        if spec and spec.submodule_search_locations:
            d=pathlib.Path(spec.submodule_search_locations[0])/"lib"
            if d.is_dir():
                libs.append(str(d))
    except:
        pass
seen=set()
uniq=[]
for p in libs:
    if "numpy" in p: continue
    if p not in seen:
        seen.add(p); uniq.append(p)
print("\\n".join(uniq))
"""
    res=run([str(venv_python),"-c",code],timeout=10)
    if res.returncode==0 and res.stdout.strip():
        return [p.strip() for p in res.stdout.strip().splitlines() if p.strip()]
    return []

def install_torch_stack(venv_python: Path, cuda_variant: str):
    if cuda_variant=="nvidia-cuda13":
        index="https://download.pytorch.org/whl/cu130"
        console.print(f"[cyan]Installing PyTorch CUDA13 STABLE from {index}[/]")
        # Known-good matched versions for Python 3.14 - torch 2.11.0 is latest stable with cu130
        attempts=[
            ["uv","pip","install","--python",str(venv_python),"--index-url",index,
             "torch==2.11.0","torchaudio==2.11.0","torchvision==0.26.0"],
            ["uv","pip","install","--python",str(venv_python),"--index-url",index,
             "torch","torchaudio"],
        ]
    elif cuda_variant=="nvidia-cuda12":
        index="https://download.pytorch.org/whl/cu128"
        console.print(f"[cyan]Installing PyTorch CUDA12.8 LEGACY from {index}[/]")
        attempts=[
            ["uv","pip","install","--python",str(venv_python),"--index-url",index,
             "torch==2.11.0","torchaudio==2.11.0"],
            ["uv","pip","install","--python",str(venv_python),"--index-url",index,
             "torch","torchaudio"],
        ]
    elif cuda_variant=="amd":
        index="https://download.pytorch.org/whl/rocm6.3"
        attempts=[["uv","pip","install","--python",str(venv_python),"--index-url",index,"torch","torchaudio"]]
    else:
        index="https://download.pytorch.org/whl/cpu"
        attempts=[["uv","pip","install","--python",str(venv_python),"--index-url",index,"torch","torchaudio"]]

    for cmd in attempts:
        res=run_with_retry(cmd,cwd=str(APP_DIR),timeout=None,capture_output=False,max_retries=2)
        if res.returncode==0:
            console.print(f"[green]Torch OK via {index}[/]")
            return True
    console.print("[red]All torch attempts failed[/]")
    return False

def main():
    check_pacman_deps()
    hw=detect_hardware()
    tbl=Table(title="Detected Hardware",box=box.ROUNDED)
    tbl.add_column("Key",style="cyan"); tbl.add_column("Value")
    for k,v in hw.items(): tbl.add_row(k,str(v))
    console.print(tbl)

    if hw.get("driver_major",0)>=580:
        console.print("\n[bold green]Driver >=580 (610.43.03) - CUDA 13 native[/]")
        console.print(" [1] NVIDIA CUDA 13 pip STABLE [RECOMMENDED]")
        console.print(" [2] NVIDIA CUDA 12.8 pip LEGACY")
        console.print(" [3] AMD ROCm")
        console.print(" [4] CPU Only")
        choice=Prompt.ask("Hardware [1/2/3/4]",default="1")
        mapping={"1":"nvidia-cuda13","2":"nvidia-cuda12","3":"amd","4":"cpu"}
    else:
        console.print("\n [1] CUDA 12.8 STABLE\n [2] CUDA 13 EXPERIMENTAL\n [3] AMD\n [4] CPU")
        choice=Prompt.ask("Hardware [1/2/3/4]",default="1")
        mapping={"1":"nvidia-cuda12","2":"nvidia-cuda13","3":"amd","4":"cpu"}
    hardware=mapping.get(choice,"nvidia-cuda13")

    console.print("\nModel:\n [1] v2 EN 6.05% WER STABLE\n [2] unified-en 5.91% WER EXP\n [3] v3 25 langs")
    mchoice=Prompt.ask("Model [1/2/3]",default="1")
    model={"1":"nemo-parakeet-tdt-0.6b-v2","2":"nemo-parakeet-unified-en-0.6b","3":"nemo-parakeet-tdt-0.6b-v3"}.get(mchoice,"nemo-parakeet-tdt-0.6b-v2")

    console.print("\nQuant:\n [1] int8 4GB RECOMMENDED\n [2] fp16\n [3] fp32")
    qchoice=Prompt.ask("Quant [1/2/3]",default="1")
    quant={"1":"int8","2":"fp16","3":"fp32"}.get(qchoice,"int8")

    enable_vad=Confirm.ask("Enable VAD?",default=True)
    chunk_seconds=int(Prompt.ask("Max chunk seconds",default="25"))
    enable_realtime=Confirm.ask("Enable REALTIME wtype?",default=True)
    console.print("\nOutput: [1] clip [2] file [3] both [4] realtime+both")
    ochoice=Prompt.ask("Output [1/2/3/4]",default="4")
    out={"1":"clipboard","2":"file","3":"both","4":"realtime-both"}.get(ochoice,"realtime-both")

    config={"hardware":hardware,"model":model,"quantization":quant,"enable_vad":enable_vad,
            "chunk_seconds":chunk_seconds,"transcript_output":out,"realtime":enable_realtime,
            "realtime_chunk":1.2,"python":"3.14.6","idle_timeout":30,"use_ram":True,
            "installer_version":"8.1-fixed","driver":hw.get("driver"),"driver_major":hw.get("driver_major")}
    console.print(Panel(json.dumps(config,indent=2),title="Config",border_style="green"))
    if not Confirm.ask("Proceed?",default=True): sys.exit(0)

    pyproject=APP_DIR/"pyproject.toml"
    pyproject.write_text('[project]\nname="dusky-stt"\nversion="8.1"\nrequires-python=">=3.14"\ndependencies=[]\n[tool.uv]\nmanaged=true\n')
    console.print(f"\n[cyan]Creating venv at {APP_DIR} Python 3.14.6[/]")
    res=run(["uv","venv","--python","3.14.6","--clear"],cwd=str(APP_DIR),timeout=120)
    if res.returncode!=0:
        console.print(f"[red]uv venv failed: {res.stderr}[/]"); sys.exit(1)

    venv_python=APP_DIR/".venv"/"bin"/"python"
    if not venv_python.exists():
        venv_python=APP_DIR/".venv"/"bin"/"python3.14"
    if not venv_python.exists():
        console.print("[red]No venv python[/]"); sys.exit(1)

    ok=install_torch_stack(venv_python,hardware)
    if not ok:
        console.print("[red]CRITICAL: Torch install failed, aborting[/]"); sys.exit(1)

    base_deps=[
        "onnx-asr==0.12.0","soundfile","numpy==2.5.1","sounddevice","rich",
        "huggingface_hub>=0.28","hf_xet>=1.1","silero-vad==6.2.1",
        "onnxruntime==1.27.0" if hardware=="nvidia-cuda13" else "onnxruntime==1.26.0",
    ]
    console.print(f"[cyan]Step 2: Installing base: {' '.join(base_deps)}[/]")
    res=run_with_retry(["uv","pip","install","--python",str(venv_python)]+base_deps,
                       cwd=str(APP_DIR),timeout=None,capture_output=False,max_retries=2)
    if res.returncode!=0:
        console.print("[red]Base install failed[/]"); sys.exit(1)

    if hardware=="nvidia-cuda12":
        cuda_deps=["nvidia-cuda-runtime-cu12","nvidia-cublas-cu12","nvidia-cudnn-cu12",
                   "nvidia-cufft-cu12","nvidia-curand-cu12","nvidia-cusolver-cu12","nvidia-nvjitlink-cu12"]
        console.print(f"[cyan]Step 3: CUDA12 runtime libs[/]")
        run_with_retry(["uv","pip","install","--python",str(venv_python)]+cuda_deps,
                       cwd=str(APP_DIR),timeout=None,capture_output=False,max_retries=2)
        console.print("[cyan]Installing onnxruntime-gpu 1.26.0 (last CUDA12)[/]")
        run_with_retry(["uv","pip","install","--python",str(venv_python),"onnxruntime-gpu==1.26.0"],
                       cwd=str(APP_DIR),timeout=None,capture_output=False,max_retries=2)
    elif hardware=="nvidia-cuda13":
        console.print("[cyan]Step 3: onnxruntime-gpu 1.27.0 for CUDA13[/]")
        res=run_with_retry(["uv","pip","install","--python",str(venv_python),"onnxruntime-gpu==1.27.0"],
                           cwd=str(APP_DIR),timeout=None,capture_output=False,max_retries=2)
        if res.returncode!=0:
            console.print("[yellow]1.27.0 failed, fallback 1.26.0[/]")
            run_with_retry(["uv","pip","install","--python",str(venv_python),"onnxruntime-gpu==1.26.0"],
                           cwd=str(APP_DIR),timeout=None,capture_output=False,max_retries=1)

    console.print("[cyan]Discovering pip CUDA libs...[/]")
    pip_cuda_paths=get_pip_cuda_lib_paths(venv_python)
    ld_library_path=":".join(pip_cuda_paths)
    console.print(f"[green]Found {len(pip_cuda_paths)} libs: {pip_cuda_paths}[/]")

    env=os.environ.copy()
    if ld_library_path:
        env["LD_LIBRARY_PATH"]=ld_library_path+(":"+env.get("LD_LIBRARY_PATH","") if env.get("LD_LIBRARY_PATH") else "")
    env["HF_XET_HIGH_PERFORMANCE"]="1"
    env["PYTHONUNBUFFERED"]="1"
    res=run([str(venv_python),"-c","import onnx_asr,soundfile,numpy,sounddevice,huggingface_hub; print('ALL IMPORTS OK')"],timeout=15,env=env)
    console.print(res.stdout[-2000:] if res.stdout else "")
    if res.returncode==0:
        console.print("[green]Imports OK![/]")
    else:
        console.print(f"[red]Import check failed: {res.stderr[-1000:]}[/]")
        sys.exit(1)

    src_dir=Path(__file__).parent
    for fname in ["dusky_main.py","dusky_worker.py","dusky-trigger.py","README.md"]:
        cand=src_dir/fname
        if cand.exists():
            if fname=="dusky-trigger.py":
                dest=TRIGGER_PATH
                (APP_DIR/"dusky-trigger.py").write_text(cand.read_text())
            else:
                dest=APP_DIR/fname
            shutil.copy(cand,dest)
            if fname=="dusky-trigger.py":
                dest.chmod(0o755)
            console.print(f"[green]Copied {fname} -> {dest}[/]")

    (APP_DIR/".env").write_text(
        f"LD_LIBRARY_PATH={ld_library_path}\n"
        f"HF_XET_HIGH_PERFORMANCE=1\n"
        f"HF_HUB_CACHE={Path.home()}/.cache/huggingface\n"
        f"PYTHONUNBUFFERED=1\n"
        f"PYTORCH_NVML_BASED_CUDA_CHECK=1\n"
        f"CUDA_MODULE_LOADING=LAZY\n"
    )

    service_content=f"""[Unit]
Description=Dusky STT v8.1 FIXED - Parakeet Realtime D3-cold safe
After=pipewire.service pipewire-pulse.service graphical-session.target xdg-desktop-portal.service
Wants=pipewire.service
PartOf=graphical-session.target
StartLimitBurst=5
StartLimitIntervalSec=90

[Service]
Type=exec
ExecStart={APP_DIR}/.venv/bin/python {APP_DIR}/dusky_main.py --daemon
WorkingDirectory={APP_DIR}
Environment=HF_HUB_CACHE=%h/.cache/huggingface
Environment=HF_XET_HIGH_PERFORMANCE=1
Environment=PYTHONUNBUFFERED=1
Environment=PYTORCH_NVML_BASED_CUDA_CHECK=1
Environment=CUDA_MODULE_LOADING=LAZY
EnvironmentFile=-{APP_DIR}/.env
MemoryHigh=6G
MemoryMax=8G
MemorySwapMax=1G
OOMPolicy=stop
Restart=on-failure
RestartSec=2
RestartSteps=5
RestartMaxDelaySec=30
TimeoutStopSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=dusky-stt

[Install]
WantedBy=default.target
"""
    (APP_DIR/"dusky-stt.service").write_text(service_content)
    shutil.copy(APP_DIR/"dusky-stt.service", SYSTEMD_DIR/"dusky-stt.service")
    (APP_DIR/"install_config.json").write_text(json.dumps({**config,"ld_library_path":ld_library_path,"pip_cuda_paths":pip_cuda_paths},indent=2))
    console.print(Panel(f"[bold green]Setup Complete v8.1 FIXED![/]\nTrigger: {TRIGGER_PATH}\nLD libs: {len(pip_cuda_paths)}\nEnable: systemctl --user daemon-reload && systemctl --user enable --now dusky-stt.service",title="Done",border_style="green"))

if __name__=="__main__":
    main()
