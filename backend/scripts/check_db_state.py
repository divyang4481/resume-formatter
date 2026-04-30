import os
import sys
import json
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add backend to path to import models using relative paths
script_path = Path(__file__).resolve()
backend_path = script_path.parent.parent
sys.path.insert(0, str(backend_path))

# Load .env.local from the backend directory
load_dotenv(backend_path / ".env.local")

from app.db.models import ProcessingJob, LocalQueueMessage
from app.config import Settings

def check_db():
    # Force reload settings with loaded env vars
    settings = Settings()
    
    if not settings.database_url:
        settings.database_url = os.getenv('DATABASE_URL')

    if not settings.database_url:
        print("Error: DATABASE_URL is not set.")
        return

    print(f"Connecting to: {settings.database_url}")
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("\n--- Recent Processing Jobs ---")
    jobs = session.query(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(10).all()
    if not jobs:
        print("No jobs found.")
    for job in jobs:
        print(f"ID: {job.id}, Status: {job.status}, Stage: {job.stage}, Created: {job.created_at}")

    print("\n--- Recent Queue Messages ---")
    messages = session.query(LocalQueueMessage).order_by(LocalQueueMessage.created_at.desc()).limit(10).all()
    if not messages:
        print("No queue messages found.")
    for msg in messages:
        print(f"ID: {msg.id}, Queue: {msg.queue_name}, Status: {msg.status}, Created: {msg.created_at}, Processed: {msg.processed_at}")
        try:
            payload = json.loads(msg.payload_json)
            print(f"  Payload Job ID: {payload.get('job_id')}")
        except:
            print("  Payload: [Invalid JSON]")

    print("\n--- Current Processing Messages ---")
    stuck = session.query(LocalQueueMessage).filter(LocalQueueMessage.status == "processing").all()
    if not stuck:
        print("No messages currently being processed.")
    for msg in stuck:
        print(f"ID: {msg.id}, Queue: {msg.queue_name}, Status: {msg.status}, Created: {msg.created_at}, Processed: {msg.processed_at}")

    session.close()

if __name__ == "__main__":
    check_db()
