$ErrorActionPreference = "Stop"

python -m pip install -r "$PSScriptRoot\requirements-build.txt"
if ($LASTEXITCODE -ne 0) {
    throw "Installing build dependencies failed."
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name DealershipManager `
    --collect-all PIL `
    --distpath "$PSScriptRoot\dist" `
    --workpath "$PSScriptRoot\build" `
    --specpath "$PSScriptRoot" `
    "$PSScriptRoot\app.py"
if ($LASTEXITCODE -ne 0) {
    throw "Building the dealership executable failed."
}

Write-Host "Executable created: $PSScriptRoot\dist\DealershipManager.exe"
