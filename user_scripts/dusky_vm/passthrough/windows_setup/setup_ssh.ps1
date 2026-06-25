<#
.SYNOPSIS
    Dusky Windows Guest SSH Auto-Setup Utility
    Author: Antigravity Pair Programmer
    Description: Installs, configures, and secures the OpenSSH Server on Windows 10/11 VMs.
    Requirements: Run as Administrator in PowerShell.
#>

# 1. Enforce Administrator Privileges
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "This script must be run as an Administrator. Please reopen PowerShell as Administrator."
    Exit 1
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   Dusky Windows SSH Auto-Setup Utility   " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 2. Check and Install OpenSSH Server Capability
Write-Host "`n[1/5] Checking OpenSSH Server installation status..." -ForegroundColor Yellow
$sshService = Get-WindowsCapability -Online -Name OpenSSH.Server*

if ($sshService.State -ne "Installed") {
    Write-Host "OpenSSH Server is not installed. Installing capability (requires internet)..." -ForegroundColor Cyan
    try {
        Add-WindowsCapability -Online -Name $sshService.Name -ErrorAction Stop
        Write-Host "[OK] OpenSSH Server installed successfully." -ForegroundColor Green
    } catch {
        Write-Error "Failed to install OpenSSH Server capability: $_"
        Exit 1
    }
} else {
    Write-Host "[OK] OpenSSH Server capability is already installed." -ForegroundColor Green
}

# 3. Configure and Start SSHD Service
Write-Host "`n[2/5] Configuring SSH service startup..." -ForegroundColor Yellow
try {
    # Set SSH service to Automatic
    Set-Service -Name sshd -StartupType Automatic -ErrorAction Stop
    # Start the service if not running
    if ((Get-Service -Name sshd).Status -ne "Running") {
        Start-Service sshd -ErrorAction Stop
    }
    Write-Host "[OK] SSH service (sshd) set to Automatic and running." -ForegroundColor Green
} catch {
    Write-Error "Failed to configure SSH service: $_"
    Exit 1
}

# 4. Enforce Firewall Rule
Write-Host "`n[3/5] Checking firewall rules for port 22..." -ForegroundColor Yellow
$ruleName = "OpenSSH-Server-In-TCP"
$rule = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue

if ($rule) {
    try {
        Enable-NetFirewallRule -Name $ruleName -ErrorAction Stop
        Write-Host "[OK] Enabled default OpenSSH inbound firewall rule." -ForegroundColor Green
    } catch {
        Write-Error "Failed to enable inbound firewall rule: $_"
    }
} else {
    Write-Host "Default rule not found. Creating a custom inbound firewall rule..." -ForegroundColor Cyan
    try {
        New-NetFirewallRule -Name $ruleName -DisplayName "OpenSSH SSH Server (Inbound)" -Description "Inbound rule for OpenSSH Server (TCP port 22)" -Enabled True -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -ErrorAction Stop
        Write-Host "[OK] Created and enabled custom inbound firewall rule for port 22." -ForegroundColor Green
    } catch {
        Write-Error "Failed to create firewall rule: $_"
    }
}

# 5. Optimize Configuration (Permit Empty Passwords & Set Default Shell)
Write-Host "`n[4/5] Tuning SSH configurations..." -ForegroundColor Yellow
$sshdConfigPath = "C:\ProgramData\ssh\sshd_config"

if (Test-Path $sshdConfigPath) {
    Write-Host "Configuring blank password allowance (PermitEmptyPasswords yes)..." -ForegroundColor Cyan
    $configContent = Get-Content $sshdConfigPath
    
    # Replace PermitEmptyPasswords configurations to allow blank/empty password access
    if ($configContent -match "^#?PermitEmptyPasswords\s+") {
        $configContent = $configContent -replace "^#?PermitEmptyPasswords\s+\w+", "PermitEmptyPasswords yes"
    } else {
        $configContent += "`nPermitEmptyPasswords yes"
    }
    
    # Save the updated configuration
    $configContent | Set-Content $sshdConfigPath -Force
    Write-Host "[OK] sshd_config successfully tuned for VM remote diagnostics." -ForegroundColor Green
} else {
    Write-Warning "sshd_config not found at $sshdConfigPath. Skipping configuration tuning."
}

Write-Host "Setting PowerShell as the default SSH shell..." -ForegroundColor Cyan
try {
    # Set Default Shell to PowerShell
    $sshKeyPath = "HKLM:\SOFTWARE\OpenSSH"
    if (-not (Test-Path $sshKeyPath)) {
        New-Item -Path "HKLM:\SOFTWARE" -Name "OpenSSH" -Force | Out-Null
    }
    New-ItemProperty -Path $sshKeyPath -Name "DefaultShell" -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force | Out-Null
    Write-Host "[OK] PowerShell set as the default SSH shell." -ForegroundColor Green
} catch {
    Write-Warning "Failed to set default SSH shell: $_"
}

# 6. Restart SSHD to Apply Settings
Write-Host "`n[5/5] Restarting SSH service to apply configurations..." -ForegroundColor Yellow
try {
    Restart-Service sshd -ErrorAction Stop
    Write-Host "[OK] SSH service restarted successfully." -ForegroundColor Green
} catch {
    Write-Error "Failed to restart SSH service: $_"
    Exit 1
}

# 7. Summary & Diagnostics
$ipAddresses = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" }).IPAddress
Write-Host "`n==========================================" -ForegroundColor Green
Write-Host "   SSH SETUP COMPLETED SUCCESSFULLY" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host "You can now connect to this VM from the host using:" -ForegroundColor Cyan
foreach ($ip in $ipAddresses) {
    Write-Host "  ssh $env:USERNAME@$ip" -ForegroundColor Yellow
}
Write-Host "==========================================" -ForegroundColor Green
