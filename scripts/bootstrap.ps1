$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $projectRoot ".venv"
$backendPath = Join-Path $projectRoot "backend"

if (-not (Test-Path -LiteralPath $venvPath)) {
    python -m venv $venvPath
}

$pythonPath = Join-Path $venvPath "Scripts\python.exe"
& $pythonPath -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }
& $pythonPath -m pip install -e "$backendPath[dev]"
if ($LASTEXITCODE -ne 0) { throw "Failed to install project dependencies." }

Write-Host "Environment ready: $venvPath"
