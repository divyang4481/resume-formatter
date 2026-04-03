import os
import sys
import time
import asyncio

# Ensure backend directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.adapters.impls.local.local_queue import SqlAlchemyMessageQueue
from app.dependencies import (
    llm_runtime_dependency, 
    document_extraction_service_dependency, 
    get_job_repository,
    resume_workflow_service_dependency,
    storage_provider_dependency
)

from app.adapters.repositories.template_repository import SqlAlchemyTemplateRepository

async def run_worker():
    print("Starting background worker process (cv-architect)...")
    llm_runtime = llm_runtime_dependency()
    doc_parser_service = document_extraction_service_dependency()
    storage_provider = storage_provider_dependency()

    # Pre-initialize DB locally (SQLite)
    from app.config import settings
    if settings.cloud == "local":
        from app.db.session import engine
        from app.db.models import Base
        Base.metadata.create_all(bind=engine)
        print("Worker local database initialized.")

    while True:
        db = SessionLocal()
        try:
            queue = SqlAlchemyMessageQueue(db)
            job_repository = get_job_repository(db)
            template_repository = SqlAlchemyTemplateRepository(db=db)

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
                print(f"Worker picked up job_id: {job_id}")

                # Execute the workflow via the centralized service
                try:
                    await workflow_service.execute_job(job_id=job_id)
                    print(f"Worker successfully processed job_id: {job_id}")
                except Exception as e:
                    print(f"Worker failed processing job_id: {job_id} with error: {e}")
                    import traceback
                    traceback.print_exc()
                    
                    # Ensure failed status is persisted
                    job = job_repository.get_job(job_id)
                    if job and job.status != "failed":
                        job.status = "failed"
                        job.error_message = str(e)
                        job_repository.save_job(job)
            else:
                # Sleep briefly if queue is empty
                await asyncio.sleep(2)
        except Exception as e:
            print(f"Worker encountered an error: {e}")
            await asyncio.sleep(5)
        finally:
            db.close()

if __name__ == "__main__":
    asyncio.run(run_worker())
