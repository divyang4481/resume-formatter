import asyncio
import logging
from app.db.session import SessionLocal
from app.db.models import ProcessingJob

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LIST")

async def list_jobs():
    db = SessionLocal()
    try:
        jobs = db.query(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(5).all()
        for j in jobs:
            print(f"ID: {j.id} | Status: {j.status} | Created: {j.created_at}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(list_jobs())
