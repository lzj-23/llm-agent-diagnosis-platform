$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Virtual environment not found. Run scripts\bootstrap.ps1 first."
}

Push-Location (Join-Path $projectRoot "backend")
try {
    & $pythonPath -m uvicorn diagnosis_agent.main:app --host 127.0.0.1 --port 8000 --reload
} finally {
    Pop-Location
}
