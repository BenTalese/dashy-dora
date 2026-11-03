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
#
# Designed to be re-runnable; partial output won't poison subsequent
# runs (PyInstaller's cache handles that). Mirrors `build-linux.sh`
# step-for-step so a build-log diff between platforms stays readable.

param(
    [switch]$SkipSpa,
    [switch]$SkipPyInstaller,
    [switch]$Clean
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
