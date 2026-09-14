$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Virtual environment not found. Run scripts\bootstrap.ps1 first."
}

Push-Location (Join-Path $projectRoot "backend")
try {
    & $pythonPath -m ruff check .
    if ($LASTEXITCODE -ne 0) { throw "Ruff checks failed." }
    & $pythonPath -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
} finally {
    Pop-Location
}
