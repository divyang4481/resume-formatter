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
    from app.dependencies import get_llm_runtime
    llm_runtime = get_llm_runtime()

    from app.agent.graph import build_template_processing_graph, build_resume_processing_graph

    try:
        job = job_repo.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found in DB.")
            return

        job.status = "PROCESSING"
        job_repo.save_job(job)

        filename = input_uri.split("/")[-1]
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if input_uri.endswith(".docx") else "application/pdf"

        initial_state = {
            "session_id": job_id,
            "file_path": input_uri,
            "filename": filename,
            "content_type": content_type,
            "file_type": content_type,
            "runtime_metadata": {
                "template_id": message.get("template_id"),
                "version_id": message.get("version_id")
            }
        }

        if job_type == "TEMPLATE_PROCESSING":
            graph = build_template_processing_graph(doc_parser, storage, job_repo)
            result = await graph.ainvoke(initial_state)

            if "_failed" in result.get("status", ""):
                error_msg = result.get("validation_errors", ["Unknown AI failure"])[0]
                raise ValueError(f"AI Template Processing Failed: {error_msg}")

            # Update template status
            template_id = message.get("template_id")
            version_id = message.get("version_id")
            if template_id and version_id:
                from app.db.models import TemplateAsset
                from app.schemas.enums import AssetStatus
                template = db.query(TemplateAsset).filter_by(id=template_id, version=version_id).first()
                if template:
                    contract = result.get("canonical_model")
                    if isinstance(contract, list) and len(contract) > 0:
                        template.field_extraction_manifest = json.dumps(contract)
                        template.status = AssetStatus.READY_FOR_TESTING.value
                    else:
                        template.status = "FAILED"
                        template.field_extraction_manifest = json.dumps([])
                    db.commit()

        elif job_type in ["RESUME_FORMATTING", "TEMPLATE_TEST_RUN"]:
            graph = build_resume_processing_graph(llm_runtime, doc_parser, storage, job_repo)
            result = await graph.ainvoke(initial_state)

            if "_failed" in result.get("status", ""):
                error_msg = result.get("validation_errors", ["Unknown AI failure"])[0]
                raise ValueError(f"AI Resume Processing Failed: {error_msg}")

            job.render_docx_uri = result.get("render_docx_uri")
            job.summary_uri = result.get("summary_uri")
            job.error_message = "\n".join(result.get("validation_warnings", [])) if result.get("validation_warnings") else None

        else:
            raise ValueError(f"Unsupported job_type: {job_type}")

        job.status = "COMPLETED"
        job_repo.save_job(job)
        logger.info(f"Worker successfully processed job_id: {job_id} with job_type: {job_type}")

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

async def run_worker():
    logger.info("Starting long-running ECS background worker...")

    # Initialize DB (PostgreSQL RDS in AWS)
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
