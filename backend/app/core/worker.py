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

async def run_worker():
    logger.info("Starting background worker process (cv-architect)...")

    # Initialize singleton-like stateless dependencies
    llm_runtime = get_llm_runtime()
    doc_parser_service = get_document_extraction_service()
    storage_provider = get_storage_provider()

    # Pre-initialize DB locally (SQLite)
    if settings.cloud == "local":
        from app.db.session import engine
        from app.db.models import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Worker local database initialized.")

    while True:
        db = SessionLocal()
        try:
            # Re-initialize DB-bound dependencies per session
            queue = get_message_queue(db)
            job_repository = get_job_repository(db)
            template_repository = get_template_repository(db)

            # Initialize the workflow service with current DB session dependencies
            workflow_service = resume_workflow_service_dependency(
                llm=llm_runtime,
                parser=doc_parser_service,
                job_repo=job_repository,
                template_repo=template_repository,
                storage=storage_provider
            )

            message = queue.dequeue("document_processing")
            if message:
                job_id = message.get("job_id")
                logger.info(f"Worker picked up job_id: {job_id}")

                # Execute the workflow via the centralized service
                try:
                    await workflow_service.execute_job(job_id=job_id)
                    logger.info(f"Worker successfully processed job_id: {job_id}")
                except Exception as e:
                    logger.error(f"Worker failed processing job_id: {job_id} with error: {e}", exc_info=True)
                    
                    # Ensure failed status is persisted
                    try:
                        job = job_repository.get_job(job_id)
                        if job and job.status != "failed":
                            job.status = "failed"
                            job.error_message = str(e)
                            job_repository.save_job(job)
                    except Exception as db_e:
                        logger.error(f"Failed to persist job failure state for job_id: {job_id}: {db_e}")
            else:
                # Sleep briefly if queue is empty
                await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Worker encountered a critical error: {e}", exc_info=True)
            await asyncio.sleep(5)
        finally:
            db.close()

if __name__ == "__main__":
    asyncio.run(run_worker())
