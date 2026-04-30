# Resume Formatter Platform

A full-stack, template-aware document processing platform designed to transform unstructured documents (like resumes and CVs) into structured, template-driven outputs.

---

## Project Structure

- **`backend/`**: A FastAPI application managed with Conda and Poetry. Contains the core logic, API routing, PII rule enforcement, and cloud adapters.
- **`frontend/`**: An Angular Single Page Application (SPA) providing the user interface.

---

## How to Run Locally

### Option 1: Running in VS Code (Recommended)
This project is configured out-of-the-box for VS Code tasks.
1. Open this repository root in VS Code.
2. Go to the **Run and Debug** view on the side panel.
3. Select **`Full Stack: Debug`** or **`Full Stack: Run`** from the debugger dropdown in the top left and hit the **Play** button.

This will automatically execute the tasks to boot both the frontend and backend servers together, and optionally attach a debug browser.

### Option 2: Running Manually from the Terminal

> **Note:** If you are connecting to real AWS resources (S3, SQS, Bedrock), you must still provision the AWS infrastructure (see **Step 1** under *Docker & AWS Setup*) and populate your `.env` file first.

**Frontend (Angular)**
1. Open a terminal and navigate to the frontend directory:
   ```bash
   # Bash or PowerShell
   cd frontend
   npm install
   npm run start
   ```
2. The UI will be available at `http://localhost:4200`

**Backend (FastAPI)**
1. Open a separate terminal and navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Activate your Conda environment and start the server:

   *For Mac/Linux (Bash):*
   ```bash
   conda activate cv-architect
   poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

   *For Windows (PowerShell):*
   ```powershell
   # Ensure you are using the cv-architect conda environment
   conda activate cv-architect
   poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

Because it runs with the `--reload` flag, the server will automatically hot-reload any code changes you make!

---

## Configuration

- **Backend:** Settings and cloud profiles are managed via the `backend/config/` directory. You can configure variables in the `.env` file such as `CLOUD` target (aws, azure, gcp) and `DOCUMENT_PARSER_BACKEND`.
- **Frontend:** Standard Angular proxy and environment configurations are securely nestled in `frontend/src/environments/`.
- **CORS:** Ensure your backend enables CORS for `http://localhost:4200` to handle frontend requests smoothly (already configured).

---

## Helpful URLs

After you start the servers, check out these local URLs:

- **Frontend App:** [http://localhost:4200](http://localhost:4200)
- **The API Root:** [http://localhost:8000/](http://localhost:8000/) *(Returns a friendly JSON response — no more 404!)*
- **Swagger UI Docs:** [http://localhost:8000/docs](http://localhost:8000/docs) *(FastAPI automatically generates this—you can interactively see and test all your endpoints here)*
- **ReDoc Docs:** [http://localhost:8000/redoc](http://localhost:8000/redoc) *(Alternative API documentation viewer)*
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

Refresh your browser, and you should now seamlessly access the UI as well as the API!

## Testing and Coverage

### Backend
The backend tests rely on `pytest`. Unit tests evaluate modules without any dependencies. Integration tests hit actual endpoints with a SQLite configuration in the `.data` folder.

To run tests and get a coverage report:
```bash
cd backend
PYTHONPATH=. poetry run pytest --cov=app --cov-report=term-missing tests/
```

### Frontend
The frontend uses `karma` and `jasmine` for component integration and logic tests.

To run tests and get a coverage report:
```bash
cd frontend
CHROME_BIN=/usr/bin/google-chrome-stable npm run test -- --watch=false --browsers=ChromeHeadless --code-coverage
```

### Playwright E2E
For E2E integration, Playwright is installed. You can run the fast local mocked tests, or the full worker loop.

To run the full E2E flow:
```bash
cd frontend
npx playwright test --config=playwright.full.config.ts
```

To run the fast CI smoke test:
```bash
cd frontend
npx playwright test
```

---

## Docker & AWS Setup (Local vs Cloud)

You can run the entire system locally using Docker Compose, configured to perfectly mirror the cloud environment by connecting directly to real AWS resources (S3, SQS, RDS, and Bedrock).


### Docker Images and PyTorch (CPU vs GPU)
By default, compiling the Docker images pulls a lightweight, CPU-only version of PyTorch. This is intentional to keep the image sizes small and to ensure cost-effective deployments on serverless architectures like AWS ECS Fargate, which do not currently support GPUs.

If you are deploying to EC2 (e.g., `g4dn`) or have a local GPU and wish to leverage CUDA for faster OCR with Docling, you can build the images with GPU support by passing the `USE_GPU=true` build argument:
```bash
docker build -t cv-architect-worker -f backend/Dockerfile.worker --build-arg USE_GPU=true .
```

### Step 1: Provisioning AWS Infrastructure (Required for both Local & Prod)
Before creating local containers or deploying to the cloud, you must provision the necessary AWS resources. We provide an `aws-infrastructure.yaml` CloudFormation template to spin up the necessary backing services in AWS. This template creates:
- **S3 Bucket** (for document storage)
- **SQS Queue** (for asynchronous messaging between the API and Worker)
- **RDS PostgreSQL Database** (for job state and metadata)
- **IAM User / Roles** (for permissions to Bedrock, S3, SQS, and RDS)

**Steps to Provision:**
1. Go to the AWS Console -> CloudFormation.
2. Ensure your region is set to **ap-south-1 (Mumbai)**.
3. Upload `aws-infrastructure.yaml` and create the stack.
4. Once deployed, go to the **Outputs** tab of the stack. You will find:
   - `S3BucketName`
   - `SQSQueueUrl`
   - `RDSConnectionString`
   - `DeveloperAccessKeyId`
   - `DeveloperSecretAccessKey`

### Step 2: Local Setup via Docker Compose (Windows/Mac/Linux)
Because `Docling` requires heavy machine learning libraries (like PyTorch) and system dependencies (like `libgl1`, `libglib2.0-0`), running via Docker is highly recommended to isolate the environment.

**Note:** You must have completed Step 1 to run the containers locally with AWS resources.

We use a 3-container setup that connects directly to your newly created AWS resources:
1. **API Container**: FastAPI Control Plane
2. **Worker Container**: Asynchronous Python Execution Plane
3. **Frontend Container**: Angular Application

**Step-by-Step for Windows (WSL2 / Docker Desktop):**
1. **Prerequisites:** Ensure **WSL2** and **Docker Desktop** are installed and running. Allocate at least 4GB of RAM to Docker Desktop.
   > **Tip:** For Windows users building these containers locally, we highly recommend using Docker Buildx (which is included in modern Docker Desktop) to ensure the images align perfectly with the target Linux execution environment, preventing ML compilation mismatches.
2. **Configure Environment:** In the root directory, open your `.env` file and fill in the outputs from the CloudFormation stack:
   ```env
   AWS_REGION=ap-south-1
   AWS_ACCESS_KEY_ID=<from_cloudformation>
   AWS_SECRET_ACCESS_KEY=<from_cloudformation>
   # Map the single S3 bucket created by CloudFormation to both input and output
   S3_BUCKET_INPUT=<from_cloudformation>
   S3_BUCKET_OUTPUT=<from_cloudformation>
   SQS_PROCESSING_QUEUE_URL=<from_cloudformation>
   DATABASE_URL=<from_cloudformation>
   ```
3. **Run Docker Compose:** Open your terminal in the root directory of the repository and run:
   ```bash
   docker-compose up --build
   ```
4. **Access the App:**
   - Frontend: `http://localhost:4200`
   - API: `http://localhost:8000/docs`

*How it works locally:* Instead of relying on local mock services (like LocalStack or SQLite), your local 3-container setup uses your exact `aws-infrastructure.yaml` configuration. When a file is uploaded, it goes straight to the real S3 bucket. The message is pushed to the real SQS queue, picked up by your local worker container, and LLM reasoning uses the real AWS Bedrock models.

### Step 3: Full AWS Cloud Deployment
The system is built for a scalable, cost-effective AWS setup separating the web server from heavy processing. Since your local containers already use the real AWS backing services (S3, SQS, RDS, Bedrock), the code requires **no changes** for production.

**Deployment Steps for AWS:**
1. **Infrastructure:** You have already completed Step 1 and deployed `aws-infrastructure.yaml`. Keep the outputs handy.
2. **ECR (Elastic Container Registry):** Build and push the backend `docker/Dockerfile` and frontend `Dockerfile` images to your ECR.
3. **Fargate (Control Plane):** Deploy the API image to an ECS Fargate cluster via `cloudformation.yaml`. Map it behind an Application Load Balancer. It handles fast HTTP traffic.
4. **Fargate/ECS (Execution Plane):** Deploy the Worker image as an ECS Service reading from the SQS queue. Configure Auto-Scaling based on queue depth to keep costs low (it scales to 0 when idle).
5. **Agentic Core / Bedrock:** Ensure your AWS Bedrock Agent using `meta.llama3-8b-instruct-v1:0` (or similar) is active. The ECS tasks will use their assigned IAM Task Role instead of IAM User keys.

## Resource Mapping
| Component | Implementation (Local Docker & AWS Cloud) |
| :--- | :--- |
| **Worker Compute** | Docker Container (Local) / ECS Fargate Tasks (Cloud) |
| **API Server** | Docker Container (Local) / ECS Fargate + ALB (Cloud) |
| **Message Queue** | Amazon SQS (Provisioned via CFN) |
| **Database State** | Amazon RDS PostgreSQL (Provisioned via CFN) |
| **Storage (Blobs)** | Amazon S3 (Provisioned via CFN) |
| **Reasoning Agent** | AWS Bedrock Agents |
| **Knowledge Base** | AWS Bedrock Knowledge Bases |
| **Extraction** | Docling (Inside Docker Containers) |

### APIs
The API is cleanly separated into two distinct spaces:
1. **Runtime API (`/runtime`)**: Stateless, used by candidate/recruiter applications to upload resumes and poll for results.
2. **Admin API (`/admin`)**: Fully handles template versioning, knowledge assets, formatting rules, and sample test-runs before publishing templates.

### Worker Node
Due to the memory footprint of deep learning OCR libraries like `Docling`, processing has been refactored into a scalable, asynchronous ECS Worker task rather than AWS Lambda. A lightweight `API` layer runs independently to ensure fast HTTP responses.
