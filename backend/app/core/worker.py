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
    template_id = message.get("template_id")

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

        from app.schemas.enums import JobStatus, AssetStatus
        job.status = JobStatus.PROCESSING.value
        job_repo.save_job(job)

        # Fallback for input_uri if not in message
        if not input_uri:
            input_uri = getattr(job, "original_file_ref", None)
            
        if not input_uri:
            raise ValueError(f"No input URI found for job {job_id}")

        if not template_id:
            template_id = getattr(job, "template_asset_id", None)
            if not template_id:
                # In RESUME_FORMATTING, it might be in selected_template_id if it's a domain object, 
                # but job is a DB model here.
                template_id = getattr(job, "template_asset_id", None)

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
                    contract_data = result.get("canonical_model", {})
                    
                    if isinstance(contract_data, dict) and contract_data:
                        # Map all available AI-generated metadata gracefully
                        template.purpose = contract_data.get("purpose") or template.purpose
                        template.expected_sections = contract_data.get("expected_sections") or template.expected_sections
                        template.expected_fields = contract_data.get("expected_fields") or template.expected_fields
                        
                        # Serialize guidance dicts if they are not already strings
                        summary_g = contract_data.get("summary_guidance")
                        if summary_g:
                            template.summary_guidance = json.dumps(summary_g) if isinstance(summary_g, (dict, list)) else summary_g
                        
                        formatting_g = contract_data.get("formatting_guidance")
                        if formatting_g:
                            template.formatting_guidance = json.dumps(formatting_g) if isinstance(formatting_g, (dict, list)) else formatting_g
                        
                        # The manifest itself
                        manifest = contract_data.get("field_extraction_manifest")
                        if manifest:
                            template.field_extraction_manifest = json.dumps(manifest) if isinstance(manifest, (dict, list)) else manifest
                            
                            # Derive expected_fields directly from the manifest's fieldnames
                            if isinstance(manifest, list):
                                extracted_fields = [f.get("fieldname") for f in manifest if isinstance(f, dict) and f.get("fieldname")]
                                if extracted_fields:
                                    template.expected_fields = ",".join(extracted_fields)
                        
                        template.status = AssetStatus.READY_FOR_TESTING.value
                        logger.info(f"Template {template_id} processed successfully. Status: {template.status}")
                        
                        template.status = AssetStatus.READY_FOR_TESTING.value
                        logger.info(f"Template {template_id} processed successfully. Status: {template.status}")
                    else:
                        template.status = AssetStatus.FAILED.value
                        logger.warning(f"Template {template_id} processing failed: No useful metadata extracted.")
                        template.field_extraction_manifest = json.dumps([])
                    db.commit()

                # Update job status
                job.status = JobStatus.COMPLETED.value
                job_repo.save_job(job)
                logger.info(f"Worker successfully processed job_id: {job_id} with job_type: {job_type}")

        elif job_type == "RESUME_FORMATTING":
            graph = build_resume_processing_graph(llm_runtime, doc_parser, storage, job_repo)
            # template_id from message or job record
            final_template_id = template_id or message.get("template_id")
            
            # Prepare initial state with the selected template ID
            state_input = {**initial_state}
            if final_template_id:
                state_input["selected_template_id"] = final_template_id
            
            result = await graph.ainvoke(state_input)
            job.status = JobStatus.COMPLETED.value
            job_repo.save_job(job)
            if "_failed" in result.get("status", ""):
                error_msg = result.get("validation_errors", ["Unknown AI failure"])[0]
                raise ValueError(f"AI Resume Processing Failed: {error_msg}")

            job.render_docx_uri = result.get("render_docx_uri")
            job.summary_uri = result.get("summary_uri")
            job.error_message = "\n".join(result.get("validation_warnings", [])) if result.get("validation_warnings") else None

        else:
            raise ValueError(f"Unsupported job_type: {job_type}")

        job.status = JobStatus.COMPLETED.value
        job_repo.save_job(job)
        logger.info(f"Worker successfully processed job_id: {job_id} with job_type: {job_type}")

    except Exception as e:
        logger.error(f"Worker failed processing job_id: {job_id} with error: {e}", exc_info=True)
        try:
            job = job_repo.get_job(job_id)
            if job:
                job.status = JobStatus.FAILED.value
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
            logger.info("Worker polling for jobs...")
            for message in queue.consume():
                logger.info(f"--- WORKER RECEIVED MESSAGE: {message['message_id']} ---")
                logger.info(f"Message Body: {message['body']}")
                
                body = message['body']
                job_id = body.get('job_id')
                job_type = body.get('job_type')
                
                logger.info(f"Starting processing for Job {job_id} ({job_type})...")
                await process_job(db, body)
                
                queue.ack(message)
                logger.info(f"Successfully processed and Acknowledged message: {message['message_id']}")

            # Sleep briefly if queue is empty
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Worker encountered a critical error: {e}", exc_info=True)
            await asyncio.sleep(5)
        finally:
            db.close()

if __name__ == "__main__":
    asyncio.run(run_worker())
