import os
import logging
import traceback
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi_mcp import FastApiMCP
from app.api.processing import router as processing_router
from app.api.admin import router as admin_router
from app.api.a2a import router as a2a_router
from app.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Bootstraps the FastAPI application.
    Integrates all API routes and core configurations.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Initialize DB tables (idempotent, safe to run multiple times)
        try:
            logger.info("Starting application initialization...")
            logger.info(f"Cloud mode: {settings.cloud}")
            logger.info(f"Storage backend: {settings.storage_backend}")
            logger.info(f"LLM backend: {settings.llm_backend}")
            logger.info(f"CORS origins: {settings.cors_origins}")
            
            # Try to initialize database, but don't fail if it's not ready
            try:
                from app.db.session import engine
                from app.db.models import Base, TemplateAsset
                from sqlalchemy.orm import Session
                
                logger.info("Creating database tables...")
                Base.metadata.create_all(bind=engine)
                logger.info("Database tables created successfully")
                
                # Seed basic data if empty
                with Session(engine) as session:
                    count = session.query(TemplateAsset).count()
                    if count == 0:
                        logger.info("Seeding initial demo data...")
                        from app.schemas.enums import AssetStatus
                        demo_template = TemplateAsset(
                            id="general_professional_v1",
                            name="General Professional",
                            version="1.0.0",
                            status="ACTIVE",
                            industry="General",
                            created_by="system",
                            is_active=True
                        )
                        session.add(demo_template)
                        session.commit()
                        logger.info("Demo data seeded successfully")
                    else:
                        logger.info(f"Found {count} existing templates")
            except Exception as db_error:
                logger.warning(f"Database initialization failed (will retry on first request): {str(db_error)}")
            
            # Optionally start an embedded worker in the API process.
            # Keep disabled by default when a dedicated worker service is deployed.
            if settings.enable_api_embedded_worker:
                try:
                    from app.core.worker import run_worker
                    import asyncio
                    asyncio.create_task(run_worker())
                    logger.info("Embedded background worker started in API process")
                except Exception as worker_error:
                    logger.warning(f"Embedded background worker failed to start: {str(worker_error)}")
            else:
                logger.info("Embedded background worker is disabled in API process")
            
            logger.info("Application initialized successfully")
        except Exception as e:
            logger.error(f"Error during startup: {str(e)}")
            logger.error(traceback.format_exc())
            # Don't raise - allow app to start even if initialization partially fails
        
        yield
        
        logger.info("Application shutting down...")

    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(
        lifespan=lifespan,
        title=settings.project_name,
        description="A Template-aware, privacy-governed, agentic document processing platform",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Initialize Model Context Protocol (MCP) support
    # This automatically turns FastAPI endpoints into discoverable AI tools
    mcp = FastApiMCP(app)

    # Add error handling middleware
    @app.middleware("http")
    async def error_handling_middleware(request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            logger.error(f"Unhandled exception: {str(exc)}")
            logger.error(traceback.format_exc())
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error",
                    "error": str(exc) if settings.log_level == "DEBUG" else "An error occurred"
                }
            )
    
    # Add CORS middleware
    logger.info(f"Configuring CORS with origins: {settings.cors_origins_list}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    
    # Add validation error handler
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"Validation error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors(), "body": exc.body}
        )
    
    # Add general exception handler
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {str(exc)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "error": str(exc) if settings.log_level == "DEBUG" else "An error occurred",
                "path": str(request.url)
            }
        )

    app.include_router(
        processing_router,
        prefix="/v1/processing",
        tags=["Candidate Processing", "MCP Tool"],
    )
    app.include_router(admin_router, prefix="/admin", tags=["Admin"])
    # Expose at root to match `.well-known` discovery path correctly
    app.include_router(a2a_router, tags=["A2A Discoverability"])

    # This automatically turns FastAPI endpoints into discoverable AI tools
    mcp.mount_http()

    @app.get("/health")
    async def health_check():
        """Lightweight health check endpoint for load balancers"""
        return {
            "status": "healthy",
            "service": "resume-formatter-api"
        }

    @app.get("/readiness")
    async def readiness_check():
        """Comprehensive readiness check for all dependencies"""
        readiness_status = {
            "status": "ready",
            "cloud_mode": settings.cloud,
            "storage_backend": settings.storage_backend,
            "llm_backend": settings.llm_backend,
            "cors_configured": len(settings.cors_origins_list) > 0,
        }
        
        # Check database connection
        try:
            from sqlalchemy import text
            from app.db.session import engine
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            readiness_status["database"] = "connected"
        except Exception as e:
            logger.warning(f"Database readiness check failed: {str(e)}")
            readiness_status["database"] = "not_ready"
            readiness_status["database_error"] = str(e)
            readiness_status["status"] = "not_ready"
        
        # Check storage
        try:
            if settings.storage_backend == "s3":
                import boto3
                s3 = boto3.client('s3')
                s3.head_bucket(Bucket=settings.s3_bucket)
                readiness_status["storage"] = "connected"
            else:
                import os
                if os.path.exists(settings.local_storage_path):
                    readiness_status["storage"] = "connected"
                else:
                    readiness_status["storage"] = "path_missing"
        except Exception as e:
            logger.warning(f"Storage readiness check failed: {str(e)}")
            readiness_status["storage"] = "not_ready"
            readiness_status["storage_error"] = str(e)
            readiness_status["status"] = "not_ready"
        
        return readiness_status

    @app.get("/")
    async def root():
        return {
            "message": "Welcome to Resume Formatter API. Visit /docs for the API documentation.",
            "status": "active",
        }

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
