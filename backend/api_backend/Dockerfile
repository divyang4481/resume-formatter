# API backend image: REST API + A2A discovery + MCP tool surface.
# Build context must be the backend/ directory.
ARG BASE_IMAGE=114644266543.dkr.ecr.ap-south-1.amazonaws.com/agentic-doc-base-dev:v1.2.0
FROM ${BASE_IMAGE}

WORKDIR /app

# Install dependencies not present in base image.
RUN pip install --no-cache-dir "boto3[crt]" lxml docxtpl

# Copy the shared application package and this backend's entrypoint.
COPY ./app ./app
COPY ./api_backend ./api_backend

EXPOSE 8000

CMD ["uvicorn", "api_backend.entrypoint:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
