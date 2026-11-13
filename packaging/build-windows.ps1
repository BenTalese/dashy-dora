# Build the Dashy Dora desktop bundle for Windows.
#
# Produces `dist\Dora\Dora.exe` plus its sibling tree of DLLs +
# bundled data. The app opens the SPA in the default browser.
#
# Prerequisites:
#   - Python 3.11 + a venv with `pip install -r requirements.txt`
#   - Node + npm
#
# Flags:
#   -SkipSpa            reuse an existing `web_app\dist\spa\` build
#   -SkipPyInstaller    run only the SPA build (sanity check)
#   -Clean              wipe dist\ + build\ before starting
#   -Installer          after pyinstaller, wrap dist\Dora\ into
#                       dist\Dora-vX.Y.Z-windows-x64-setup.exe with
#                       Inno Setup 6 (needs ISCC.exe on PATH or in its
#                       default install folder; Pillow for the icon)
#   -Version <X.Y.Z>    version stamped on the installer. Default:
#                       CURRENT_VERSION from version_info.py
#
# Designed to be re-runnable; partial output won't poison subsequent
# runs (PyInstaller's cache handles that). Mirrors `build-linux.sh`
# step-for-step so a build-log diff between platforms stays readable.

param(
    [switch]$SkipSpa,
    [switch]$SkipPyInstaller,
    [switch]$Clean,
    [switch]$Installer,
    [string]$Version
)

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

Write-Host "[build] Dashy Dora - Windows desktop bundle"
Write-Host "[build] cwd=$((Get-Location).Path)"

if ($Clean) {
    Write-Host "[build] Cleaning dist\ + build\"
    if (Test-Path dist) { Remove-Item -Recurse -Force dist }
    if (Test-Path build) { Remove-Item -Recurse -Force build }
}

# --- 1. SPA build ------------------------------------------------------
if (-not $SkipSpa) {
    if (-not (Test-Path 'web_app\node_modules')) {
        Write-Host "[build] web_app\node_modules missing - running npm install"
        Push-Location web_app
        try { npm install } finally { Pop-Location }
        if ($LASTEXITCODE -ne 0) { throw "[build] npm install failed" }
    }
    Write-Host "[build] Building SPA (quasar build)"
    Push-Location web_app
    try { npm run build } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "[build] npm run build failed" }
} else {
    Write-Host "[build] Skipping SPA build (-SkipSpa)"
}

if (-not (Test-Path 'web_app\dist\spa\index.html')) {
    throw "[build] ERROR: web_app\dist\spa\index.html missing. Did the SPA build succeed?"
}

# --- 2. PyInstaller bundle --------------------------------------------
if ($SkipPyInstaller) {
    Write-Host "[build] Skipping PyInstaller (-SkipPyInstaller)"
    exit 0
}

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    throw "[build] ERROR: pyinstaller not on PATH. Activate your venv and pip install pyinstaller."
}

# Fetch the Piper TTS binary so the bundle ships Dora's neural voice
# (R-018 / ADR-013). fetch_piper.py auto-detects the platform when run
# on Windows and picks `windows_amd64`. Idempotent; non-fatal - a
# failure only costs neural TTS; the desktop app falls back to the
# browser voice.
Write-Host "[build] Fetching Piper binary (packaging\fetch_piper.py)"
python packaging\fetch_piper.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[build] WARN: Piper fetch failed; bundle will use browser-voice fallback"
}

# Prefetch the default Piper voice so the bundle ships a neural voice
# ready out of the box. Idempotent + non-fatal: a network blip only
# costs the zero-friction first-run experience, not the build itself.
Write-Host "[build] Fetching default Piper voice (packaging\fetch_default_voice.py)"
python packaging\fetch_default_voice.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[build] WARN: default voice fetch failed; user will need to download one from Settings"
}

Write-Host "[build] Running pyinstaller dora.spec"
pyinstaller --noconfirm dora.spec
if ($LASTEXITCODE -ne 0) { throw "[build] pyinstaller failed" }

# --- 3. Quick smoke check --------------------------------------------
$binPath = 'dist\Dora\Dora.exe'
if (-not (Test-Path $binPath)) {
    throw "[build] ERROR: PyInstaller didn't produce $binPath"
}
$sizeMB = [math]::Round((Get-ChildItem -Recurse 'dist\Dora' | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host "[build] OK. Bundle at $binPath ($sizeMB MB)"
Write-Host "[build] Try it:  .\$binPath"

# --- 4. Optional installer (Inno Setup) ------------------------------
if (-not $Installer) {
    Write-Host "[build] (rerun with -Installer to wrap dist\Dora into a setup .exe)"
    exit 0
}

if (-not $Version) {
    $Version = (python -c "from dora_api.features.help.version_info import CURRENT_VERSION; print(CURRENT_VERSION)").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Version) { throw "[build] Couldn't read CURRENT_VERSION" }
}
$Version = $Version.TrimStart('v')

$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if ($iscc) {
    $isccPath = $iscc.Source
} else {
    $isccPath = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
    if (-not (Test-Path $isccPath)) {
        throw "[build] ERROR: Inno Setup 6 not found. Install it (winget install JRSoftware.InnoSetup) or put ISCC.exe on PATH."
    }
}

# Setup.exe wants a real .ico; make one from the PNG the app already uses.
New-Item -ItemType Directory -Force build | Out-Null
python -c "from PIL import Image; Image.open('packaging/icons/dora.png').save('build/dora.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
$isccArgs = @(
    "/DAppVersion=$Version",
    "/DSourceDir=$((Resolve-Path 'dist\Dora').Path)",
    "/DOutputDir=$((Resolve-Path 'dist').Path)",
    "/DOutputBaseFilename=Dora-v$Version-windows-x64-setup"
)
if ($LASTEXITCODE -eq 0 -and (Test-Path 'build\dora.ico')) {
    $isccArgs += "/DIconFile=$((Resolve-Path 'build\dora.ico').Path)"
} else {
    Write-Host "[build] WARN: couldn't make build\dora.ico (is Pillow installed?); installer gets Inno's default icon"
}

Write-Host "[build] Running Inno Setup ($isccPath)"
& $isccPath @isccArgs 'packaging\windows\dora.iss'
if ($LASTEXITCODE -ne 0) { throw "[build] Inno Setup failed" }

$setupPath = "dist\Dora-v$Version-windows-x64-setup.exe"
if (-not (Test-Path $setupPath)) { throw "[build] ERROR: Inno Setup didn't produce $setupPath" }
$setupMB = [math]::Round((Get-Item $setupPath).Length / 1MB, 1)
Write-Host "[build] OK. Installer at $setupPath ($setupMB MB)"
