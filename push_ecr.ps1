
$ErrorActionPreference = "Stop"
$REGISTRY="114644266543.dkr.ecr.ap-south-1.amazonaws.com"
$VERSION="v1.8.9"

Write-Host "Building API..."
docker build --build-arg BASE_IMAGE=agentic-doc-base-local:latest -f backend/Dockerfile.api -t ${REGISTRY}/agentic-doc-api-dev:latest -t ${REGISTRY}/agentic-doc-api-dev:${VERSION} backend

Write-Host "Building Worker..."
docker build --build-arg BASE_IMAGE=agentic-doc-base-local:latest -f backend/Dockerfile.worker -t ${REGISTRY}/agentic-doc-worker-dev:latest -t ${REGISTRY}/agentic-doc-worker-dev:${VERSION} backend

Write-Host "Building Frontend..."
docker build --build-arg ENVIRONMENT=development -f frontend/Dockerfile -t ${REGISTRY}/agentic-doc-frontend-dev:latest -t ${REGISTRY}/agentic-doc-frontend-dev:${VERSION} frontend

Write-Host "Pushing API..."
docker push ${REGISTRY}/agentic-doc-api-dev:latest
docker push ${REGISTRY}/agentic-doc-api-dev:${VERSION}

Write-Host "Pushing Worker..."
docker push ${REGISTRY}/agentic-doc-worker-dev:latest
docker push ${REGISTRY}/agentic-doc-worker-dev:${VERSION}

Write-Host "Pushing Frontend..."
docker push ${REGISTRY}/agentic-doc-frontend-dev:latest
docker push ${REGISTRY}/agentic-doc-frontend-dev:${VERSION}

Write-Host "Done!"

