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

# Concurrency throttling to avoid overwhelming downstream LLM providers.
MAX_CONCURRENT_JOBS = getattr(settings, "max_parallel_jobs", 3)
semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

async def process_job_task(job_id: str, queue_name: str, queue_message: dict, llm_runtime, doc_parser_service, storage_provider):
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
            queue = get_message_queue(db)

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
            queue.mark_completed(queue_name, queue_message)
            logger.info(f"Task: Successfully finished job_id: {job_id}")

        except Exception as e:
            logger.error(f"Task: Critical failure for job_id: {job_id}: {e}", exc_info=True)
            
            # Attempt one final fail-state persistence in a fresh session if needed
            try:
                # Use a fresh repository for the fail-state to avoid session pollution
                job_repository = get_job_repository(db)
                queue = get_message_queue(db)
                job = job_repository.get_job(job_id)
                if job and job.status != "failed":
                    job.status = "failed"
                    job.error_message = str(e)
                    job_repository.save_job(job)
                queue.mark_failed(queue_name, queue_message, error=str(e))
            except Exception as db_e:
                logger.error(f"Task: Could not persist failure for job_id: {job_id}: {db_e}")
        finally:
            db.close()

async def cleanup_stuck_messages(queue_name: str):
    """
    On startup, reset any messages that are in 'processing' state back to 'pending'.
    This is useful for local development where a restart/crash would otherwise leave
    jobs stuck until the visibility timeout expires.
    """
    db = SessionLocal()
    try:
        from app.db.models import LocalQueueMessage
        stuck_messages = db.query(LocalQueueMessage).filter(
            LocalQueueMessage.queue_name == queue_name,
            LocalQueueMessage.status == "processing"
        ).all()
        
        if stuck_messages:
            logger.info(f"Startup: Found {len(stuck_messages)} orphaned 'processing' messages. Resetting to 'pending'.")
            for msg in stuck_messages:
                msg.status = "pending"
            db.commit()
    except Exception as e:
        logger.error(f"Startup: Failed to cleanup stuck messages: {e}")
    finally:
        db.close()

async def run_worker():
    logger.info(f"Starting async background worker process (cv-architect) with concurrency limit: {MAX_CONCURRENT_JOBS}")
    queue_name = settings.document_processing_queue_name

    # Initialize shared singleton-like stateless dependencies
    llm_runtime = get_llm_runtime()
    doc_parser_service = get_document_extraction_service()
    storage_provider = get_storage_provider()

    # Pre-initialize DB locally (SQLite) or wait for remote DB
    if settings.cloud == "local":
        from app.db.session import engine
        from app.db.models import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Worker: Central database schema verified.")
    else:
        # For cloud deployments, wait for database to be available
        logger.info("Worker: Waiting for database to be available...")
        max_retries = 30
        retry_count = 0
        db_ready = False
        
        while retry_count < max_retries and not db_ready:
            try:
                from sqlalchemy import text
                from app.db.session import engine
                from app.db.models import Base
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                Base.metadata.create_all(bind=engine)
                logger.info("Worker: Database connected and schema verified.")
                db_ready = True
            except Exception as e:
                retry_count += 1
                logger.warning(f"Worker: Database not ready (attempt {retry_count}/{max_retries}): {str(e)}")
                await asyncio.sleep(10)  # Wait 10 seconds before retry
        
        if not db_ready:
            logger.error("Worker: Failed to connect to database after maximum retries. Starting anyway...")

    # Startup Cleanup: Reset orphaned 'processing' messages to 'pending'
    # This prevents jobs from being stuck for 30 minutes after a restart/crash.
    await cleanup_stuck_messages(queue_name)

    while True:
        db = SessionLocal()
        try:
            queue = get_message_queue(db)
            message = queue.dequeue(queue_name)
            
            if message:
                job_id = message.get("job_id")
                logger.info(f"Worker: Processing job_id {job_id}")
                # Dispatch task to run in background (concurrency controlled by semaphore inside task)
                asyncio.create_task(process_job_task(job_id, queue_name, message, llm_runtime, doc_parser_service, storage_provider))
                
                # Small yield to allow the task to start and potentially claim the semaphore before next poll
                await asyncio.sleep(0.1)
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
