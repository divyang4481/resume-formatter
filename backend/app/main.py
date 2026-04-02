import uvicorn
from fastapi import FastAPI
from app.api.runtime import router as runtime_router
from app.api.admin import router as admin_router
from app.api.a2a import router as a2a_router
from app.api.mcp import router as mcp_router
from app.config import settings

def create_app() -> FastAPI:
    """
    Bootstraps the FastAPI application.
    Integrates all API routes and core configurations.
    """
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from starlette.requests import Request
    import traceback

    app = FastAPI(
        title=settings.project_name,
        description="A Template-aware, privacy-governed, agentic document processing platform",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def catch_exceptions_middleware(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            # We must return a JSONResponse with CORS headers so that
            # the frontend does not show a misleading CORS error when a 500 occurs.
            traceback.print_exc()
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error", "error": str(e)},
                headers={
                    "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
                    "Access-Control-Allow-Credentials": "true",
                }
            )

    app.include_router(runtime_router, prefix="/v1/runtime", tags=["Runtime"])
    app.include_router(admin_router, prefix="/admin", tags=["Admin"])
    app.include_router(a2a_router, prefix="/a2a", tags=["A2A Discoverability"])
    app.include_router(mcp_router, prefix="/mcp", tags=["MCP Tools"])

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "cloud_mode": settings.cloud}

    @app.get("/")
    async def root():
        return {
            "message": "Welcome to Resume Formatter API. Visit /docs for the API documentation.",
            "status": "active"
        }

    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
