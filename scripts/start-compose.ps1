<#
.SYNOPSIS
  Starts the local Docker Desktop Compose stack on Windows.

.DESCRIPTION
  Convenience wrapper for Windows developers. It creates .env.local from
  .env.local.example when needed, validates Docker Desktop is reachable, and
  starts the API, worker, frontend, LocalStack, and Postgres services.

.EXAMPLE
  .\scripts\start-compose.ps1

.EXAMPLE
  .\scripts\start-compose.ps1 -NoBuild -Detached:$false
#>
[CmdletBinding()]
param(
    [switch]$NoBuild,
    [bool]$Detached = $true
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found. Install and start Docker Desktop for Windows first."
}

docker version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not reachable. Start Docker Desktop and retry."
}

if (-not (Test-Path ".env.local") -and (Test-Path ".env.local.example")) {
    Copy-Item ".env.local.example" ".env.local"
    Write-Host "Created .env.local from .env.local.example. Add real Bedrock credentials/profile if needed."
}

$args = @("compose", "up")
if ($Detached) { $args += "-d" }
if (-not $NoBuild) { $args += "--build" }

Write-Host "Starting local stack with: docker $($args -join ' ')"
& docker @args
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose startup failed."
}

Write-Host "`nLocal stack URLs:"
Write-Host "  Frontend:   http://localhost:4200"
Write-Host "  API:        http://localhost:8000/api/health"
Write-Host "  LocalStack: http://localhost:4566/_localstack/health"
Write-Host "  Postgres:   localhost:5432 (app_user/app_password/app_db)"
Write-Host "`nRun .\scripts\smoke-compose.ps1 -NoStartStack to verify an already-running stack."
