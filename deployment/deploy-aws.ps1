# Deployment script for Resume Formatter (Stack + Frontend)
# Usage: .\deployment\deploy-aws.ps1 -Region ap-south-1 -StackName resume-formatter-demo

param (
    [string]$Region = "ap-south-1",
    [string]$StackName = "resume-formatter-demo"
)

$ErrorActionPreference = "Stop"

$AccountId = (aws sts get-caller-identity --query Account --output text)

# Get the latest image digest instead of using :latest tag
Write-Host "Retrieving latest image digest..." -ForegroundColor Yellow
$ImageDigest = (aws ecr describe-images --repository-name resume-formatter-backend --region $Region --query 'sort_by(imageDetails,&imagePushedAt)[-1].imageDigest' --output text)
$BackendImageUri = "$($AccountId).dkr.ecr.$($Region).amazonaws.com/resume-formatter-backend@$ImageDigest"
Write-Host "Using image: $BackendImageUri" -ForegroundColor Cyan

Write-Host "`n--- Deploying CloudFormation Stack: $StackName ---" -ForegroundColor Cyan
aws cloudformation deploy `
    --template-file deployment/aws-demo.yaml `
    --stack-name $StackName `
    --parameter-overrides BackendImage=$BackendImageUri `
    --capabilities CAPABILITY_IAM `
    --region $Region

# Get Outputs
$Outputs = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].Outputs" --output json | ConvertFrom-Json
$ApiUrl = ($Outputs | Where-Object { $_.OutputKey -eq "ApiUrl" }).OutputValue
$BucketName = ($Outputs | Where-Object { $_.OutputKey -eq "FrontendBucketName" }).OutputValue

if ($null -eq $BucketName) { $BucketName = "$AccountId-$StackName-frontend" }

Write-Host "`nDeployment Outputs:" -ForegroundColor Cyan
Write-Host "  API URL: $ApiUrl"
Write-Host "  Frontend Bucket: $BucketName"

# Build and Sync Frontend
Write-Host "`n--- Updating Frontend API Configuration ---" -ForegroundColor Cyan
$EnvFilePath = "frontend/src/environments/environment.ts"

# Ensure API URL has https:// prefix
if (-not $ApiUrl.StartsWith("http")) {
    $ApiUrl = "https://$ApiUrl"
}

Write-Host "  Setting API URL to: $ApiUrl"
(Get-Content $EnvFilePath) -replace "apiUrl:\s*'.*?'", "apiUrl: '$ApiUrl'" | Set-Content $EnvFilePath

Write-Host "--- Building Angular Frontend ---"
cd frontend
npm install
npm run build -- --configuration production
cd ..

Write-Host "--- Syncing Frontend to S3 ($BucketName) ---"
$DistFolder = "frontend/dist/frontend/browser" 
if (-not (Test-Path $DistFolder)) { $DistFolder = "frontend/dist/frontend" }

aws s3 sync $DistFolder "s3://$BucketName" --delete --region $Region

Write-Host "`n--- DEPLOYMENT COMPLETE! ---" -ForegroundColor Green
$FrontendUrl = ($Outputs | Where-Object { $_.OutputKey -eq 'FrontendUrl' }).OutputValue
Write-Host "`nDeployment URLs:" -ForegroundColor Yellow
Write-Host "  Frontend: $FrontendUrl" -ForegroundColor Cyan
Write-Host "  API:      $ApiUrl" -ForegroundColor Cyan

Write-Host "`nVerifying API Health..." -ForegroundColor Yellow
try {
    $HealthCheck = Invoke-RestMethod -Uri "$ApiUrl/health" -Method Get -TimeoutSec 10
    Write-Host "  API Status: $($HealthCheck.status) [OK]" -ForegroundColor Green
    Write-Host "  Cloud Mode: $($HealthCheck.cloud_mode)" -ForegroundColor Green
} catch {
    Write-Host "  Warning: Could not reach API health endpoint" -ForegroundColor Yellow
    Write-Host "  This is normal if the service is still starting up" -ForegroundColor Yellow
}

Write-Host "`nNext Steps:" -ForegroundColor Cyan
Write-Host "  1. Wait 2-3 minutes for App Runner to fully start"
Write-Host "  2. Open the Frontend URL in your browser"
Write-Host "  3. Check browser console for any CORS errors"
Write-Host "  4. Test file upload functionality"
