# AWS Deployment Guide - Resume Formatter

## Overview
This guide will help you deploy the Resume Formatter application to AWS with proper CORS configuration.

## Architecture
- **Frontend**: S3 Static Website Hosting
- **API**: AWS App Runner (auto-scaling containerized API)
- **Worker**: ECS Fargate (background processing)
- **Database**: RDS PostgreSQL
- **Storage**: S3 bucket for document storage
- **LLM**: AWS Bedrock

## Prerequisites

1. **AWS CLI** installed and configured
   ```powershell
   aws --version
   aws configure
   ```

2. **Docker** installed and running (for building container images)
   ```powershell
   docker --version
   ```

3. **Node.js and npm** installed (for frontend build)
   ```powershell
   node --version
   npm --version
   ```

4. **AWS Account Setup**:
   - IAM user with appropriate permissions (ECR, CloudFormation, S3, App Runner, ECS, RDS)
   - AWS Bedrock access enabled in your region
   - ECR repository created

## Pre-Deployment Steps

### Step 1: Create ECR Repository
```powershell
$Region = "ap-south-1"
aws ecr create-repository --repository-name resume-formatter-backend --region $Region
```

### Step 2: Build and Push Docker Image
```powershell
cd backend

# Get ECR login token
$AccountId = (aws sts get-caller-identity --query Account --output text)
$Region = "ap-south-1"
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com"

# Build the image
docker build -f docker/Dockerfile -t resume-formatter-backend:latest .

# Tag and push
docker tag resume-formatter-backend:latest "$AccountId.dkr.ecr.$Region.amazonaws.com/resume-formatter-backend:latest"
docker push "$AccountId.dkr.ecr.$Region.amazonaws.com/resume-formatter-backend:latest"

cd ..
```

### Step 3: Deploy the Stack
```powershell
.\deployment\deploy-aws.ps1 -Region ap-south-1 -StackName resume-formatter-demo
```

## What the Deployment Does

1. **Creates Infrastructure**:
   - VPC with public subnets
   - RDS PostgreSQL database
   - S3 buckets for frontend and storage
   - App Runner service for API
   - ECS Fargate cluster for worker
   - IAM roles and security groups

2. **Configures CORS**:
   - Backend accepts requests from the S3 frontend URL
   - Both HTTP and HTTPS protocols supported
   - Configured via `CORS_ORIGINS` environment variable

3. **Builds and Deploys Frontend**:
   - Updates API URL in Angular environment
   - Builds production bundle
   - Syncs to S3 bucket
   - Enables static website hosting

## CORS Configuration

### Backend Configuration
The backend CORS settings are configured via environment variables:

```yaml
CORS_ORIGINS: "http://frontend-bucket.s3-website-region.amazonaws.com,https://frontend-bucket.s3-website-region.amazonaws.com"
```

The backend code (in `config.py`) parses this comma-separated list and applies it to the FastAPI CORS middleware.

### Frontend Configuration
The frontend makes requests to the App Runner API URL, which is automatically configured during deployment in `environment.ts`.

## Verification Steps

After deployment completes:

1. **Check API Health**:
   ```powershell
   # Get API URL from CloudFormation outputs
   $StackName = "resume-formatter-demo"
   $Region = "ap-south-1"
   $ApiUrl = (aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
   
   # Test health endpoint
   Invoke-RestMethod -Uri "https://$ApiUrl/health"
   ```

2. **Check Frontend**:
   - Open the Frontend URL in browser
   - Open browser DevTools (F12) > Console
   - Look for any CORS errors
   - Should see no errors related to cross-origin requests

3. **Test Upload**:
   - Upload a test resume PDF
   - Verify it processes successfully
   - Check backend logs if issues occur

## Troubleshooting CORS Issues

### Issue: "CORS policy: No 'Access-Control-Allow-Origin' header"

**Cause**: Backend CORS_ORIGINS doesn't include the frontend origin

**Solution**:
1. Get the frontend URL from S3 bucket properties
2. Update the CloudFormation stack with correct CORS_ORIGINS
3. Redeploy or update App Runner environment variables manually

### Issue: "Access-Control-Allow-Credentials: true but credentials not set"

**Cause**: Mismatch in credentials handling

**Solution**: 
- Ensure frontend HTTP client includes credentials in requests if needed
- Or set `allow_credentials=False` in backend CORS middleware

### Issue: Preflight OPTIONS request fails

**Cause**: Missing or incorrect CORS headers

**Solution**:
- Verify `allow_methods=["*"]` and `allow_headers=["*"]` in backend
- Check that OPTIONS requests return proper headers

## Environment Variables Reference

### Backend Environment Variables (App Runner)
- `DATABASE_URL`: PostgreSQL connection string
- `CLOUD`: Set to "aws"
- `STORAGE_BACKEND`: Set to "s3"
- `S3_BUCKET`: Storage bucket name
- `LLM_BACKEND`: Set to "aws_bedrock"
- `CORS_ORIGINS`: Comma-separated list of allowed origins

### Frontend Environment Variables
- `apiUrl`: App Runner API URL (configured in `environment.ts`)

## Cost Considerations

Estimated monthly costs (ap-south-1 region):
- App Runner: ~$25-50 (depends on traffic)
- ECS Fargate: ~$30-40 (1 worker task)
- RDS db.t4g.micro: ~$15-20
- S3: ~$1-5 (storage and requests)
- Data Transfer: Variable
- **Total**: ~$70-115/month

## Cleanup

To delete all resources:
```powershell
$StackName = "resume-formatter-demo"
$Region = "ap-south-1"

# Empty S3 buckets first
$AccountId = (aws sts get-caller-identity --query Account --output text)
aws s3 rm "s3://$AccountId-$StackName-frontend" --recursive
aws s3 rm "s3://$AccountId-$StackName-storage" --recursive

# Delete the stack
aws cloudformation delete-stack --stack-name $StackName --region $Region

# Monitor deletion
aws cloudformation wait stack-delete-complete --stack-name $StackName --region $Region
```

## Support

If you encounter issues:
1. Check CloudFormation Events in AWS Console for stack errors
2. Check App Runner logs in CloudWatch
3. Check ECS task logs for worker issues
4. Verify IAM permissions
5. Ensure AWS Bedrock is enabled in your region
