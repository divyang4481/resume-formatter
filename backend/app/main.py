import uvicorn
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute
from fastapi_mcp import FastApiMCP
from app.api.runtime import router as runtime_router
from app.api.admin_endpoints import router as admin_endpoints_router
from app.api.admin import router as admin_folder_router
from app.api.processing import router as processing_router
from app.api.a2a import router as a2a_router
from app.config import settings


def _route_paths(app: FastAPI) -> list[str]:
    return sorted({getattr(route, "path", "") for route in app.routes if isinstance(route, BaseRoute)})


def _set_stable_operation_ids(app: FastAPI) -> None:
    """
    Give FastAPI-MCP stable, readable tool names after all routers are registered.
    Route function names are easier for agents to use than generated names that include paths.
    """
    seen: dict[str, int] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        base_id = route.name
        count = seen.get(base_id, 0)
        seen[base_id] = count + 1
        route.operation_id = base_id if count == 0 else f"{base_id}_{count + 1}"


def create_app() -> FastAPI:
    """
    Bootstraps the API container application.
    Integrates REST API routes, A2A discovery, MCP tool exposure, and core configuration.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Initialize database tables (using RDS/PostgreSQL in AWS)
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:4200"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(
        runtime_router,
        prefix="/api/runtime",
        tags=["Candidate Processing", "MCP Tool"],
    )
    app.include_router(admin_endpoints_router, prefix="/api/admin", tags=["Admin"])
    app.include_router(admin_folder_router, prefix="/api/admin", tags=["Admin"])
    app.include_router(processing_router, prefix="/api/v1/processing", tags=["Processing", "MCP Tool"])
    # Expose at root to match `.well-known` discovery paths correctly.
    app.include_router(a2a_router, tags=["A2A Discoverability"])

    # Initialize Model Context Protocol (MCP) support after all routers are registered.
    # FastApiMCP introspects the app's OpenAPI route table, so mounting after route
    # registration ensures REST processing endpoints are exposed as MCP tools.
    _set_stable_operation_ids(app)
    mcp = FastApiMCP(app)
    mcp.mount_http()

    @app.get("/api/health")
    async def health_check():
        route_paths = _route_paths(app)
        return {
            "status": "healthy",
            "runtime_mode": settings.runtime_mode,
            "api": "ready",
            "a2a": {
                "status": "ready",
                "agent_card_url": "/.well-known/agent-card.json",
                "legacy_agent_card_url": "/.well-known/agent.json",
            },
            "mcp": {
                "status": "ready" if any(path.startswith("/mcp") for path in route_paths) else "not_mounted",
                "url": "/mcp",
                "discovery_url": "/.well-known/mcp.json",
            },
        }

    @app.get("/api/capabilities")
    async def capabilities():
        return {
            "api": {
                "status": "ready",
                "docs_url": "/docs",
                "openapi_url": "/openapi.json",
                "processing_prefix": "/api/v1/processing",
            },
            "a2a": {
                "status": "ready",
                "agent_card_urls": ["/.well-known/agent-card.json", "/.well-known/agent.json"],
            },
            "mcp": {
                "status": "ready",
                "endpoint": "/mcp",
                "discovery_url": "/.well-known/mcp.json",
            },
        }

    @app.get("/api")
    async def root():
        return {
            "message": "Welcome to Resume Formatter API. Visit /docs for the API documentation.",
            "status": "active",
            "capabilities_url": "/api/capabilities",
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
