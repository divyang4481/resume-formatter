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

**Frontend (Angular)**
1. Open a terminal and navigate to the frontend directory:
   ```bash
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
   ```bash
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

## Local Docker Setup & Deployment

You can run the entire system locally using Docker, ensuring parity with the cloud environment.

### Running Locally via Docker
Because `Docling` requires heavy machine learning libraries (like PyTorch) and system dependencies (like `libgl1`, `libglib2.0-0`), running via Docker is highly recommended to isolate the environment. The `docker-compose.yml` spins up:
1. The **FastAPI API Server** (Control Plane)
2. The **Asynchronous Python Worker** (Execution Plane)
3. **LocalStack / Redis / Local File Storage** (Mock Infrastructure)

**Steps:**
1. Ensure Docker Desktop is running (works well on Windows WSL2 or macOS).
2. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```
3. Run `docker-compose up --build`:
   ```bash
   docker-compose up --build
   ```
*Note for Windows users:* The Dockerfiles are optimized to run `docling` without crashing by pre-installing `libgl1` and `gcc`. Ensure Docker Desktop is allocated at least 4GB of RAM.

### AWS Cloud Deployment
The system is built for a scalable, cost-effective AWS setup separating the web server from heavy processing.

**Deployment Steps for AWS:**
1. **ECR (Elastic Container Registry):** Build and push the `Dockerfile.api` and `Dockerfile.worker` images to your ECR.
2. **Fargate (Control Plane):** Deploy the `Dockerfile.api` image to an ECS Fargate cluster. Map it behind an Application Load Balancer. It handles fast HTTP traffic.
3. **Fargate/ECS (Execution Plane):** Deploy the `Dockerfile.worker` image as an ECS Service reading from an SQS queue. Configure Auto-Scaling based on queue depth to keep costs low (it scales to 0 when idle).
4. **Agentic Core / Bedrock:** Create an AWS Bedrock Agent using `meta.llama3-8b-instruct-v1:0` (or similar) and link an S3-backed Bedrock Knowledge Base.
5. **Infrastructure:** Map environments to use S3 for Storage, SQS for Queues, and DynamoDB/Aurora/RDS for Job State.

### Resource Mapping: Local vs AWS
| Component | Local Development | AWS Cost-Effective Deployment |
| :--- | :--- | :--- |
| **Orchestrator** | LangGraph (Local Memory) | LangGraph (Python in Worker) |
| **Worker Compute** | Docker Container | ECS Fargate Tasks (Auto-Scaling) |
| **API Server** | Docker Container (Uvicorn) | ECS Fargate + ALB |
| **Message Queue** | Local in-memory / SQLite | Amazon SQS |
| **Database State** | SQLite | Amazon DynamoDB or RDS Serverless |
| **Storage (Blobs)** | Local File System | Amazon S3 |
| **Reasoning Agent** | Ollama / Mock Local Agent | AWS Bedrock Agents |
| **Knowledge Base** | Local FAISS / Memory | AWS Bedrock Knowledge Bases |
| **Extraction** | Docling (Local PyTorch) | Docling (Inside ECS Worker Container) |

### APIs
The API is cleanly separated into two distinct spaces:
1. **Runtime API (`/runtime`)**: Stateless, used by candidate/recruiter applications to upload resumes and poll for results.
2. **Admin API (`/admin`)**: Fully handles template versioning, knowledge assets, formatting rules, and sample test-runs before publishing templates.

### Worker Node
Due to the memory footprint of deep learning OCR libraries like `Docling`, processing has been refactored into a scalable, asynchronous ECS Worker task rather than AWS Lambda. A lightweight `API` layer runs independently to ensure fast HTTP responses.
