import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# URL-encoded DB connection string from .env
db_url = "postgresql://dbadmin:HaysDemo_%23123@agentic-platform-db-dev.ctgoo20ag6cj.ap-south-1.rds.amazonaws.com:5432/agenticdb"

engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

job_id = "e8279bbd-b648-4198-8c99-078a30a6f4ee"
result = session.execute(text(f"SELECT * FROM processing_jobs WHERE id = '{job_id}'")).fetchone()

if result:
    print(f"Job ID: {result.id}")
    print(f"Status: {result.status}")
    print(f"Error Message: {result.error_message}")
    print(f"Validation Report: {getattr(result, 'validation_report', 'N/A')}")
    print(f"Extension Metadata: {result.extension_metadata}")
else:
    print("Job not found.")

session.close()
