import os
import sys
import time
import asyncio

# Ensure backend directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.adapters.impls.local.local_queue import SqlAlchemyMessageQueue
from app.api.runtime import async_process_document_task
from app.dependencies import llm_runtime_dependency, document_extraction_service_dependency, get_job_repository

async def run_worker():
    print("Starting background worker process...")
    llm_runtime = llm_runtime_dependency()
    doc_parser_service = document_extraction_service_dependency()

    while True:
        db = SessionLocal()
        try:
            queue = SqlAlchemyMessageQueue(db)
            job_repository = get_job_repository(db)

            message = queue.dequeue("document_processing")
            if message:
                job_id = message.get("job_id")
                print(f"Worker picked up job_id: {job_id}")

                # Execute the workflow
                try:
                    await async_process_document_task(job_id, llm_runtime, doc_parser_service, job_repository)
                    print(f"Worker successfully processed job_id: {job_id}")
                except Exception as e:
                    print(f"Worker failed processing job_id: {job_id} with error: {e}")
                    job = job_repository.get_job(job_id)
                    if job:
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
