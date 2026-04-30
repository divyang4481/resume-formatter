# AWS Deployment Troubleshooting Guide

## Quick Diagnosis

After deploying, run the diagnostic script:
```powershell
.\deployment\diagnose-deployment.ps1 -StackName resume-formatter-demo -Region ap-south-1
```

This will check:
- ✓ API health and availability
- ✓ CORS configuration
- ✓ App Runner service status
- ✓ Database connectivity
- ✓ S3 bucket access
- ✓ CloudWatch logs
- ✓ ECS worker status

## Common Issues and Solutions

### 1. CORS Errors (Most Common)

**Symptom**: Browser console shows:
```
Access to XMLHttpRequest at 'https://xxx.awsapprunner.com' from origin 'http://bucket.s3-website-region.amazonaws.com' has been blocked by CORS policy
```

**Root Causes**:
- Frontend URL doesn't match CORS_ORIGINS environment variable
- CORS_ORIGINS not set correctly in App Runner

**Solution**:
```powershell
# 1. Get your actual frontend URL
$StackName = "resume-formatter-demo"
$Region = "ap-south-1"
$FrontendUrl = (aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='FrontendUrl'].OutputValue" --output text)

echo "Frontend URL: $FrontendUrl"

# 2. Check App Runner CORS_ORIGINS environment variable
.\deployment\diagnose-deployment.ps1 -StackName $StackName -Region $Region

# 3. If CORS_ORIGINS is wrong, update CloudFormation and redeploy
.\deployment\deploy-aws.ps1 -Region $Region -StackName $StackName
```

**Manual Fix** (if CloudFormation is correct but App Runner needs update):
```powershell
# Update App Runner service environment variable directly
$ServiceArn = (aws apprunner list-services --region $Region --output json | ConvertFrom-Json).ServiceSummaryList | Where-Object { $_.ServiceName -eq "$StackName-api" } | Select-Object -ExpandProperty ServiceArn

# Note: App Runner requires a full service update via CloudFormation
# Easier to just redeploy the stack
```

### 2. 500 Internal Server Error

**Symptom**: API calls return 500 status code

**Common Causes**:

#### A. Database Connection Failed
**Check logs**:
```powershell
aws logs tail /aws/apprunner/resume-formatter-demo-api/service --follow --region ap-south-1
```

Look for: `sqlalchemy.exc.OperationalError` or `database connection failed`

**Solution**:
- Verify RDS is in "available" status
- Check DATABASE_URL format: `postgresql://user:pass@host:5432/postgres`
- Ensure App Runner VPC connector has access to RDS security group

#### B. AWS Bedrock Access Denied
**Check logs for**: `AccessDeniedException` or `bedrock` errors

**Solution**:
1. Enable Bedrock in your AWS region:
   - Go to AWS Bedrock console
   - Request model access for Claude/Titan
   - Wait 5-10 minutes for approval

2. Verify IAM role permissions:
```powershell
# Check if BackendTaskRole has Bedrock permissions
aws iam get-role-policy --role-name resume-formatter-demo-BackendTaskRole --policy-name BackendPermissions --region ap-south-1
```

#### C. S3 Bucket Permission Issues
**Check logs for**: `S3UploadFailedError` or `AccessDenied`

**Solution**:
- Verify IAM role has S3 permissions for the storage bucket
- Check bucket exists and is in the correct region

#### D. Missing Dependencies
**Check logs for**: `ModuleNotFoundError` or `ImportError`

**Solution**:
- Rebuild Docker image with all dependencies
- Verify `pyproject.toml` includes all required packages
```powershell
.\deployment\build.ps1 -Region ap-south-1
.\deployment\deploy-aws.ps1 -Region ap-south-1
```

#### E. LLM Model Configuration Issues
**Check logs for**: `Model not found` or `Invalid model configuration`

**Solution**:
- For AWS Bedrock: Use `anthropic.claude-v2` or `amazon.titan-text-express-v1`
- Update environment variable:
```yaml
LLM_MODEL_NAME: "anthropic.claude-v2"
```

### 3. Service Won't Start (App Runner Stuck)

**Symptom**: App Runner shows "Creating" or "Updating" for > 15 minutes

**Check**:
1. **Health check failing**:
   - App Runner health check path: `/health`
   - Timeout: 10 seconds
   - If app takes longer to start, increase timeout in CloudFormation

2. **Docker image pull failed**:
   - Verify image exists in ECR
   - Check ECR repository permissions
   - Verify image was built for `linux/amd64` platform

**Solution**:
```powershell
# Check ECR images
aws ecr list-images --repository-name resume-formatter-backend --region ap-south-1

# If no images, rebuild and push
.\deployment\build.ps1 -Region ap-south-1

# Then redeploy
.\deployment\deploy-aws.ps1 -Region ap-south-1
```

### 4. Frontend Not Loading

**Symptom**: S3 URL returns 404 or blank page

**Checks**:
1. Files uploaded to S3?
```powershell
aws s3 ls s3://YOUR-FRONTEND-BUCKET/ --region ap-south-1
```

2. Bucket configured for static website hosting?
3. Bucket policy allows public read?

**Solution**:
```powershell
# Rebuild and re-sync frontend
cd frontend
npm install
npm run build -- --configuration production
cd ..

$BucketName = "YOUR-FRONTEND-BUCKET"
aws s3 sync frontend/dist/frontend/browser s3://$BucketName --delete --region ap-south-1
```

### 5. Worker Not Processing Jobs

**Symptom**: Jobs stay in "pending" status, never complete

**Check**:
```powershell
# Check ECS tasks are running
aws ecs describe-services --cluster resume-formatter-demo-cluster --services worker --region ap-south-1

# Check worker logs
aws logs tail /ecs/resume-formatter-demo-worker --follow --region ap-south-1
```

**Solution**:
- Ensure worker has same environment variables as API
- Check worker has access to database and S3
- Verify task definition is correct

### 6. High Costs

**Symptom**: AWS bill higher than expected

**Check**:
- App Runner: Scales with traffic (check metrics)
- Data transfer: S3 to App Runner transfer costs
- RDS: Running 24/7
- ECS Fargate: Worker running continuously

**Solution to reduce costs**:
```powershell
# Stop non-production stacks
aws cloudformation delete-stack --stack-name resume-formatter-demo --region ap-south-1

# Or scale down:
# - Use smaller RDS instance (db.t4g.micro)
# - Reduce App Runner CPU/memory
# - Stop ECS worker when not needed
```

## Viewing Logs

### App Runner API Logs
```powershell
# Follow live logs
aws logs tail /aws/apprunner/resume-formatter-demo-api/service --follow --region ap-south-1

# Get last 100 lines
aws logs tail /aws/apprunner/resume-formatter-demo-api/service --since 1h --region ap-south-1
```

### ECS Worker Logs
```powershell
aws logs tail /ecs/resume-formatter-demo-worker --follow --region ap-south-1
```

### CloudFormation Events
```powershell
# Check deployment progress
aws cloudformation describe-stack-events --stack-name resume-formatter-demo --region ap-south-1 --max-items 20
```

## Testing CORS Manually

```powershell
# Test OPTIONS preflight request
$FrontendUrl = "http://YOUR-BUCKET.s3-website-ap-south-1.amazonaws.com"
$ApiUrl = "https://YOUR-SERVICE.ap-south-1.awsapprunner.com"

Invoke-WebRequest -Uri "$ApiUrl/health" -Method Options -Headers @{
    "Origin" = $FrontendUrl
    "Access-Control-Request-Method" = "POST"
    "Access-Control-Request-Headers" = "Content-Type"
} -Verbose
```

Look for response header: `Access-Control-Allow-Origin: YOUR-FRONTEND-URL`

## Emergency Rollback

If deployment breaks everything:

```powershell
# 1. Find last working stack
aws cloudformation list-stacks --region ap-south-1 --stack-status-filter UPDATE_COMPLETE

# 2. Get previous template
aws cloudformation get-template --stack-name resume-formatter-demo --region ap-south-1 > old-template.json

# 3. Redeploy with old template
aws cloudformation deploy --template-file old-template.json --stack-name resume-formatter-demo --region ap-south-1
```

## Getting Help

1. **Run diagnostics first**:
   ```powershell
   .\deployment\diagnose-deployment.ps1 -StackName resume-formatter-demo -Region ap-south-1
   ```

2. **Check comprehensive health endpoint**:
   ```powershell
   Invoke-RestMethod -Uri "https://YOUR-API-URL/health"
   ```

3. **Collect logs**:
   ```powershell
   aws logs tail /aws/apprunner/resume-formatter-demo-api/service --since 30m --region ap-south-1 > api-logs.txt
   ```

4. **Check GitHub issues**: Common problems may already be documented

## Best Practices

1. **Always run pre-deployment check**:
   ```powershell
   .\deployment\pre-deploy-check.ps1 -Region ap-south-1
   ```

2. **Test locally first**: Ensure app works with `docker-compose up` before AWS deployment

3. **Use staging environment**: Test deployments in separate stack first

4. **Monitor costs**: Set up AWS Budget alerts

5. **Enable detailed logging**: Set `LOG_LEVEL=DEBUG` in development

6. **Backup database**: Take RDS snapshots before major updates
