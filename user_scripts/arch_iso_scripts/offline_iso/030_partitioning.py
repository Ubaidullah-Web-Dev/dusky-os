#!/usr/bin/env python3
"""
030_partitioning.py - DUSKY Final - Python 3.14.6 + Rich 15.0.0
Fixes:
 [1] --lock=yes single token
 [2] removeprefix not lstrip
 [3] NOCOW chattr +C alone
 [4] swapoff handles /mnt/swap/swapfile and /swap/swapfile
 [5] mkfs modern defaults crc32c
 [6] EFI hardened fmask=0177
"""
from __future__ import annotations
import os, sys, re, json, time, shlex, shutil, getpass, signal, argparse, subprocess, tempfile
from pathlib import Path
from typing import Literal
def _ensure_rich():
    import importlib.util
    try:
        if importlib.util.find_spec("rich") is not None: return
    except ModuleNotFoundError: pass
    if not hasattr(os,"geteuid") or os.geteuid()!=0:
        print("python-rich missing", file=sys.stderr); sys.exit(1)
    try:
        du = shutil.disk_usage("/run/archiso/cowspace")
        if du.free < 250*1024*1024:
            subprocess.run(["mount","-o","remount,size=2G","/run/archiso/cowspace"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass
    print(">> Installing python-rich...", file=sys.stderr)
    subprocess.run(["pacman","-Sy","--needed","--noconfirm","python-rich"], stdout=sys.stderr, stderr=sys.stderr)
_ensure_rich()
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
def make_console():
    term = os.environ.get("TERM","")
    if term in ("dumb","unknown"):
        return Console(color_system=None, force_terminal=False, no_color=True, legacy_windows=False)
    return Console(color_system="standard", legacy_windows=False, safe_box=True, highlight=False, markup=True)
console = make_console()
TARGET_CRYPT_NAME = "cryptroot"
EFI_GUID = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"
BIOS_GUID = "21686148-6449-6e6f-744e-656564454649"
LINUX_ROOT_GUID = "0fc63daf-8483-4772-8e79-3d69d8477de4"
LUKS_GUID = "ca7d7ccb-63ed-4c53-861c-1742536059cc"
DUSKY_EFI_LABEL = "DUSKY_EFI"; DUSKY_ROOT_LABEL = "DUSKY_ROOT"; DUSKY_BIOS_LABEL = "DUSKY_BIOS"
DUSKY_EFI_PARTNAME = "DUSKY_EFI"; DUSKY_ROOT_PARTNAME = "DUSKY_ROOT"
STATE_ENV = Path("/tmp/arch_install_state.env"); STATE_JSON = Path("/tmp/dusky_state.json")
VALID_PART_RE = re.compile(r"^[a-zA-Z0-9_./-]+$")
BTRFS_CSUM = "crc32c"
def run(*cmd, check=True, capture=True, input_text=None, timeout=300):
    argv = [os.fspath(c) for c in cmd]
    try:
        if isinstance(input_text, (bytes, bytearray)):
            return subprocess.run(argv, check=check, text=False, capture_output=capture, input=bytes(input_text), timeout=timeout)
        elif isinstance(input_text, str):
            return subprocess.run(argv, check=check, text=True, capture_output=capture, input=input_text, timeout=timeout)
        return subprocess.run(argv, check=check, text=True, capture_output=capture, timeout=timeout)
    except subprocess.CalledProcessError:
        if check: console.print(f"[red]Failed {shlex.join([str(x) for x in argv])}[/red]")
        raise
def get_partition_path(disk, num):
    disk = disk.rstrip("/")
    if re.search(rf"p{num}$", disk): return disk
    name = Path(disk).name
    if re.search(r"(?:nvme\d+n\d+|mmcblk\d+|loop\d+|nbd\d+|pmem\d+)$", name) or (disk and disk[-1].isdigit()):
        return f"{disk}p{num}"
    return f"{disk}{num}"
def detect_boot_mode() -> Literal["UEFI","BIOS"]:
    return "UEFI" if Path("/sys/firmware/efi/efivars").is_dir() else "BIOS"
def parse_credentials(path="./.arch_credentials"):
    out = {}; cred = Path(path)
    if not cred.exists(): return out
    try:
        script = f'set +u; source {shlex.quote(str(cred))} 2>/dev/null; printf "TARGET_USER=%s\\nENCRYPT_ROOT=%s\\nROOT_PASS=%s\\n" "$TARGET_USER" "$ENCRYPT_ROOT" "$ROOT_PASS"'
        r = subprocess.run(["bash","-c",script], text=True, capture_output=True, check=False, timeout=5)
        for line in r.stdout.splitlines():
            if "=" not in line: continue
            k,v = line.split("=",1); out[k]=v
    except: pass
    return out
def lsblk_all():
    r = run("lsblk","--json","--bytes","--paths","--tree","-o","NAME,PATH,KNAME,PKNAME,TYPE,FSTYPE,PARTTYPE,PARTLABEL,LABEL,SIZE,MODEL,MOUNTPOINTS", check=False, capture=True)
    try: return json.loads(r.stdout)
    except: return {"blockdevices":[]}
def list_disks():
    data = lsblk_all(); disks = []
    for dev in data.get("blockdevices",[]):
        if dev.get("type") != "disk": continue
        name = dev.get("name","")
        if name.startswith("/dev/loop") or name.startswith("/dev/zram") or name.startswith("/dev/ram") or name.startswith("/dev/sr"): continue
        try:
            if int(dev.get("size",0)) < 1*1024*1024*1024: continue
        except: continue
        disks.append(dev)
    return disks
def get_pkname(dev_path):
    try:
        r = run("lsblk","-ndlo","PKNAME",dev_path, check=False, capture=True)
        pk = r.stdout.strip().splitlines()[0].strip() if r.stdout.strip() else ""
        if pk: return f"/dev/{pk}"
    except: pass
    return ""
def get_immediate_backing(dev):
    try:
        real = str(Path(dev).resolve())
        if dev.startswith("/dev/mapper/") or real.startswith("/dev/dm-"):
            mapper = Path(dev).name if dev.startswith("/dev/mapper/") else None
            if not mapper:
                try:
                    p = Path(f"/sys/class/block/{Path(real).name}/dm/name")
                    if p.exists(): mapper = p.read_text().strip()
                except: mapper = None
            if mapper:
                try:
                    rr = run("cryptsetup","status",mapper, check=False, capture=True)
                    for line in rr.stdout.splitlines():
                        if line.strip().lower().startswith("device:"):
                            backing = line.split(":",1)[1].strip()
                            if backing and Path(backing).exists(): return str(Path(backing).resolve())
                except: pass
            try:
                dmk = Path(real).name
                sd = Path(f"/sys/class/block/{dmk}/slaves")
                if sd.is_dir():
                    for c in sd.iterdir(): return f"/dev/{c.name}"
            except: pass
        pk = get_pkname(dev)
        if pk: return pk
        try:
            k = Path(dev).name
            sl = Path(f"/sys/class/block/{k}/slaves")
            if sl.is_dir():
                for s in sl.iterdir(): return f"/dev/{s.name}"
        except: pass
    except: pass
    return None
def device_is_on_disk(node, disk, max_depth=32):
    try:
        cur = str(Path(node).resolve()); target = str(Path(disk).resolve()); depth=0
        while depth < max_depth:
            if cur == target: return True
            nxt = get_immediate_backing(cur)
            if not nxt:
                pk = get_pkname(cur)
                if not pk: return False
                cur = str(Path(pk).resolve())
            else:
                cur = str(Path(nxt).resolve())
            depth += 1
        return False
    except: return False
def findmnt_targets(prefix="/mnt"):
    try:
        r = run("findmnt","--json","--list","--submounts","--output","TARGET","--target",prefix, check=False, capture=True)
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            t = [fs.get("target","") for fs in data.get("filesystems",[]) if fs.get("target","").startswith(prefix)]
            return sorted(set(t), key=lambda p:(p.count("/"),len(p)), reverse=True)
    except: pass
    try:
        r = run("findmnt","-rn","-o","TARGET", check=False, capture=True)
        targets = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith(prefix)]
        return sorted(targets, key=lambda p:(p.count("/"),len(p)), reverse=True)
    except: return []
def wait_for_dev(path, timeout=10):
    p = Path(path)
    try:
        r = run("udevadm","wait","--timeout",str(timeout),"--settle",str(p), check=False, capture=True, timeout=timeout+2)
        if r.returncode == 0 and p.exists(): return True
    except: pass
    for _ in range(timeout*10):
        if p.exists(): return True
        time.sleep(0.1)
    return p.exists()
def prompt_luks_password(confirm=True):
    while True:
        try: pw = getpass.getpass("Enter LUKS passphrase: ")
        except EOFError: console.print("[red]No TTY[/red]"); sys.exit(1)
        if not pw: console.print("[red]Empty[/red]"); continue
        if not confirm: return bytearray(pw.encode())
        try: pw2 = getpass.getpass("Verify: ")
        except EOFError: sys.exit(1)
        if pw != pw2: console.print("[red]Mismatch[/red]"); continue
        return bytearray(pw.encode())
def is_mounted(dev):
    try:
        r = run("findmnt","-n","-o","TARGET","--source",dev, check=False, capture=True)
        return r.stdout.strip() or None
    except: return None
def detect_windows_esp(disk):
    data = lsblk_all()
    for dev in data.get("blockdevices",[]):
        dp = dev.get("path") or dev.get("name")
        if dp != disk and f"/dev/{dev.get('name')}" != disk and dev.get("name") != Path(disk).name:
            if dp != disk: continue
        for child in dev.get("children",[]) or []:
            fstype = (child.get("fstype") or "").lower()
            ptype = (child.get("parttype") or "").lower()
            path = child.get("path") or child.get("name")
            if not path: continue
            if ptype != EFI_GUID and fstype not in ("vfat","fat32"): continue
            mnt = is_mounted(path); tmp_obj = None; tmp_path = mnt
            try:
                if not mnt:
                    tmp_obj = tempfile.TemporaryDirectory(prefix="dusky_efi_check_")
                    tmp_path = tmp_obj.name
                    run("mount","--mkdir","-t","vfat","-o","ro,noexec,nosuid,nodev",path,tmp_path, check=False, capture=True)
                if Path(tmp_path,"EFI","Microsoft","Boot","bootmgfw.efi").exists() or Path(tmp_path,"EFI","Microsoft").is_dir():
                    if tmp_obj: run("umount",tmp_path, check=False, capture=True); tmp_obj.cleanup()
                    return True, path
                if tmp_obj: run("umount",tmp_path, check=False, capture=True)
            except:
                try:
                    if tmp_obj: run("umount",tmp_path, check=False, capture=True); tmp_obj.cleanup()
                except: pass
    return False, None
def safe_deactivate_swaps_for_device(target_dev):
    wanted = {"/mnt/swap/swapfile","/swap/swapfile"}
    candidates = set()
    try:
        r = run("swapon","--show=NAME","--raw","--noheadings", check=False, capture=True)
        candidates.update(l.strip() for l in r.stdout.splitlines() if l.strip())
    except: pass
    try:
        for line in Path("/proc/swaps").read_text().splitlines()[1:]:
            name = line.split()[0].strip()
            if name: candidates.add(name)
    except: pass
    for name in candidates:
        try:
            if name in wanted or (name.startswith("/mnt/") and name.endswith("swapfile")) or (Path(name).name == "swapfile" and (name.startswith("/mnt/") or name == "/swap/swapfile")):
                if target_dev:
                    check_src = name
                    if Path(name).is_file():
                        try:
                            r2 = run("findmnt","-rn","-T",name,"-o","SOURCE", check=False, capture=True)
                            check_src = r2.stdout.strip().split("[",1)[0] or name
                        except: pass
                    if device_is_on_disk(check_src, target_dev) or name in wanted:
                        run("swapoff",name, check=False, capture=True)
                else:
                    run("swapoff",name, check=False, capture=True)
        except: pass
    for p in wanted:
        run("swapoff",p, check=False, capture=True)
def teardown_device(target_dev):
    console.print(f"[yellow]>> Tearing down {target_dev}...[/yellow]")
    safe_deactivate_swaps_for_device(target_dev)
    for mp in findmnt_targets("/mnt"):
        try: run("umount","-R",mp, check=False, capture=True)
        except: pass
    try:
        r = run("findmnt","-rn","-o","TARGET,SOURCE", check=False, capture=True)
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2: continue
            tgt,src = parts[0],parts[1].split("[",1)[0]
            try:
                if Path(src).exists() and device_is_on_disk(src,target_dev):
                    run("umount","-R",tgt, check=False, capture=True)
            except: pass
    except: pass
    try:
        # Note: Do NOT combine -l (list) and -r (raw). Newer lsblk versions (util-linux >= 2.42) fail if both are combined.
        r = run("lsblk","-pnro","NAME,TYPE", check=False, capture=True)
        for line in r.stdout.splitlines():
            p = line.split()
            if len(p) < 2: continue
            name,typ = p[0],p[1]
            if typ == "crypt" and device_is_on_disk(name,target_dev):
                dm = Path(name).name
                if name.startswith("/dev/mapper/"): dm = name.split("/")[-1]
                else:
                    try: dm = Path(f"/sys/class/block/{Path(name).name}/dm/name").read_text().strip()
                    except: pass
                run("cryptsetup","close",dm, check=False, capture=True)
    except: pass
    run("udevadm","settle","--timeout=10", check=False, capture=True)
def ensure_mapper_free(target_dev=None):
    mp = Path(f"/dev/mapper/{TARGET_CRYPT_NAME}")
    if not mp.exists(): return
    if target_dev:
        try:
            r = run("cryptsetup","status",TARGET_CRYPT_NAME, check=False, capture=True)
            backing = ""
            for line in r.stdout.splitlines():
                if line.strip().lower().startswith("device:"):
                    backing = line.split(":",1)[1].strip(); break
            if backing and not device_is_on_disk(backing,target_dev): return
        except: pass
    run("cryptsetup","close",TARGET_CRYPT_NAME, check=False, capture=True)
    run("udevadm","settle","--timeout=5", check=False, capture=True)
def get_ram_kb():
    try: return (os.sysconf("SC_PHYS_PAGES")*os.sysconf("SC_PAGE_SIZE"))//1024
    except: return 4*1024*1024
def write_gpt_sfdisk(disk, boot_mode, encrypt, efi_size="1G"):
    root_type = LUKS_GUID if encrypt else LINUX_ROOT_GUID
    sfdisk_input = "label: gpt\n\n"
    if boot_mode == "UEFI":
        sfdisk_input += f'size={efi_size}, type={EFI_GUID}, name="{DUSKY_EFI_PARTNAME}"\n'
        sfdisk_input += f'size=+, type={root_type}, name="{DUSKY_ROOT_PARTNAME}"\n'
    else:
        sfdisk_input += f'size=2M, type={BIOS_GUID}, name="{DUSKY_BIOS_LABEL}"\n'
        sfdisk_input += f'size=+, type={root_type}, name="{DUSKY_ROOT_PARTNAME}"\n'
    console.print(f"[cyan]Writing GPT to {disk}[/cyan]")
    run("wipefs","--all","--force","--lock=yes",disk, check=False, capture=True)
    try:
        run("sfdisk","--force","--wipe","always","--wipe-partitions","always","--label","gpt","--lock=yes",disk, input_text=sfdisk_input, capture=True)
    except subprocess.CalledProcessError:
        run("sfdisk","--force","--wipe","always","--wipe-partitions","always","--label","gpt",disk, input_text=sfdisk_input, capture=True)
    run("blockdev","--rereadpt",disk, check=False, capture=True)
    try: run("udevadm","trigger","--settle","-w","--timeout=10",disk, check=False, capture=True)
    except: run("udevadm","settle","--timeout=10", check=False, capture=True)
    efi_part = get_partition_path(disk,1) if boot_mode=="UEFI" else None
    root_part = get_partition_path(disk,2)
    if not wait_for_dev(root_part,10): raise RuntimeError(f"{root_part} missing")
    if efi_part and not wait_for_dev(efi_part,10): raise RuntimeError(f"{efi_part} missing")
    return root_part, efi_part
def show_disks_table(disks):
    table = Table(title="Disks",box=box.ASCII,safe_box=True)
    table.add_column("#",justify="right",style="cyan"); table.add_column("Device",style="bold"); table.add_column("Size",justify="right"); table.add_column("Model",style="dim")
    for i,d in enumerate(disks,1):
        try: sz = f"{int(d.get('size',0))/1024**3:.1f}G"
        except: sz = str(d.get("size",""))
        table.add_row(str(i),d.get("path") or d.get("name"),sz,(d.get("model") or "")[:30])
    console.print(table)
def validate_part_input(raw):
    if not raw or not VALID_PART_RE.match(raw): raise ValueError("Invalid chars")
    name = raw.removeprefix("/dev/")
    p = Path("/dev") / name
    try: rp = p.resolve()
    except: rp = p
    try:
        if not rp.is_relative_to(Path("/dev")): raise ValueError("Must be under /dev")
    except AttributeError:
        if "/dev" not in str(rp): raise ValueError("Must be under /dev")
    if not rp.exists(): raise ValueError(f"{rp} no exist")
    return rp
def choose_disk(disks):
    show_disks_table(disks)
    while True:
        ans = Prompt.ask("Select disk number or /dev path",console=console,default="1")
        if ans.isdigit():
            idx = int(ans)-1
            if 0 <= idx < len(disks): return disks[idx].get("path") or disks[idx].get("name")
        try:
            p = validate_part_input(ans)
            if p.exists(): return str(p)
        except Exception as e:
            console.print(f"[red]{e}[/red]")
        else:
            console.print("[red]Invalid[/red]")
def main():
    parser = argparse.ArgumentParser(description="DUSKY 030")
    parser.add_argument("--auto",action="store_true"); parser.add_argument("--disk",type=str)
    parser.add_argument("--encrypt",action="store_true"); parser.add_argument("--no-encrypt",action="store_true")
    parser.add_argument("--efi-size",type=str,default="1G",choices=["1G","2G","4G"]); parser.add_argument("--allow-bios",action="store_true")
    args = parser.parse_args()
    if hasattr(os,"geteuid") and os.geteuid()!=0: console.print("[red]Need root[/red]"); sys.exit(1)
    if not args.auto and not sys.stdin.isatty(): console.print("[red]Need TTY or --auto[/red]"); sys.exit(1)
    boot_mode = detect_boot_mode()
    if boot_mode == "BIOS" and not args.allow_bios:
        console.print("[yellow]BIOS detected, use --allow-bios[/yellow]")
        if not args.auto and not Confirm.ask("Continue BIOS?",console=console,default=False): sys.exit(0)
    console.print(Panel(f"[bold cyan]DUSKY Partitioning[/bold cyan] {boot_mode}",box=box.ROUNDED))
    creds = parse_credentials(); preset = None
    if args.encrypt: preset = 1
    elif args.no_encrypt: preset = 0
    elif creds.get("ENCRYPT_ROOT") in ("1","0"):
        try: preset = int(creds["ENCRYPT_ROOT"])
        except: pass
    disks = list_disks()
    if not disks: console.print("[red]No disks[/red]"); sys.exit(1)
    target_dev = args.disk or (disks[0].get("path") if args.auto and len(disks)==1 else choose_disk(disks))
    target_dev = str(Path(target_dev).resolve())
    has_win,win_esp = detect_windows_esp(target_dev)
    if has_win: console.print(Panel(f"[yellow]Windows ESP {win_esp} detected[/yellow]",title="Dual-Boot",box=box.ROUNDED))
    do_encrypt = preset if preset is not None else (1 if Confirm.ask("Encrypt LUKS2?",console=console,default=False) else 0)
    wipe_entire = True; format_efi = True; part_root = ""; part_boot = ""
    if has_win and not args.auto:
        if Confirm.ask("Reuse partitions (safer)?",console=console,default=True): wipe_entire = False
    if wipe_entire and not has_win and not args.auto:
        if not Confirm.ask(f"[red]WIPE ENTIRE {target_dev}?[/red]",console=console,default=False): wipe_entire = False
    if not wipe_entire:
        r = run("lsblk","-l","-o","NAME,SIZE,TYPE,FSTYPE,PARTLABEL,LABEL",target_dev,check=False,capture=True); console.print(r.stdout)
        while True:
            try: raw = Prompt.ask("ROOT partition (e.g. vda2)",console=console); rp = validate_part_input(raw); part_root = str(rp); break
            except Exception as e: console.print(f"[red]{e}[/red]")
        if boot_mode == "UEFI":
            while True:
                try: raw = Prompt.ask("EFI partition (e.g. vda1)",console=console); ep = validate_part_input(raw); part_boot = str(ep); break
                except Exception as e: console.print(f"[red]{e}[/red]")
            if has_win and part_boot == win_esp: format_efi = Confirm.ask("Format EFI? NO keeps Windows",console=console,default=False)
            else: format_efi = Confirm.ask(f"Format EFI {part_boot} as {DUSKY_EFI_LABEL}?",console=console,default=True)
        is_luks = run("cryptsetup","isLuks",part_root,check=False,capture=True).returncode == 0
        fstype = run("lsblk","-ndlo","FSTYPE",part_root,check=False,capture=True).stdout.strip().lower()
        if is_luks or fstype == "btrfs":
            if Confirm.ask("Rescue: use existing?",console=console,default=False):
                ensure_mapper_free(target_dev)
                if is_luks:
                    if creds.get("ROOT_PASS"):
                        pw = bytearray(creds["ROOT_PASS"].encode())
                        run("cryptsetup","open","--allow-discards","--key-file","-",part_root,TARGET_CRYPT_NAME,input_text=pw,capture=True)
                        for i in range(len(pw)): pw[i]=0
                    else:
                        pw = prompt_luks_password(False)
                        run("cryptsetup","open","--allow-discards","--key-file","-",part_root,TARGET_CRYPT_NAME,input_text=pw,capture=False)
                        for i in range(len(pw)): pw[i]=0
                STATE_ENV.write_text(f'PROVISIONED_ROOT_PART="{part_root}"\nPROVISIONED_EFI_PART="{part_boot}"\nENCRYPT_ROOT="{1 if is_luks else 0}"\n'); STATE_ENV.chmod(0o600)
                STATE_JSON.write_text(json.dumps({"root_part":part_root,"efi_part":part_boot,"encrypt":bool(is_luks),"disk":target_dev,"boot_mode":boot_mode},indent=2)); STATE_JSON.chmod(0o600)
                console.print("[green]Rescue done[/green]"); return
    luks_ba = None
    if do_encrypt: luks_ba = bytearray(creds["ROOT_PASS"].encode()) if creds.get("ROOT_PASS") else prompt_luks_password()
    console.print(Panel(f"Action: {'Wipe '+target_dev if wipe_entire else 'Format '+part_root}\nLUKS={bool(do_encrypt)}",title="Confirm",box=box.ROUNDED))
    console.print("[magenta]5s abort Ctrl+C[/magenta]")
    try:
        if console.is_terminal:
            with Progress(SpinnerColumn(),TextColumn("{task.description}"),transient=True,console=console) as prog:
                t = prog.add_task("Waiting...",total=5)
                for _ in range(5): time.sleep(1); prog.advance(t,1)
        else: time.sleep(5)
    except KeyboardInterrupt: sys.exit(1)
    teardown_device(target_dev); ensure_mapper_free(target_dev)
    if wipe_entire:
        try: part_root,tmp = write_gpt_sfdisk(target_dev,boot_mode,bool(do_encrypt),efi_size=args.efi_size); part_boot = tmp or ""
        except Exception as e: console.print(f"[red]{e}[/red]"); sys.exit(1)
    if run("cryptsetup","isLuks",part_root,check=False,capture=True).returncode == 0:
        run("cryptsetup","--batch-mode","erase",part_root,check=False,capture=True)
    run("wipefs","--all","--force","--lock=yes",part_root,check=False,capture=True)
    btrfs_target = part_root
    if do_encrypt:
        assert luks_ba is not None
        mem_kb = get_ram_kb(); pbkdf = []
        if mem_kb < 3_000_000: pbkdf = ["--pbkdf-memory","256","--pbkdf-parallel","1"]
        elif mem_kb < 4_200_000: pbkdf = ["--pbkdf-memory","512"]
        try:
            fmt = ["cryptsetup","--batch-mode","--type","luks2","--pbkdf","argon2id","--label",DUSKY_ROOT_LABEL] + pbkdf + ["luksFormat","--key-file","-",part_root]
            r = run(*fmt,input_text=luks_ba,check=False,capture=True)
            if r.returncode == 3:
                fmt = ["cryptsetup","--batch-mode","--type","luks2","--pbkdf","argon2id","--label",DUSKY_ROOT_LABEL,"--pbkdf-memory","256","--pbkdf-parallel","1","luksFormat","--key-file","-",part_root]
                r = run(*fmt,input_text=luks_ba,check=False,capture=True)
            if r.returncode != 0: console.print(f"[red]luksFormat fail[/red]"); sys.exit(1)
            ro = run("cryptsetup","open","--type","luks2","--allow-discards","--key-file","-",part_root,TARGET_CRYPT_NAME,input_text=luks_ba,check=False,capture=True)
            if ro.returncode != 0: console.print("[red]open fail[/red]"); sys.exit(1)
        finally:
            for i in range(len(luks_ba)): luks_ba[i]=0
        btrfs_target = f"/dev/mapper/{TARGET_CRYPT_NAME}"
    if BTRFS_CSUM == "blake2":
        run("mkfs.btrfs","-f","--csum","blake2","-O","no-holes","-L",DUSKY_ROOT_LABEL,btrfs_target,capture=True)
    else:
        run("mkfs.btrfs","-f","-L",DUSKY_ROOT_LABEL,btrfs_target,capture=True)
    if boot_mode == "UEFI" and part_boot:
        if wipe_entire or format_efi:
            if has_win and part_boot == win_esp:
                console.print("[yellow]Preserving Windows ESP[/yellow]")
            else:
                run("wipefs","--all","--force","--lock=yes",part_boot,check=False,capture=True)
                run("mkfs.fat","-F","32","-n",DUSKY_EFI_LABEL,part_boot,capture=True)
        else:
            if not has_win:
                try: run("fatlabel",part_boot,DUSKY_EFI_LABEL,check=False,capture=True)
                except: pass
    env = f'PROVISIONED_ROOT_PART="{part_root}"\n'
    if part_boot: env += f'PROVISIONED_EFI_PART="{part_boot}"\n'
    env += f'ENCRYPT_ROOT="{do_encrypt}"\n'
    STATE_ENV.write_text(env); STATE_ENV.chmod(0o600)
    STATE_JSON.write_text(json.dumps({"root_part":part_root,"efi_part":part_boot,"encrypt":bool(do_encrypt),"disk":target_dev,"boot_mode":boot_mode},indent=2)); STATE_JSON.chmod(0o600)
    console.print(Panel(f"[green]Done Root={part_root} EFI={part_boot or 'N/A'}[/green]",box=box.ROUNDED))
if __name__ == "__main__":
    def _h(s,f):
        try: run("udevadm","settle","--timeout=2",check=False,capture=True)
        except: pass
        sys.exit(128+s)
    signal.signal(signal.SIGINT,_h); signal.signal(signal.SIGTERM,_h)
    try: main()
    except KeyboardInterrupt: sys.exit(130)
