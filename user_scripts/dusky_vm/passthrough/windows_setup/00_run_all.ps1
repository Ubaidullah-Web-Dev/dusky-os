<#
.SYNOPSIS
    Master VM Guest Setup Runner
    Description: Runs the guest VM setup scripts sequentially (SSH configuration first, then VDD installation).
    Requirements: Run as Administrator in PowerShell.
#>

# 1. Enforce Administrator Privileges
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Re-launching master runner as Administrator..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    Exit
}

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "          Dusky VM Master Guest Setup             " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# Define the shared drive directory
$scriptDir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
if (-not (Test-Path $scriptDir)) {
    $scriptDir = "Z:\"
}

# 2. Run SSH Auto-Setup (01_setup_ssh.ps1)
$sshScript = Join-Path $scriptDir "01_setup_ssh.ps1"
if (Test-Path $sshScript) {
    Write-Host "`n>>> [STEP 1/2] RUNNING SSH CONFIGURATION..." -ForegroundColor Cyan
    & $sshScript
} else {
    Write-Warning "Could not find SSH script at $sshScript. Skipping STEP 1."
}

# 3. Run VDD Bootstrapper & Installer (02_bootstrap_vdd.ps1)
$vddScript = Join-Path $scriptDir "02_bootstrap_vdd.ps1"
if (Test-Path $vddScript) {
    Write-Host "`n>>> [STEP 2/2] RUNNING VIRTUAL DISPLAY DRIVER SETUP..." -ForegroundColor Cyan
    & $vddScript
} else {
    Write-Warning "Could not find VDD bootstrapper at $vddScript. Skipping STEP 2."
}

Write-Host "`n==================================================" -ForegroundColor Green
Write-Host "      ALL VM GUEST SETUPS COMPLETED SUCCESSFULLY! " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Read-Host "Press Enter to close..."
