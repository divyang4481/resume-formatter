# Local Development Guide

## Overview
Run the **exact same Docker containers** used in production, but connected to AWS cloud services for testing before deployment.

## Architecture
- **Backend API**: Docker container (same as production)
- **Worker**: Docker container (same as production)
- **Frontend**: Docker container (or npm for faster dev)
- **Database**: AWS RDS PostgreSQL (shared with production)
- **LLM**: AWS Bedrock Llama 3
- **Storage**: AWS S3

## Prerequisites

1. **Docker Desktop** installed and running
2. **AWS CLI** configured with credentials:
   ```bash
   aws configure
   ```
3. **AWS Services** deployed (from CloudFormation stack)

## Quick Start

### First Time Setup

1. **Verify AWS Connection**:
   ```powershell
   aws sts get-caller-identity
   ```

2. **Configuration is already created** in `backend/.env.local`:
   - Database URL points to AWS RDS
   - LLM configured for AWS Bedrock
   - Storage points to AWS S3

3. **Build Docker Images** (first time only):
   ```powershell
   .\start-local-dev.ps1 -Build
   ```

4. **Start All Services**:
   ```powershell
   .\start-local-dev.ps1
   ```

### Daily Development Workflow

**Start services**:
```powershell
.\start-local-dev.ps1
```

**View logs**:
```powershell
.\start-local-dev.ps1 -Logs
```

**Stop services**:
```powershell
.\start-local-dev.ps1 -Down
```

**Rebuild after code changes**:
```powershell
.\start-local-dev.ps1 -Build
```

## Access Points

- **Frontend**: http://localhost:4200
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Admin API**: http://localhost:8000/admin/templates

## Testing Workflow

1. **Make code changes** in `backend/app/` or `frontend/src/`
2. **Rebuild** if needed: `.\start-local-dev.ps1 -Build`
3. **Test locally** at http://localhost:4200
4. **When satisfied**, deploy to AWS:
   ```powershell
   .\deployment\build.ps1 -Region ap-south-1
   .\deployment\deploy-aws.ps1 -Region ap-south-1 -StackName resume-formatter-demo
   ```

## Differences from Production

| Aspect | Local | Production |
|--------|-------|------------|
| Container Runtime | Docker Desktop | AWS App Runner / ECS |
| Code Changes | Hot-reload with volumes | Requires rebuild & redeploy |
| Logs | `docker-compose logs` | CloudWatch Logs |
| Debugging | Full access | Limited (log-based) |

## Benefits

✅ **Same container** - No "works on my machine" issues  
✅ **Real AWS services** - Test with production data/models  
✅ **Fast iteration** - No deployment wait times  
✅ **Full debugging** - Use breakpoints, inspect state  
✅ **Cost effective** - Only pay for AWS resources usage  

## Troubleshooting

### Containers won't start
```powershell
# Check logs
.\start-local-dev.ps1 -Logs

# Check container status
docker-compose -f docker-compose.local.yml ps
```

### Database connection issues
```powershell
# Test database connection
docker-compose -f docker-compose.local.yml exec backend-api python -c "from app.db.session import engine; print(engine.connect())"
```

### AWS credentials not working
```powershell
# Verify AWS credentials
aws sts get-caller-identity

# Re-configure if needed
aws configure
```

### Port already in use
```powershell
# Stop existing containers
.\start-local-dev.ps1 -Down

# Or manually:
docker stop resume-formatter-api-local resume-formatter-worker-local resume-formatter-frontend-local
```

## Manual Docker Commands

If you prefer direct Docker Compose control:

```powershell
# Start services
docker-compose -f docker-compose.local.yml up -d

# View logs
docker-compose -f docker-compose.local.yml logs -f backend-api

# Restart a service
docker-compose -f docker-compose.local.yml restart backend-api

# Stop all
docker-compose -f docker-compose.local.yml down

# Rebuild
docker-compose -f docker-compose.local.yml build --no-cache
```

## Environment Variables

Configuration is in `backend/.env.local`:
- `DATABASE_URL`: AWS RDS connection string
- `LLM_BACKEND`: aws_bedrock
- `LLM_MODEL_NAME`: meta.llama3-8b-instruct-v1:0
- `AWS_REGION`: ap-south-1
- `STORAGE_BACKEND`: s3
- `S3_BUCKET`: Your S3 bucket name

## Next Steps

After testing locally:
1. Commit your changes
2. Build production image: `.\deployment\build.ps1`
3. Deploy to AWS: `.\deployment\deploy-aws.ps1`
4. Verify in production: https://nvkk38xxmk.ap-south-1.awsapprunner.com
