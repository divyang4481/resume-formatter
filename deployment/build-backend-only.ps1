# Build Backend Docker Image and Push to ECR
# Usage: .\deployment\build-backend-only.ps1 -Region ap-south-1

param (
    [string]$Region = "ap-south-1"
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== Building Backend Docker Image ===" -ForegroundColor Cyan

# Get AWS Account ID
$AccountId = (aws sts get-caller-identity --query Account --output text)
Write-Host "AWS Account: $AccountId" -ForegroundColor Green
Write-Host "Region: $Region" -ForegroundColor Green

# Image details
$ImageName = "resume-formatter-backend"
$Tag = "latest"
$EcrUri = "$AccountId.dkr.ecr.$Region.amazonaws.com"
$FullImageUri = "$EcrUri/${ImageName}:$Tag"

# Step 1: Create ECR repository if it doesn't exist
Write-Host "`n--- Step 1: Checking ECR Repository ---" -ForegroundColor Cyan
$repoExists = aws ecr describe-repositories --repository-names $ImageName --region $Region 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating ECR repository: $ImageName" -ForegroundColor Yellow
    aws ecr create-repository --repository-name $ImageName --region $Region | Out-Null
    Write-Host "Repository created!" -ForegroundColor Green
} else {
    Write-Host "Repository exists: $ImageName" -ForegroundColor Green
}

# Step 2: Login to ECR
Write-Host "`n--- Step 2: Logging into ECR ---" -ForegroundColor Cyan
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $EcrUri
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to login to ECR" -ForegroundColor Red
    exit 1
}
Write-Host "Logged in successfully!" -ForegroundColor Green

# Step 3: Build Docker image
Write-Host "`n--- Step 3: Building Docker Image ---" -ForegroundColor Cyan
Write-Host "This will take 15-30 minutes..." -ForegroundColor Yellow
Write-Host "Building from: backend/docker/Dockerfile.simple" -ForegroundColor Gray

cd backend

docker build `
    --platform linux/amd64 `
    -f docker/Dockerfile.simple `
    -t "${ImageName}:${Tag}" `
    .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker build failed!" -ForegroundColor Red
    cd ..
    exit 1
}

cd ..
Write-Host "Build successful!" -ForegroundColor Green

# Step 4: Tag image for ECR
Write-Host "`n--- Step 4: Tagging Image ---" -ForegroundColor Cyan
docker tag "${ImageName}:${Tag}" $FullImageUri
Write-Host "Tagged as: $FullImageUri" -ForegroundColor Green

# Step 5: Push to ECR
Write-Host "`n--- Step 5: Pushing to ECR ---" -ForegroundColor Cyan
Write-Host "Uploading image (this may take 5-10 minutes)..." -ForegroundColor Yellow

docker push $FullImageUri

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to push image to ECR" -ForegroundColor Red
    exit 1
}

# Get the image digest
$ImageDigest = (aws ecr describe-images --repository-name $RepoName --region $Region --query 'sort_by(imageDetails,&imagePushedAt)[-1].imageDigest' --output text)
$ImageWithDigest = "${AccountId}.dkr.ecr.${Region}.amazonaws.com/${RepoName}@${ImageDigest}"

Write-Host "`n=== BUILD AND PUSH COMPLETE! ===" -ForegroundColor Green
Write-Host "`nImage Tag URI: $FullImageUri" -ForegroundColor Cyan
Write-Host "Image Digest URI: $ImageWithDigest" -ForegroundColor Cyan
Write-Host "`nNext Step: Deploy to AWS" -ForegroundColor Yellow
Write-Host "  .\deployment\deploy-aws.ps1 -Region $Region -StackName resume-formatter-demo" -ForegroundColor Gray
Write-Host ""
