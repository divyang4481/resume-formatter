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
                candidate_resume_id=job.candidate_resume_id if hasattr(job, 'candidate_resume_id') else f"resume-{job.id}",
                status=job.status.value if hasattr(job.status, 'value') else job.status,
                stage="INITIAL"
            )
            self.db.add(model)
        else:
            model.status = job.status.value if hasattr(job.status, 'value') else job.status

        self.db.commit()
        return model.id
