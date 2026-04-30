# Pre-Deployment Check Script for AWS Deployment
# Usage: .\deployment\pre-deploy-check.ps1 -Region ap-south-1

param (
    [string]$Region = "ap-south-1",
    [string]$StackName = "resume-formatter-demo"
)

$ErrorActionPreference = "Continue"
$AllChecksPassed = $true

Write-Host "`n=== AWS Deployment Pre-Flight Check ===" -ForegroundColor Cyan
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host "Stack Name: $StackName`n" -ForegroundColor Yellow

# Function to check command
function Test-Command {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

# Function to display check result
function Show-CheckResult {
    param(
        [string]$CheckName,
        [bool]$Passed,
        [string]$Message = ""
    )
    
    if ($Passed) {
        Write-Host "✓ $CheckName" -ForegroundColor Green
        if ($Message) { Write-Host "  $Message" -ForegroundColor Gray }
    } else {
        Write-Host "✗ $CheckName" -ForegroundColor Red
        if ($Message) { Write-Host "  $Message" -ForegroundColor Yellow }
        $script:AllChecksPassed = $false
    }
}

# Check 1: AWS CLI
Write-Host "Checking Prerequisites..." -ForegroundColor Cyan
$HasAwsCli = Test-Command "aws"
if ($HasAwsCli) {
    $AwsVersion = aws --version 2>&1
    Show-CheckResult "AWS CLI Installed" $true $AwsVersion
} else {
    Show-CheckResult "AWS CLI Installed" $false "Install from: https://aws.amazon.com/cli/"
}

# Check 2: AWS Credentials
if ($HasAwsCli) {
    try {
        $AccountId = aws sts get-caller-identity --query Account --output text 2>&1
        if ($LASTEXITCODE -eq 0) {
            Show-CheckResult "AWS Credentials Configured" $true "Account ID: $AccountId"
        } else {
            Show-CheckResult "AWS Credentials Configured" $false "Run: aws configure"
        }
    } catch {
        Show-CheckResult "AWS Credentials Configured" $false "Run: aws configure"
    }
}

# Check 3: Docker
$HasDocker = Test-Command "docker"
if ($HasDocker) {
    try {
        $DockerVersion = docker --version
        $DockerRunning = docker ps 2>&1
        if ($LASTEXITCODE -eq 0) {
            Show-CheckResult "Docker Installed and Running" $true $DockerVersion
        } else {
            Show-CheckResult "Docker Installed and Running" $false "Docker daemon not running"
        }
    } catch {
        Show-CheckResult "Docker Installed and Running" $false "Start Docker Desktop"
    }
} else {
    Show-CheckResult "Docker Installed and Running" $false "Install from: https://www.docker.com/products/docker-desktop"
}

# Check 4: Node.js and npm
$HasNode = Test-Command "node"
$HasNpm = Test-Command "npm"
if ($HasNode -and $HasNpm) {
    $NodeVersion = node --version
    $NpmVersion = npm --version
    Show-CheckResult "Node.js and npm Installed" $true "Node: $NodeVersion, npm: $NpmVersion"
} else {
    Show-CheckResult "Node.js and npm Installed" $false "Install from: https://nodejs.org/"
}

# Check 5: ECR Repository
Write-Host "`nChecking AWS Resources..." -ForegroundColor Cyan
if ($HasAwsCli -and $AccountId) {
    try {
        $EcrRepo = aws ecr describe-repositories --repository-names resume-formatter-backend --region $Region 2>&1
        if ($LASTEXITCODE -eq 0) {
            Show-CheckResult "ECR Repository Exists" $true "resume-formatter-backend"
        } else {
            Show-CheckResult "ECR Repository Exists" $false "Create with: aws ecr create-repository --repository-name resume-formatter-backend --region $Region"
        }
    } catch {
        Show-CheckResult "ECR Repository Exists" $false "Create with: aws ecr create-repository --repository-name resume-formatter-backend --region $Region"
    }
}

# Check 6: Backend Docker Image
if ($HasAwsCli -and $AccountId) {
    try {
        $Images = aws ecr list-images --repository-name resume-formatter-backend --region $Region --query 'imageIds[?imageTag==`latest`]' 2>&1
        if ($LASTEXITCODE -eq 0 -and $Images -ne "[]") {
            Show-CheckResult "Backend Docker Image in ECR" $true "latest tag exists"
        } else {
            Show-CheckResult "Backend Docker Image in ECR" $false "Build and push the Docker image first (see deployment guide)"
        }
    } catch {
        Show-CheckResult "Backend Docker Image in ECR" $false "Build and push the Docker image first (see deployment guide)"
    }
}

# Check 7: Project Structure
Write-Host "`nChecking Project Structure..." -ForegroundColor Cyan
$HasBackend = Test-Path "backend/app/main.py"
Show-CheckResult "Backend Code Present" $HasBackend "backend/app/main.py"

$HasFrontend = Test-Path "frontend/package.json"
Show-CheckResult "Frontend Code Present" $HasFrontend "frontend/package.json"

$HasDeploymentTemplate = Test-Path "deployment/aws-demo.yaml"
Show-CheckResult "CloudFormation Template Present" $HasDeploymentTemplate "deployment/aws-demo.yaml"

$HasDeployScript = Test-Path "deployment/deploy-aws.ps1"
Show-CheckResult "Deployment Script Present" $HasDeployScript "deployment/deploy-aws.ps1"

# Check 8: AWS Bedrock Access
Write-Host "`nChecking AWS Services..." -ForegroundColor Cyan
if ($HasAwsCli) {
    try {
        $BedrockModels = aws bedrock list-foundation-models --region $Region --query 'modelSummaries[0]' 2>&1
        if ($LASTEXITCODE -eq 0) {
            Show-CheckResult "AWS Bedrock Access" $true "Access granted in $Region"
        } else {
            Show-CheckResult "AWS Bedrock Access" $false "Enable Bedrock access in AWS Console for region $Region"
        }
    } catch {
        Show-CheckResult "AWS Bedrock Access" $false "Enable Bedrock access in AWS Console for region $Region"
    }
}

# Check 9: Existing Stack
if ($HasAwsCli) {
    try {
        $StackStatus = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query 'Stacks[0].StackStatus' --output text 2>&1
        if ($LASTEXITCODE -eq 0) {
            Show-CheckResult "Existing Stack Check" $true "Stack '$StackName' exists with status: $StackStatus (will be updated)"
        } else {
            Show-CheckResult "Existing Stack Check" $true "No existing stack (will create new)"
        }
    } catch {
        Show-CheckResult "Existing Stack Check" $true "No existing stack (will create new)"
    }
}

# Summary
Write-Host "`n=== Pre-Flight Check Summary ===" -ForegroundColor Cyan
if ($AllChecksPassed) {
    Write-Host "✓ All checks passed! Ready to deploy." -ForegroundColor Green
    Write-Host "`nNext Steps:" -ForegroundColor Yellow
    Write-Host "  1. Build and push Docker image (if not done):"
    Write-Host "     cd backend"
    Write-Host "     .\deployment\build.ps1 -Region $Region"
    Write-Host "     cd .."
    Write-Host ""
    Write-Host "  2. Run deployment:"
    Write-Host "     .\deployment\deploy-aws.ps1 -Region $Region -StackName $StackName"
} else {
    Write-Host "✗ Some checks failed. Please fix the issues above before deploying." -ForegroundColor Red
    Write-Host "`nSee deployment/AWS_DEPLOYMENT_GUIDE.md for detailed instructions." -ForegroundColor Yellow
}

Write-Host ""
