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
        model = self.db.query(ProcessingJobModel).filter(ProcessingJobModel.id == job.id).first()
        if not model:
            model = ProcessingJobModel(
                id=job.id,
                candidate_resume_id=job.candidate_id if hasattr(job, 'candidate_id') and job.candidate_id else f"resume-{job.id}",
                original_file_ref=job.original_file_ref if hasattr(job, 'original_file_ref') else None,
                status=job.status.value if hasattr(job.status, 'value') else job.status,
                stage="INITIAL"
            )
            self.db.add(model)
        else:
            model.status = job.status.value if hasattr(job.status, 'value') else job.status

        # Map additional fields that might be updated by the graph workflow
        if hasattr(job, 'summary_uri'):
            model.summary_uri = job.summary_uri
        if hasattr(job, 'generated_summary'):
            model.generated_summary = job.generated_summary
        if hasattr(job, 'render_docx_uri'):
            model.render_docx_uri = job.render_docx_uri
        if hasattr(job, 'error_message'):
            model.error_message = job.error_message
        if hasattr(job, 'selected_template_id'):
            model.template_asset_id = job.selected_template_id
        if hasattr(job, 'extraction_quality_score'):
            model.extraction_quality_score = job.extraction_quality_score
        if hasattr(job, 'missing_fields'):
            import json
            model.missing_fields = json.dumps(job.missing_fields) if job.missing_fields is not None else None

        self.db.commit()
        return model.id
