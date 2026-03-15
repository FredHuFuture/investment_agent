<#
.SYNOPSIS
    Start the Investment Agent backend and frontend servers.
.DESCRIPTION
    Launches uvicorn (port 8000) and Vite dev server (port 3000) in parallel.
    Press Ctrl+C to stop both.
.PARAMETER Backend
    Start only the backend API server.
.PARAMETER Frontend
    Start only the frontend dev server.
.PARAMETER Seed
    Run seed.py to populate demo data, then exit.
.PARAMETER Test
    Run the test suite, then exit.
.EXAMPLE
    .\run.ps1              # Start both servers
    .\run.ps1 -Backend     # Start API only
    .\run.ps1 -Frontend    # Start frontend only
    .\run.ps1 -Seed        # Seed demo data
    .\run.ps1 -Test        # Run tests
#>
param(
    [switch]$Backend,
    [switch]$Frontend,
    [switch]$Seed,
    [switch]$Test
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

if ($Seed) {
    python "$ProjectRoot\seed.py"
    exit $LASTEXITCODE
}

if ($Test) {
    python -m pytest "$ProjectRoot\tests" -q
    exit $LASTEXITCODE
}

if ($Backend) {
    Write-Host "Starting backend on http://localhost:8000 ..." -ForegroundColor Cyan
    uvicorn api.app:app --port 8000 --reload
    exit $LASTEXITCODE
}

if ($Frontend) {
    Write-Host "Starting frontend on http://localhost:3000 ..." -ForegroundColor Cyan
    Set-Location "$ProjectRoot\frontend"
    npm run dev
    exit $LASTEXITCODE
}

# Default: start both in parallel
Write-Host ""
Write-Host "  Investment Agent" -ForegroundColor Green
Write-Host "  Backend  -> http://localhost:8000" -ForegroundColor Cyan
Write-Host "  Frontend -> http://localhost:3000" -ForegroundColor Cyan
Write-Host "  Press Ctrl+C to stop both." -ForegroundColor DarkGray
Write-Host ""

$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:ProjectRoot
    uvicorn api.app:app --port 8000 --reload 2>&1
}

$frontendJob = Start-Job -ScriptBlock {
    Set-Location "$using:ProjectRoot\frontend"
    npm run dev 2>&1
}

try {
    while ($true) {
        # Stream output from both jobs
        Receive-Job $backendJob -ErrorAction SilentlyContinue
        Receive-Job $frontendJob -ErrorAction SilentlyContinue

        # Check if either died
        if ($backendJob.State -eq "Failed") {
            Write-Host "Backend crashed!" -ForegroundColor Red
            Receive-Job $backendJob
            break
        }
        if ($frontendJob.State -eq "Failed") {
            Write-Host "Frontend crashed!" -ForegroundColor Red
            Receive-Job $frontendJob
            break
        }

        Start-Sleep -Milliseconds 500
    }
}
finally {
    Write-Host "`nShutting down..." -ForegroundColor Yellow
    Stop-Job $backendJob -ErrorAction SilentlyContinue
    Stop-Job $frontendJob -ErrorAction SilentlyContinue
    Remove-Job $backendJob -Force -ErrorAction SilentlyContinue
    Remove-Job $frontendJob -Force -ErrorAction SilentlyContinue
}
