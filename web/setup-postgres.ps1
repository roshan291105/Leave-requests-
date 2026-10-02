$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw 'Could not install website dependencies.' }
& .\.venv\Scripts\python.exe postgres_setup.py
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL setup did not complete. See the message above.' }
