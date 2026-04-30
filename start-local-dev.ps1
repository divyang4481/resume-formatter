# Local Development with Docker - Same containers as production
# Runs Backend API, Worker, and Frontend in Docker, connected to AWS services

param(
    [switch]$Build = $false,
    [switch]$Down = $false,
    [switch]$Logs = $false,
    [switch]$FrontendOnly = $false
)

$ErrorActionPreference = "Stop"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Resume Formatter - Docker Local Dev" -ForegroundColor Cyan
Write-Host "  Backend: Docker (Port 8000)" -ForegroundColor White
Write-Host "  Worker: Docker (Background)" -ForegroundColor White
Write-Host "  Frontend: Docker (Port 4200)" -ForegroundColor White
Write-Host "  Database: AWS RDS" -ForegroundColor Yellow
Write-Host "  LLM: AWS Bedrock Llama 3" -ForegroundColor Yellow
Write-Host "  Storage: AWS S3" -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Cyan

# Stop containers if requested
if ($Down) {
    Write-Host "--- Stopping Docker Containers ---" -ForegroundColor Yellow
    docker-compose -f docker-compose.local.yml down
    Write-Host "Containers stopped!" -ForegroundColor Green
    exit 0
}

# Show logs if requested
if ($Logs) {
    Write-Host "--- Showing Container Logs ---" -ForegroundColor Yellow
    docker-compose -f docker-compose.local.yml logs -f
    exit 0
}

# Check if .env.local exists
if (-not (Test-Path "backend\.env.local")) {
    Write-Host "Error: backend\.env.local not found!" -ForegroundColor Red
    Write-Host "File already exists with AWS configuration." -ForegroundColor Yellow
    exit 1
}

# Verify AWS credentials
Write-Host "--- Verifying AWS Access ---" -ForegroundColor Yellow
try {
    $Identity = aws sts get-caller-identity --output json | ConvertFrom-Json
    Write-Host "AWS Account: $($Identity.Account)" -ForegroundColor Green
    Write-Host "AWS User: $($Identity.Arn)" -ForegroundColor Green
} catch {
    Write-Host "Warning: AWS credentials not configured!" -ForegroundColor Red
    Write-Host "Run: aws configure" -ForegroundColor Yellow
}
Write-Host ""

# Build images if requested
if ($Build) {
    Write-Host "--- Building Docker Images ---" -ForegroundColor Yellow
    Write-Host "This may take 5-10 minutes..." -ForegroundColor Gray
    docker-compose -f docker-compose.local.yml build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "Build complete!" -ForegroundColor Green
    Write-Host ""
}

# Start containers
Write-Host "--- Starting Docker Containers ---" -ForegroundColor Yellow

if ($FrontendOnly) {
    Write-Host "Starting frontend only (backend must be running)..." -ForegroundColor White
    docker-compose -f docker-compose.local.yml up -d frontend
} else {
    Write-Host "Starting all services..." -ForegroundColor White
    docker-compose -f docker-compose.local.yml up -d
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to start containers!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Start-Sleep -Seconds 3

# Check container status
Write-Host "--- Container Status ---" -ForegroundColor Yellow
docker-compose -f docker-compose.local.yml ps

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All Services Running!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "URLs:" -ForegroundColor Yellow
Write-Host "  Frontend:  http://localhost:4200" -ForegroundColor White
Write-Host "  Backend:   http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs:  http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Connected to:" -ForegroundColor Yellow
Write-Host "  Database:  AWS RDS (ap-south-1)" -ForegroundColor White
Write-Host "  LLM:       AWS Bedrock Llama 3" -ForegroundColor White
Write-Host "  Storage:   AWS S3" -ForegroundColor White
Write-Host ""
Write-Host "Commands:" -ForegroundColor Yellow
Write-Host "  View logs:  .\start-local-dev.ps1 -Logs" -ForegroundColor Gray
Write-Host "  Rebuild:    .\start-local-dev.ps1 -Build" -ForegroundColor Gray
Write-Host "  Stop all:   .\start-local-dev.ps1 -Down" -ForegroundColor Gray
Write-Host ""
Write-Host "Testing health endpoint..." -ForegroundColor Cyan
Start-Sleep -Seconds 5
try {
    $Health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
    Write-Host "Backend Status: $($Health.status)" -ForegroundColor Green
} catch {
    Write-Host "Backend still starting... (check logs with -Logs flag)" -ForegroundColor Yellow
}
Write-Host ""
