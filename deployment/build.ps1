# Build script for Resume Formatter Backend
# Usage: .\deployment\build.ps1 -Region ap-south-1

param (
    [string]$Region = "ap-south-1"
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== Building Backend Docker Image ===" -ForegroundColor Cyan

# 1. Get AWS Account ID
$AccountId = (aws sts get-caller-identity --query Account --output text)
$RepoName = "resume-formatter-backend"
$ImageUri = "$($AccountId).dkr.ecr.$($Region).amazonaws.com/$($RepoName):latest"

Write-Host "AWS Account: $AccountId" -ForegroundColor Gray
Write-Host "Region: $Region" -ForegroundColor Gray
Write-Host ""

# 2. Ensure repository exists
Write-Host "--- Step 1: Checking ECR Repository ---" -ForegroundColor Yellow
try {
    $null = aws ecr describe-repositories --repository-names $RepoName --region $Region --output json 2>$null
    Write-Host "Repository exists: $RepoName" -ForegroundColor Green
} catch {
    Write-Host "Creating ECR repository: $RepoName..." -ForegroundColor Cyan
    $null = aws ecr create-repository --repository-name $RepoName --region $Region
    Write-Host "Repository created!" -ForegroundColor Green
}
Write-Host ""

# 3. Login to ECR
Write-Host "--- Step 2: Logging into ECR ---" -ForegroundColor Yellow
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com"
if ($LASTEXITCODE -eq 0) {
    Write-Host "Logged in successfully!" -ForegroundColor Green
}
Write-Host ""

# 4. Build Docker Image
Write-Host "--- Step 3: Building Docker Image ---" -ForegroundColor Yellow
Write-Host "This will take 10-15 minutes..." -ForegroundColor Gray
Write-Host "Building from: backend/docker/Dockerfile.simple" -ForegroundColor Gray

docker build --platform linux/amd64 `
    -t "$($RepoName):latest" `
    -f backend/docker/Dockerfile.simple `
    backend/

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nDocker build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Build successful!" -ForegroundColor Green
Write-Host ""

# 5. Tag and Push
Write-Host "--- Step 4: Tagging Image ---" -ForegroundColor Yellow
docker tag "$($RepoName):latest" $ImageUri
Write-Host "Tagged as: $ImageUri" -ForegroundColor Green
Write-Host ""

Write-Host "--- Step 5: Pushing to ECR ---" -ForegroundColor Yellow
Write-Host "Uploading image (this may take 5-10 minutes)..." -ForegroundColor Gray
docker push $ImageUri

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nDocker push failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== BUILD AND PUSH COMPLETE! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Image URI: $ImageUri" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next Step: Deploy to AWS" -ForegroundColor Cyan
Write-Host "  .\deployment\deploy-aws.ps1 -Region $Region -StackName resume-formatter-demo" -ForegroundColor Gray
Write-Host ""
