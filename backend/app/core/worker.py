import os
import sys
import asyncio
import logging

# Set up simple logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("worker")

# Ensure backend directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.db.session import SessionLocal
from app.dependencies import (
    get_llm_runtime,
    get_document_extraction_service,
    get_job_repository,
    resume_workflow_service_dependency,
    get_storage_provider,
    get_message_queue,
    get_template_repository
)
from app.config import settings

# Concurrency Throttling to prevent overloading local LLM
MAX_CONCURRENT_JOBS = getattr(settings, "max_parallel_jobs", 3)
semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

async def process_job_task(job_id: str, llm_runtime, doc_parser_service, storage_provider):
    """
    Independently processes a single job in its own database session context.
    """
    async with semaphore:
        db = SessionLocal()
        try:
            logger.info(f"Task: Starting processing for job_id: {job_id}")
            
            # Initialize DB-bound dependencies for this specific task
            job_repository = get_job_repository(db)
            template_repository = get_template_repository(db)

            # Initialize the workflow service
            workflow_service = resume_workflow_service_dependency(
                llm=llm_runtime,
                parser=doc_parser_service,
                job_repo=job_repository,
                template_repo=template_repository,
                storage=storage_provider
            )

            # Execute the workflow
            await workflow_service.execute_job(job_id=job_id)
            logger.info(f"Task: Successfully finished job_id: {job_id}")

        except Exception as e:
            logger.error(f"Task: Critical failure for job_id: {job_id}: {e}", exc_info=True)
            
            # Attempt one final fail-state persistence in a fresh session if needed
            try:
                # Use a fresh repository for the fail-state to avoid session pollution
                job_repository = get_job_repository(db)
                job = job_repository.get_job(job_id)
                if job and job.status != "failed":
                    job.status = "failed"
                    job.error_message = str(e)
                    job_repository.save_job(job)
            except Exception as db_e:
                logger.error(f"Task: Could not persist failure for job_id: {job_id}: {db_e}")
        finally:
            db.close()

async def run_worker():
    logger.info(f"Starting async background worker process (cv-architect) with concurrency limit: {MAX_CONCURRENT_JOBS}")

    # Initialize shared singleton-like stateless dependencies
    llm_runtime = get_llm_runtime()
    doc_parser_service = get_document_extraction_service()
    storage_provider = get_storage_provider()

    # Pre-initialize DB locally (SQLite)
    if settings.cloud == "local":
        from app.db.session import engine
        from app.db.models import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Worker: Central database schema verified.")

    # Track active background tasks
    background_tasks = set()

    while True:
        # Clean up finished tasks from the tracker
        background_tasks = {t for t in background_tasks if not t.done()}

        db = SessionLocal()
        try:
            queue = get_message_queue(db)
            message = queue.dequeue("document_processing")
            
            if message:
                job_id = message.get("job_id")
                # Spawn an independent async task for this job
                task = asyncio.create_task(
                    process_job_task(job_id, llm_runtime, doc_parser_service, storage_provider)
                )
                background_tasks.add(task)
                logger.info(f"Worker: Dispatched job_id {job_id} to background. Active tasks: {len(background_tasks)}")
            else:
                # Polling interval
                await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Worker Loop Encountered Critical Error: {e}", exc_info=True)
            await asyncio.sleep(5)
        finally:
            db.close()

if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker process interrupted by user. Shutting down gracefully...")
