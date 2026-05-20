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
            from app.dependencies import get_template_analysis_service
            analysis_service = get_template_analysis_service()
            
            # Update Stage
            job.stage = "ANALYZING_TEMPLATE"
            job_repo.save_job(job)

            # Fetch raw DOCX from storage
            template_bytes = storage.get_bytes(input_uri)
            
            # Run Production Analysis
            analysis = await analysis_service.analyze_template_asset(template_bytes, template_id)
            
            # Update Stage
            job.stage = "PERSISTING_ANALYSIS"
            job_repo.save_job(job)

            # Persist to DB
            from app.db.models import TemplateAsset
            template = db.query(TemplateAsset).filter_by(id=template_id).first()
            if template:
                template.analysis_json = analysis.model_dump_json()
                template.status = AssetStatus.READY_FOR_TESTING.value
                
                # Synchronize URIs with ProcessingJob (User Rule: storage_uri == original_file_ref)
                if not template.storage_uri:
                    template.storage_uri = input_uri
                
                # extraction_uri can be the same as storage_uri or a specific analysis artifact
                # For now, we align it to show that analysis has been completed for this storage ref
                if not template.extraction_uri:
                    template.extraction_uri = input_uri

                # Enrich TemplateAsset columns from analysis
                template.purpose = analysis.purpose
                template.summary_guidance = analysis.summary_guidance
                template.formatting_guidance = analysis.formatting_guidance
                template.validation_guidance = analysis.validation_guidance
                template.pii_guidance = analysis.pii_guidance
                template.expected_sections = ",".join(analysis.expected_sections)

                # Backward compatibility for legacy UI and existing rendering components
                all_fields = list(analysis.fields)
                for s in analysis.sections: all_fields.extend(s.fields)
                
                template.expected_fields = ",".join([f.field_name for f in all_fields])
                
                # Convert new TemplateField objects to legacy manifest format
                legacy_manifest = []
                for f in all_fields:
                    legacy_manifest.append({
                        "fieldname": f.field_name,
                        "field_type": f.field_type,
                        "meaning": f.meaning,
                        "source_hints": f.source_hints,
                        "marker_text": f.marker_text,
                        "render_locator": f.render_locator.model_dump()
                    })
                
                # Save as a rich dict containing fields and instruction_blocks for robust downstream rendering
                rich_manifest = {
                    "fields": legacy_manifest,
                    "instruction_blocks": [ib.text for ib in getattr(analysis, "instruction_blocks", []) if hasattr(ib, "text")]
                }
                template.field_extraction_manifest = json.dumps(rich_manifest)
                
                db.commit()
                logger.info(f"[Worker] Template {template_id} analyzed and persisted.")

        elif job_type in ("RESUME_FORMATTING", "TEMPLATE_TEST_RUN"):
            from app.services.resume_workflow_service import ResumeWorkflowService
            from app.adapters.repositories.template_repository import SqlAlchemyTemplateRepository
            
            # Use centralized workflow service to ensure LangGraph agents are used
            workflow_service = ResumeWorkflowService(
                llm=llm_runtime,
                parser_service=doc_parser,
                job_repo=job_repo,
                template_repo=SqlAlchemyTemplateRepository(db),
                storage=storage
            )
            
            logger.info(f"[Worker] Handing off job {job_id} to Agentic Workflow Service...")
            await workflow_service.execute_job(job_id)
            logger.info(f"[Worker] Agentic Workflow Service completed for job {job_id}")

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
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Worker database initialized.")
    except Exception as e:
        logger.info(f"Worker database initialization warning: {e}. Another worker might have completed this.")

    while True:
        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            pass
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
