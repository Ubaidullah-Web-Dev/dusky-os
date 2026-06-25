# Dusky VM Guest Setup Guide

This guide details the sequence of scripts to run inside a fresh Windows VM to configure SSH, install Python 3, and set up the Virtual Display Driver (VDD) for Looking Glass.

---

## Script Sequence

All scripts are located on the shared `Z:` drive (mapped to `/mnt/zram1` on the host). They are named with numerical prefixes so you can see the correct order:

* **`00_run_all.ps1`**: The master runner script that runs Step 1 and Step 2 sequentially.
* **`01_setup_ssh.ps1`**: Configures SSH, requests public keys, sets VM password, and sets up PowerShell as the default SSH shell.
* **`02_bootstrap_vdd.ps1`**: Checks for Python 3, automatically downloads and installs Python 3.13 if missing, and launches `03_install_vdd.py`.
* **`03_install_vdd.py`**: Interactively locates and installs the Virtual Display Driver, registers the Authenticode certificate to trust the driver, and starts the Looking Glass service.

---

## How to Run Everything Sequentially (Recommended)

To run all setup scripts in a single, automated execution:

1. Open **PowerShell** as **Administrator** inside the VM.
2. Run the master wrapper script:
   ```powershell
   Set-ExecutionPolicy Bypass -Scope Process -Force
   & "Z:\00_run_all.ps1"
   ```

---

## How to Run Scripts Individually

If you prefer to run specific stages manually, open **PowerShell** as **Administrator** and run:

### For SSH Auto-Setup alone:
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
& "Z:\01_setup_ssh.ps1"
```

### For Python & VDD Installation alone:
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
& "Z:\02_bootstrap_vdd.ps1"
```
