from app.domain.interfaces import JobRepository
from typing import Any, Dict

class InMemoryJobRepository(JobRepository):
    def __init__(self):
        self.jobs: Dict[str, Any] = {}

    def get_job(self, job_id: str) -> Any:
        return self.jobs.get(job_id)

    def save_job(self, job: Any) -> str:
        job_id = job.id
        self.jobs[job_id] = job
        return job_id
