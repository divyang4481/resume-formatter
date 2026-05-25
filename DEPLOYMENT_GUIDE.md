# Deployment Guide - Resume Formatter Platform

This guide contains the exact commands required to build and deploy the platform for both **Local Development** and **AWS Production**.

## 1. Local Development (Docker Compose)
Use these commands to test everything on your machine. The frontend will automatically connect to `http://localhost:8000`.

```powershell
# Build and Start Local Environment
docker-compose build
docker-compose up -d

# View Logs
docker-compose logs -f
```

---

## 2. AWS Production Deployment (v1.1.8)
When deploying to AWS, you **MUST** pass the production environment flag to the frontend build.

### Step A: Build and Push Images
```powershell
# API
docker build -t 114644266543.dkr.ecr.ap-south-1.amazonaws.com/agentic-doc-api-dev:v1.1.8 -f backend/Dockerfile.api ./backend
docker push 114644266543.dkr.ecr.ap-south-1.amazonaws.com/agentic-doc-api-dev:v1.1.8

# Worker
docker build -t 114644266543.dkr.ecr.ap-south-1.amazonaws.com/agentic-doc-worker-dev:v1.1.8 -f backend/Dockerfile.worker ./backend
docker push 114644266543.dkr.ecr.ap-south-1.amazonaws.com/agentic-doc-worker-dev:v1.1.8

# Frontend (IMPORTANT: Includes --build-arg for production URL)
docker build -t 114644266543.dkr.ecr.ap-south-1.amazonaws.com/agentic-doc-frontend-dev:v1.1.8 --build-arg ENVIRONMENT=production -f frontend/Dockerfile ./frontend
docker push 114644266543.dkr.ecr.ap-south-1.amazonaws.com/agentic-doc-frontend-dev:v1.1.8
```

### Step B: Update ECS Services
This script will register new task definitions and perform a rolling update for all 3 services.
```powershell
python ./artifacts/update_ecs_to_v102.py v1.1.8
```

---

## 3. Environment Troubleshooting
- **RapidOCR Model Error**: Version v1.1.8+ pre-bakes AI models into the image. If you see download errors, ensure you are using v1.1.8.
- **AWS Credentials**: We have disabled hardcoded tokens in `.env`. The containers now use your local `~/.aws` session. Ensure you run `aws sso login` or refresh your local profile.
- **CORS Errors**: Usually caused by backend crashes (500 errors). Check logs first.
- **Empty Fields**: Fixed in v1.1.5+ (JSON mapping fix).
