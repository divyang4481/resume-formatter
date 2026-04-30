# AWS Deployment Script for Resume Formatter Demo
# Usage: .\deployment\deploy.ps1 -Region us-east-1 -StackName resume-demo

param (
    [string]$Region = "us-east-1",
    [string]$StackName = "resume-formatter-demo"
)

$ErrorActionPreference = "Stop"

# 1. Get AWS Account ID
$AccountId = (aws sts get-caller-identity --query Account --output text)
if ($null -eq $AccountId) { Write-Error "Could not get AWS Account ID. Is AWS CLI configured?"; exit }

Write-Host "--- Starting Deployment for Account: $AccountId in Region: $Region ---" -ForegroundColor Cyan

# 2. Ensure ECR Repository exists
$RepoName = "resume-formatter-backend"
Write-Host "--- Ensuring ECR Repository exists: $RepoName ---"
try {
    $null = aws ecr describe-repositories --repository-names $RepoName --region $Region --output json 2>$null
} catch {
    Write-Host "Creating repository $RepoName..."
    $null = aws ecr create-repository --repository-name $RepoName --region $Region
}
$BackendImageUri = "$($AccountId).dkr.ecr.$($Region).amazonaws.com/$($RepoName):latest"
Write-Host "--- Target Image URI: $BackendImageUri ---" -ForegroundColor Gray

# 3. Docker Login, Build and Push
Write-Host "--- Logging into ECR ---"
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com"

Write-Host "--- Building Backend Docker Image (linux/amd64) ---"
docker build --platform linux/amd64 -t $RepoName -f backend/docker/Dockerfile backend/
if ($LASTEXITCODE -ne 0) { Write-Error "Docker build failed"; exit }

Write-Host "--- Tagging and Pushing Image to ECR ---"
docker tag "$($RepoName):latest" $BackendImageUri
docker push $BackendImageUri
if ($LASTEXITCODE -ne 0) { Write-Error "Docker push failed"; exit }

# 4. Deploy CloudFormation Stack
Write-Host "--- Deploying CloudFormation Stack: $StackName (This may take several minutes) ---"
aws cloudformation deploy `
    --template-file deployment/aws-demo.yaml `
    --stack-name $StackName `
    --parameter-overrides BackendImage=$BackendImageUri `
    --capabilities CAPABILITY_IAM `
    --region $Region

# 5. Get Stack Outputs (API URL and S3 Bucket)
$Outputs = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].Outputs" --output json | ConvertFrom-Json
$ApiUrl = ($Outputs | Where-Object { $_.OutputKey -eq "ApiUrl" }).OutputValue
$BucketName = ($Outputs | Where-Object { $_.OutputKey -eq "FrontendBucketName" }).OutputValue

if ($null -eq $BucketName) {
    # Fallback if output missing
    $BucketName = "$AccountId-$StackName-frontend"
}

Write-Host "--- API URL: $ApiUrl ---" -ForegroundColor Green
Write-Host "--- Bucket Name: $BucketName ---" -ForegroundColor Green

# 6. Build and Deploy Frontend
Write-Host "--- Updating Frontend API Configuration ---"
# Temporary update to the API Service file
$ApiServicePath = "frontend/src/app/services/api.service.ts"
(Get-Content $ApiServicePath) -replace "http://localhost:8000", $ApiUrl | Set-Content $ApiServicePath

Write-Host "--- Building Angular Frontend ---"
cd frontend
npm install
npm run build -- --configuration production
cd ..

Write-Host "--- Syncing Frontend to S3 ---"
# Note: Adjust 'dist/frontend' to match your actual build output directory
$DistFolder = "frontend/dist/frontend/browser" 
if (-not (Test-Path $DistFolder)) { $DistFolder = "frontend/dist/frontend" } # Fallback for older Angular versions

aws s3 sync $DistFolder "s3://$BucketName" --delete --region $Region

Write-Host "`n--- DEPLOYMENT COMPLETE! ---" -ForegroundColor Green
Write-Host "Frontend URL: $(($Outputs | Where-Object { $_.OutputKey -eq 'FrontendUrl' }).OutputValue)" -ForegroundColor Yellow
Write-Host "Backend API: $ApiUrl" -ForegroundColor Yellow
