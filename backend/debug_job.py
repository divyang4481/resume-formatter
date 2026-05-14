import asyncio
import json
import logging
from app.db.session import SessionLocal
from app.db.models import ProcessingJob

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DEBUG")

async def debug_job():
    job_id = "b9541d41-d238-4b27-9a18-447be16f6213"
    db = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if job:
            print(f"Status: {job.status}")
            print(f"Payload: {job.payload_json}")
            # print(f"State: {job.state}") # if state exists as a column
        else:
            print("Job not found")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(debug_job())
