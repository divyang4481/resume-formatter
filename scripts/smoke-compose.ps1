<#
.SYNOPSIS
  Windows PowerShell smoke test for the Docker Desktop Compose stack.

.DESCRIPTION
  Starts the local integration stack with Docker Compose and verifies API health,
  LocalStack S3/SQS, PostgreSQL, and the runtime upload/confirm/status flow.

  This is the PowerShell equivalent of scripts/smoke-compose.sh for developers
  running Docker Desktop on Windows.

.PARAMETER StartStack
  Start Compose services before running checks. Enabled by default.

.PARAMETER IncludeWorker
  Include the asynchronous worker service in the Compose startup.

.PARAMETER IncludeFrontend
  Include the Angular/nginx frontend service in the Compose startup.

.EXAMPLE
  .\scripts\smoke-compose.ps1

.EXAMPLE
  .\scripts\smoke-compose.ps1 -IncludeWorker -IncludeFrontend

.EXAMPLE
  $env:AWS_REGION = "us-east-1"; .\scripts\smoke-compose.ps1 -NoStartStack
#>
[CmdletBinding()]
param(
    [string]$ComposeCommand = "docker compose",
    [string]$ApiBaseUrl = "http://localhost:8000",
    [string]$LocalStackUrl = "http://localhost:4566",
    [string]$AwsRegion = $(if ($env:AWS_REGION) { $env:AWS_REGION } else { "ap-south-1" }),
    [string]$S3BucketInput = $(if ($env:S3_BUCKET_INPUT) { $env:S3_BUCKET_INPUT } else { "local-resume-input-bucket" }),
    [string]$S3BucketOutput = $(if ($env:S3_BUCKET_OUTPUT) { $env:S3_BUCKET_OUTPUT } else { "local-resume-output-bucket" }),
    [string]$SqsProcessingQueueName = $(if ($env:SQS_PROCESSING_QUEUE_NAME) { $env:SQS_PROCESSING_QUEUE_NAME } else { "resume-processing-queue" }),
    [switch]$IncludeWorker,
    [switch]$IncludeFrontend,
    [switch]$NoStartStack
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot
$env:AWS_REGION = $AwsRegion
$env:S3_BUCKET_INPUT = $S3BucketInput
$env:S3_BUCKET_OUTPUT = $S3BucketOutput
$env:SQS_PROCESSING_QUEUE_NAME = $SqsProcessingQueueName

function Write-Step {
    param([string]$Message)
    $timestamp = (Get-Date).ToUniversalTime().ToString("HH:mm:ss")
    Write-Host "`n[$timestamp] $Message"
}

function Get-ComposeInvocation {
    $parts = $ComposeCommand -split '\s+'
    $command = $parts[0]
    $baseArgs = @()
    if ($parts.Count -gt 1) {
        $baseArgs = $parts[1..($parts.Count - 1)]
    }
    return @{ Command = $command; BaseArgs = $baseArgs }
}

function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $invocation = Get-ComposeInvocation
    $command = $invocation["Command"]
    $baseArgs = $invocation["BaseArgs"]
    & $command @baseArgs @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Compose command failed: $ComposeCommand $($Arguments -join ' ')"
    }
}

function Invoke-ComposeOutput {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $invocation = Get-ComposeInvocation
    $command = $invocation["Command"]
    $baseArgs = $invocation["BaseArgs"]
    $output = & $command @baseArgs @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Compose command failed: $ComposeCommand $($Arguments -join ' ')"
    }
    return $output
}

function Wait-HttpOk {
    param(
        [string]$Url,
        [string]$Label,
        [int]$MaxAttempts = 60
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 | Out-Null
            return
        }
        catch {
            if ($attempt -eq $MaxAttempts) {
                throw "Timed out waiting for $Label at $Url"
            }
            Start-Sleep -Seconds 2
        }
    }
}

function Invoke-JsonEndpoint {
    param(
        [ValidateSet("GET", "POST")][string]$Method,
        [string]$Url
    )

    $response = Invoke-RestMethod -Method $Method -Uri $Url -TimeoutSec 30
    $response | ConvertTo-Json -Depth 20 | Out-Null
    return $response
}

if (-not $NoStartStack) {
    $services = New-Object System.Collections.Generic.List[string]
    $services.Add("postgres")
    $services.Add("localstack")
    $services.Add("api")
    if ($IncludeWorker) { $services.Add("worker") }
    if ($IncludeFrontend) { $services.Add("frontend") }

    Write-Step "Starting Docker Compose services: $($services -join ' ')"
    $composeArgs = @("up", "-d", "--build") + $services.ToArray()
    Invoke-Compose @composeArgs
}

Write-Step "Waiting for API and LocalStack health endpoints"
Wait-HttpOk -Url "$LocalStackUrl/_localstack/health" -Label "LocalStack"
Wait-HttpOk -Url "$ApiBaseUrl/api/health" -Label "API"

Write-Step "Checking API discovery and health endpoints"
Invoke-JsonEndpoint -Method GET -Url "$ApiBaseUrl/api" | Out-Null
Invoke-JsonEndpoint -Method GET -Url "$ApiBaseUrl/api/health" | Out-Null
Invoke-JsonEndpoint -Method GET -Url "$ApiBaseUrl/api/capabilities" | Out-Null
Invoke-JsonEndpoint -Method GET -Url "$ApiBaseUrl/api/health/dependencies" | Out-Null
Invoke-JsonEndpoint -Method GET -Url "$ApiBaseUrl/.well-known/agent-card.json" | Out-Null
Invoke-JsonEndpoint -Method GET -Url "$ApiBaseUrl/.well-known/agent.json" | Out-Null
Invoke-JsonEndpoint -Method GET -Url "$ApiBaseUrl/.well-known/mcp.json" | Out-Null
Invoke-JsonEndpoint -Method GET -Url "$ApiBaseUrl/openapi.json" | Out-Null

Write-Step "Checking LocalStack S3 buckets and SQS queue"
Invoke-Compose exec -T localstack awslocal s3api head-bucket --bucket $S3BucketInput | Out-Null
Invoke-Compose exec -T localstack awslocal s3api head-bucket --bucket $S3BucketOutput | Out-Null
$queueUrl = (Invoke-ComposeOutput exec -T localstack awslocal sqs get-queue-url --queue-name $SqsProcessingQueueName --query QueueUrl --output text | Out-String).Trim()
if ([string]::IsNullOrWhiteSpace($queueUrl)) {
    throw "Unable to resolve LocalStack SQS queue URL for $SqsProcessingQueueName"
}
Invoke-Compose exec -T localstack awslocal sqs get-queue-attributes --queue-url $queueUrl --attribute-names All | Out-Null

Write-Step "Checking RDS-compatible Postgres through the Compose network"
Invoke-Compose exec -T postgres pg_isready -U app_user -d app_db | Out-Null

Write-Step "Exercising runtime upload, queue confirm, and status APIs"
$tmpResume = New-TemporaryFile
try {
    Set-Content -Path $tmpResume.FullName -Value "Jane Candidate`nSoftware Engineer`nPython, AWS, PostgreSQL`n" -NoNewline -Encoding UTF8

    if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
        throw "curl.exe was not found. It is required for multipart upload compatibility across Windows PowerShell versions."
    }
    $uploadJson = & curl.exe -fsS -X POST "$ApiBaseUrl/api/runtime/resumes/upload" -F "file=@$($tmpResume.FullName);filename=smoke-resume.txt;type=text/plain"
    if ($LASTEXITCODE -ne 0) {
        throw "Resume upload request failed."
    }
    $uploadResponse = $uploadJson | ConvertFrom-Json
    $jobId = $uploadResponse.job_id
    if ([string]::IsNullOrWhiteSpace($jobId)) {
        throw "Upload response did not include job_id"
    }

    $confirmResponse = Invoke-JsonEndpoint -Method POST -Url "$ApiBaseUrl/api/runtime/resumes/$jobId/confirm"
    if ($confirmResponse.status -ne "QUEUED") {
        throw "Expected confirm status QUEUED, received $($confirmResponse.status)"
    }

    $statusResponse = Invoke-JsonEndpoint -Method GET -Url "$ApiBaseUrl/api/runtime/resumes/$jobId/status"
    $allowedStatuses = @("QUEUED", "PROCESSING", "COMPLETED", "FAILED")
    if ([string]::IsNullOrWhiteSpace($statusResponse.job_id) -or $allowedStatuses -notcontains $statusResponse.status) {
        throw "Unexpected status response: $($statusResponse | ConvertTo-Json -Depth 20)"
    }

    Write-Step "Checking that upload reached S3 and confirm reached SQS"
    Invoke-Compose exec -T localstack awslocal s3 ls "s3://$S3BucketOutput/jobs/$jobId/input/" | Out-Null
    Invoke-Compose exec -T localstack awslocal sqs get-queue-attributes --queue-url $queueUrl --attribute-names ApproximateNumberOfMessages | Out-Null

    Write-Step "Docker Compose smoke test passed. API, LocalStack S3/SQS, and Postgres are reachable. Job $jobId is queued."
}
finally {
    Remove-Item -Path $tmpResume.FullName -Force -ErrorAction SilentlyContinue
}
