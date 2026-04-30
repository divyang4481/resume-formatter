import os
import sys
import asyncio
import logging
import json

# Set up simple logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("worker")

# Ensure backend directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.db.session import SessionLocal
from app.dependencies import (
    get_document_extraction_service,
    get_job_repository,
    get_template_repository,
    get_storage_provider,
    get_message_queue,
    get_agent_provider,
    get_knowledge_index
)
from app.config import settings

async def process_job(db, message: dict):
    job_id = message.get("job_id")
    job_type = message.get("job_type", "RESUME_FORMATTING")
    input_uri = message.get("input_uri")

    if not job_id:
        logger.error("Job ID missing from message.")
        return

    from app.adapters.repositories.job_repository import SqlAlchemyJobRepository
    job_repo = SqlAlchemyJobRepository(db)
    storage = get_storage_provider()
    doc_parser = get_document_extraction_service()
    agent = get_agent_provider()

    try:
        job = job_repo.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found in DB.")
            return

        job.status = "PROCESSING"
        job_repo.save_job(job)

        # 1. Download source file
        local_path = f"/tmp/{job_id}_source"
        storage.get_file(input_uri, local_path)

        # 2. Extract Document
        job.status = "PARSING"
        job_repo.save_job(job)

        with open(local_path, "rb") as f:
            file_bytes = f.read()

        parsed_doc = await doc_parser.extract(
            file_bytes=file_bytes,
            filename=os.path.basename(input_uri),
            content_type="application/octet-stream"
        )

        parsed_json_key = f"jobs/{job_id}/intermediate/parsed.json"
        storage.put_bytes(json.dumps({"text": parsed_doc.text, "structured": parsed_doc.structured_data}).encode(), parsed_json_key, "application/json")

        # 3. Resume Validity Guard
        job.status = "VALIDATING_RESUME"
        job_repo.save_job(job)

        # Simple heuristic validity check for mock
        is_resume = "experience" in parsed_doc.text.lower() or "education" in parsed_doc.text.lower()
        if not is_resume and job_type != "TEMPLATE_TEST_RUN":
            job.status = "REJECTED_NOT_RESUME"
            job.error_message = "Document does not appear to be a resume."
            job_repo.save_job(job)
            return

        # 4. Agentic Core Extraction & Mapping
        job.status = "MAPPING_WITH_AGENT"
        job_repo.save_job(job)

        # Stub template contract and rules for demonstration
        template_contract = {"fields": ["candidate_summary", "experience"]}
        template_rules = {"format": "bullet points"}
        pii_policy = {"redact_email": True}

        mapped_data = agent.map_resume_to_template(
            parsed_resume={"text": parsed_doc.text},
            template_contract=template_contract,
            template_rules=template_rules,
            pii_policy=pii_policy,
            job_context={"job_id": job_id}
        )

        mapped_json_key = f"jobs/{job_id}/intermediate/mapped.json"
        storage.put_bytes(json.dumps(mapped_data).encode(), mapped_json_key, "application/json")

        # 5. Quality/Completeness Report
        quality_report = {
            "job_id": job_id,
            "overall_confidence": 0.85,
            "needs_review": False
        }
        quality_key = f"jobs/{job_id}/audit/quality_report.json"
        storage.put_bytes(json.dumps(quality_report).encode(), quality_key, "application/json")

        # 6. Render Output (Mock Renderer for now)
        job.status = "RENDERING"
        job_repo.save_job(job)

        # Generate dummy docx
        docx_key = f"jobs/{job_id}/output/formatted.docx"
        docx_uri = storage.put_bytes(b"dummy_docx_content", docx_key, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        # Update Job Status
        job.status = "COMPLETED"
        job.render_docx_uri = docx_uri
        job_repo.save_job(job)

        logger.info(f"Worker successfully processed job_id: {job_id}")
                    queue.ack(message)

    except Exception as e:
        logger.error(f"Worker failed processing job_id: {job_id} with error: {e}", exc_info=True)
        try:
            job = job_repo.get_job(job_id)
            if job:
                job.status = "FAILED"
                job.error_message = str(e)
                job_repo.save_job(job)
        except Exception as db_e:
            logger.error(f"Failed to persist job failure state for job_id: {job_id}: {db_e}")
    finally:
        if os.path.exists(f"/tmp/{job_id}_source"):
            os.remove(f"/tmp/{job_id}_source")

async def run_worker():
    logger.info("Starting long-running ECS background worker...")

    # Initialize DB (SQLite fallback for dev, usually RDS in AWS)
    from app.db.session import engine
    from app.db.models import Base
    Base.metadata.create_all(bind=engine)
    logger.info("Worker database initialized.")

    while True:
        db = SessionLocal()
        queue = get_message_queue()
        try:
            for message in queue.consume():
                logger.info(f"Worker received message: {message['message_id']}")
                body = message['body']
                await process_job(db, body)
                queue.ack(message)

            # Sleep briefly if queue is empty
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Worker encountered a critical error: {e}", exc_info=True)
            await asyncio.sleep(5)
        finally:
            db.close()

if __name__ == "__main__":
    asyncio.run(run_worker())
