import uvicorn
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP
from app.api.runtime import router as runtime_router
from app.api.admin import router as admin_router
from app.api.a2a import router as a2a_router
from app.config import settings


def create_app() -> FastAPI:
    """
    Bootstraps the FastAPI application.
    Integrates all API routes and core configurations.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Always initialize SQLite since we are using it for the DB layer in all clouds
        from app.db.session import engine
        from app.db.models import Base

        # Initialize DB tables
        Base.metadata.create_all(bind=engine)
        print("Database initialized")
        yield

    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(
        lifespan=lifespan,
        title=settings.project_name,
        description="A Template-aware, privacy-governed, agentic document processing platform",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Force DB init during module load for TestClient compat if lifespan isn't awaited natively by the test runner
    from app.db.session import engine
    from app.db.models import Base
    Base.metadata.create_all(bind=engine)

    # Initialize Model Context Protocol (MCP) support
    # This automatically turns FastAPI endpoints into discoverable AI tools
    mcp = FastApiMCP(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:4200"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(
        runtime_router,
        prefix="/runtime",
        tags=["Candidate Processing", "MCP Tool"],
    )
    app.include_router(admin_router, prefix="/admin", tags=["Admin"])
    # Expose at root to match `.well-known` discovery path correctly
    app.include_router(a2a_router, tags=["A2A Discoverability"])

    # This automatically turns FastAPI endpoints into discoverable AI tools
    mcp.mount_http()

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "cloud_mode": settings.cloud}

    @app.get("/")
    async def root():
        return {
            "message": "Welcome to Resume Formatter API. Visit /docs for the API documentation.",
            "status": "active",
        }

    return app


app = create_app()

try:
    from mangum import Mangum
    handler = Mangum(app)
except ImportError:
    pass

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
