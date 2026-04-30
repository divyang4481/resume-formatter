# AWS Deployment - Quick Start Guide

## 🚀 Deploy in 3 Steps

### Step 1: Pre-Flight Check
```powershell
# Run from project root
.\deployment\pre-deploy-check.ps1 -Region ap-south-1
```

This checks:
- ✓ AWS CLI configured
- ✓ Docker running
- ✓ Node.js installed
- ✓ ECR repository exists
- ✓ Bedrock access enabled

### Step 2: Build & Push Docker Image
```powershell
.\deployment\build.ps1 -Region ap-south-1
```

This will:
- Create ECR repositories if needed
- Build Docker image for linux/amd64
- Push to ECR

**Time**: ~10-30 minutes (depending on network speed)

### Step 3: Deploy Stack
```powershell
.\deployment\deploy-aws.ps1 -Region ap-south-1 -StackName resume-formatter-demo
```

This will:
- Deploy CloudFormation stack (VPC, RDS, App Runner, ECS, S3)
- Build Angular frontend
- Upload frontend to S3
- Configure CORS automatically

**Time**: ~15-20 minutes

---

## 📋 After Deployment

### Verify Deployment
```powershell
.\deployment\diagnose-deployment.ps1 -StackName resume-formatter-demo -Region ap-south-1
```

This comprehensive diagnostic checks:
- ✓ API health endpoint
- ✓ CORS configuration
- ✓ Database connectivity
- ✓ S3 bucket access
- ✓ App Runner status
- ✓ CloudWatch logs
- ✓ Worker service

### Get URLs
```powershell
$Outputs = aws cloudformation describe-stacks --stack-name resume-formatter-demo --region ap-south-1 --query "Stacks[0].Outputs" --output json | ConvertFrom-Json

Write-Host "Frontend: $(($Outputs | Where-Object { $_.OutputKey -eq 'FrontendUrl' }).OutputValue)"
Write-Host "API: $(($Outputs | Where-Object { $_.OutputKey -eq 'ApiUrl' }).OutputValue)"
```

---

## 🔧 Fixing Issues

### CORS Errors
If you see CORS errors in browser console:

```powershell
.\deployment\fix-cors.ps1 -StackName resume-formatter-demo -Region ap-south-1
```

This will:
- Update S3 CORS configuration
- Verify App Runner CORS_ORIGINS
- Test CORS preflight requests

### 500 Server Errors
Check the detailed troubleshooting guide:
```powershell
Get-Content .\deployment\TROUBLESHOOTING.md
```

Common causes:
1. **Database not ready**: Wait 2-3 minutes after deployment
2. **Bedrock not enabled**: Enable in AWS Console
3. **Missing environment variables**: Check App Runner configuration

### View Logs
```powershell
# Live API logs
aws logs tail /aws/apprunner/resume-formatter-demo-api/service --follow --region ap-south-1

# Recent errors
aws logs tail /aws/apprunner/resume-formatter-demo-api/service --since 30m --filter-pattern "ERROR" --region ap-south-1
```

---

## 🎯 Key Configuration Files

### Backend CORS
- **File**: `backend/app/config.py`
- **Environment Variable**: `CORS_ORIGINS` (comma-separated URLs)
- **Default**: `*` (allow all)
- **AWS**: Set in CloudFormation → App Runner → Environment Variables

### Frontend API URL
- **File**: `frontend/src/environments/environment.ts`
- **Updated**: Automatically during deployment
- **Format**: `https://xxx.region.awsapprunner.com`

### CloudFormation Template
- **File**: `deployment/aws-demo.yaml`
- **Resources**: 
  - S3 (Frontend + Storage)
  - App Runner (API)
  - ECS Fargate (Worker)
  - RDS PostgreSQL (Database)
  - VPC, Security Groups, IAM Roles

---

## 📊 Monitoring

### Health Check
```powershell
Invoke-RestMethod -Uri "https://YOUR-API-URL/health"
```

Returns:
```json
{
  "status": "healthy",
  "cloud_mode": "aws",
  "storage_backend": "s3",
  "llm_backend": "aws_bedrock",
  "database": "connected",
  "storage": "connected",
  "cors_configured": true
}
```

### API Documentation
Open in browser: `https://YOUR-API-URL/docs`

### CloudWatch Dashboard
```powershell
# Get App Runner metrics
aws apprunner list-services --region ap-south-1

# View in AWS Console
# CloudWatch > Metrics > AppRunner
```

---

## 💰 Cost Estimate

| Resource | Cost (USD/month) |
|----------|------------------|
| App Runner | $25-50 |
| ECS Fargate (Worker) | $30-40 |
| RDS db.t4g.micro | $15-20 |
| S3 Storage + Requests | $1-5 |
| Data Transfer | $5-15 |
| **Total** | **$75-130** |

To reduce costs:
- Use smaller RDS instance
- Scale down App Runner CPU/memory
- Stop ECS worker when not needed
- Delete stack when not in use

---

## 🧹 Cleanup

To delete everything:
```powershell
# 1. Empty S3 buckets first (required)
$AccountId = (aws sts get-caller-identity --query Account --output text)
$StackName = "resume-formatter-demo"
$Region = "ap-south-1"

aws s3 rm "s3://$AccountId-$StackName-frontend" --recursive --region $Region
aws s3 rm "s3://$AccountId-$StackName-storage" --recursive --region $Region

# 2. Delete CloudFormation stack
aws cloudformation delete-stack --stack-name $StackName --region $Region

# 3. Wait for deletion (optional)
aws cloudformation wait stack-delete-complete --stack-name $StackName --region $Region

Write-Host "Stack deleted successfully!" -ForegroundColor Green
```

**Note**: RDS deletion takes ~10-15 minutes. A final snapshot is created by default.

---

## 🆘 Need Help?

1. **Run diagnostics**: `.\deployment\diagnose-deployment.ps1`
2. **Check troubleshooting guide**: `.\deployment\TROUBLESHOOTING.md`
3. **View logs**: `aws logs tail /aws/apprunner/.../service --follow`
4. **Check AWS Console**: CloudFormation > Stacks > Events

---

## 📚 Documentation

- [AWS Deployment Guide](AWS_DEPLOYMENT_GUIDE.md) - Detailed step-by-step
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues and fixes
- [Architecture Docs](../Docs/ARCHITECTURE_ANALYSIS.md) - System design

---

## 🔄 Update Deployment

To update an existing deployment:

```powershell
# 1. Rebuild Docker image (if code changed)
.\deployment\build.ps1 -Region ap-south-1

# 2. Redeploy (updates App Runner with new image)
.\deployment\deploy-aws.ps1 -Region ap-south-1 -StackName resume-formatter-demo
```

CloudFormation will:
- Detect changes
- Update only modified resources
- Zero-downtime update for App Runner

---

## ✅ Success Checklist

After deployment, verify:

- [ ] API health endpoint returns `{"status": "healthy"}`
- [ ] Frontend loads at S3 URL
- [ ] Browser console shows no CORS errors
- [ ] File upload works
- [ ] Resume processing completes
- [ ] CloudWatch logs show no errors

---

**Ready to deploy?**

```powershell
# All-in-one (if you've done this before)
.\deployment\build.ps1 -Region ap-south-1
.\deployment\deploy-aws.ps1 -Region ap-south-1 -StackName resume-formatter-demo
.\deployment\diagnose-deployment.ps1 -StackName resume-formatter-demo -Region ap-south-1
```

Good luck! 🎉
