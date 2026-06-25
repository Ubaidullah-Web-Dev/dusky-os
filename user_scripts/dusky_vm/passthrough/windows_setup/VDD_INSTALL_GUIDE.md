# Manual Virtual Display Driver (VDD) Installation Guide

This guide describes how to manually install and configure the Virtual Display Driver (VDD) by `itsmikethetech` inside a Windows guest VM to enable virtual display output for Looking Glass.

---

## Why Manual Setup is Required
Windows requires all kernel-mode and user-mode drivers to be signed. Because the Virtual Display Driver is signed with a developer self-signed Authenticode certificate, Windows will block the installation or fail to load the driver (showing a signature verification error like **Code 52** in Device Manager) unless the developer's certificate is manually trusted by your local machine's certificate stores.

---

## Step-by-Step Installation

### Step 1: Download the Driver
1. Open a browser in your Windows VM or download it on the host and copy it to the VM via the shared VirtIO-FS drive (`Z:`).
2. Download the latest driver release package (usually the `.zip` containing driver files only, or the installer) from:
   👉 [https://github.com/itsmikethetech/Virtual-Display-Driver/releases](https://github.com/itsmikethetech/Virtual-Display-Driver/releases)
3. Extract the downloaded `.zip` file (e.g., to `C:\VirtualDisplayDriver`).

### Step 2: Establish Certificate Trust
Before Windows allows the driver to run, you must trust its signing certificate.
1. Open **PowerShell** as **Administrator**.
2. Run the following commands to add the driver's catalog certificate to both the `TrustedPublisher` and `Root` stores:

```powershell
# Update this path to the location of the extracted 'mttvdd.cat' file
$catPath = "C:\VirtualDisplayDriver\mttvdd.cat"

# Retrieve the signer certificate from the catalog file
$sig = Get-AuthenticodeSignature $catPath
if ($sig.SignerCertificate) {
    # Add certificate to Trusted Publisher store
    $store1 = New-Object System.Security.Cryptography.X509Certificates.X509Store("TrustedPublisher", "LocalMachine")
    $store1.Open("ReadWrite")
    $store1.Add($sig.SignerCertificate)
    $store1.Close()

    # Add certificate to Root Certification Authorities store
    $store2 = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "LocalMachine")
    $store2.Open("ReadWrite")
    $store2.Add($sig.SignerCertificate)
    $store2.Close()

    Write-Host "Driver certificate successfully trusted." -ForegroundColor Green
} else {
    Write-Error "Could not retrieve signer certificate from $catPath. Check the path and file integrity."
}
```

### Step 3: Install the Driver via pnputil
1. In the same Administrator PowerShell window, run `pnputil` to add and install the driver:
   ```powershell
   pnputil /add-driver "C:\VirtualDisplayDriver\MttVDD.inf" /install
   ```
2. Verify that the command output reports that the driver package was successfully added and installed.

---

## Configuration & Custom Resolutions

The driver reads its active display configurations from the registry. You can customize the resolutions and refresh rates (e.g., 1080p, 1440p, 4K at 60Hz, 120Hz, etc.):

1. Press `Win + R`, type `regedit`, and hit Enter.
2. Navigate to:
   `HKLM\Software\Microsoft\Windows NT\CurrentVersion\WUDF\Services\IddSampleDriver\Parameters`
3. Look for registry values defining the resolution lists:
   - For newer versions, edit the `option.txt` or XML config in the installation directory if instructed by the driver release notes.
   - Typically, modifying the resolution values allows you to select custom targets in the Windows **Display Settings** menu.

---

## Verifying Installation
1. Right-click the Start Menu and select **Device Manager**.
2. Expand **Display adapters**.
3. You should see **IddSampleDriver Device** listed without any warning icons.
4. Open Windows **Display Settings** (`Settings > System > Display`). You should see a secondary display active representing the virtual monitor. You can configure it as the main screen, extend your desktop, or adjust its resolution to match your host monitor.
