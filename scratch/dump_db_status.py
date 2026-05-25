import sys
import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), 'backend')))

from app.db.models import TemplateAsset, ProcessingJob

DATABASE_URL = "postgresql://dbadmin:HaysDemo_%23123@agentic-platform-db-dev.ctgoo20ag6cj.ap-south-1.rds.amazonaws.com:5432/agenticdb"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

template_id = "77c01dba-11ae-4298-9d3f-3b401b91a1e5"
template = db.query(TemplateAsset).filter(TemplateAsset.id == template_id).first()

if template:
    print(f"Template Name: {template.name}")
    print(f"Expected Fields: {template.expected_fields}")
    print(f"Manifest: {template.field_extraction_manifest}")
else:
    print(f"Template {template_id} not found.")

# Also check recent jobs
print("\nRecent Jobs:")
jobs = db.query(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(5).all()
for job in jobs:
    print(f"Job ID: {job.id} | Status: {job.status} | Stage: {job.stage}")
    print(f"  Facts JSON: {job.candidate_facts_json[:200] if job.candidate_facts_json else 'EMPTY'}")
    print(f"  Transformed JSON: {job.transformed_json[:200] if job.transformed_json else 'EMPTY'}")

db.close()
