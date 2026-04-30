from typing import Any
from sqlalchemy.orm import Session
from app.domain.interfaces import JobRepository
from app.db.models import ProcessingJob as ProcessingJobModel

class SqlAlchemyJobRepository(JobRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_job(self, job_id: str) -> Any:
        # Simplistic implementation returning the DB model
        return self.db.query(ProcessingJobModel).filter(ProcessingJobModel.id == job_id).first()

    def save_job(self, job: Any) -> str:
        from app.db.models import CandidateResume as CandidateResumeModel
        import logging
        logger = logging.getLogger(__name__)

        try:
            # 1. Resolve and ensure CandidateResume exists
            # Use job.candidate_id if provided, otherwise fallback to a deterministic ID
            candidate_id = getattr(job, 'candidate_id', None) or f"resume-{job.id}"
            
            logger.info(f"--- [DB] Saving job {job.id} for candidate {candidate_id} ---")
            
            candidate = self.db.query(CandidateResumeModel).filter(CandidateResumeModel.id == candidate_id).first()
            if not candidate:
                logger.info(f"--- [DB] Creating new candidate record: {candidate_id} ---")
                candidate = CandidateResumeModel(
                    id=candidate_id,
                    source_file_name=job.extension_metadata.get("filename", "unknown") if hasattr(job, 'extension_metadata') else "unknown",
                    source_storage_uri=job.original_file_ref if hasattr(job, 'original_file_ref') else "unknown"
                )
                self.db.add(candidate)
                self.db.flush() # Force insert to satisfy foreign key in next step
            
            # 2. Handle ProcessingJob
            model = self.db.query(ProcessingJobModel).filter(ProcessingJobModel.id == job.id).first()
            if not model:
                logger.info(f"--- [DB] Creating new processing job record: {job.id} ---")
                model = ProcessingJobModel(
                    id=job.id,
                    candidate_resume_id=candidate_id,
                    original_file_ref=job.original_file_ref if hasattr(job, 'original_file_ref') else None,
                    status=job.status.value if hasattr(job.status, 'value') else job.status,
                    stage="INITIAL"
                )
                self.db.add(model)
            else:
                logger.info(f"--- [DB] Updating existing job record: {job.id} ---")
                model.status = job.status.value if hasattr(job.status, 'value') else job.status

            # Map additional fields safely
            if hasattr(job, 'summary_uri'): model.summary_uri = job.summary_uri
            if hasattr(job, 'generated_summary'): model.generated_summary = job.generated_summary
            if hasattr(job, 'render_docx_uri'): model.render_docx_uri = job.render_docx_uri
            if hasattr(job, 'error_message'): model.error_message = job.error_message
            
            # Validate template ID existence if provided to prevent FK violation
            if hasattr(job, 'selected_template_id') and job.selected_template_id:
                from app.db.models import TemplateAsset
                template_exists = self.db.query(TemplateAsset).filter(TemplateAsset.id == job.selected_template_id).first()
                if template_exists:
                    model.template_asset_id = job.selected_template_id
                else:
                    logger.warning(f"--- [DB] Template {job.selected_template_id} not found. Setting job template to NULL. ---")
                    model.template_asset_id = None

            if hasattr(job, 'extension_metadata'):
                setattr(model, 'extension_metadata', job.extension_metadata)

            self.db.commit()
            logger.info(f"--- [DB] Successfully saved job {job.id} ---")
            return model.id
            
        except Exception as e:
            logger.error(f"--- [DB ERROR] Failed to save job {job.id}: {str(e)} ---")
            self.db.rollback()
            raise e
