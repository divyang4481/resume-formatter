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
