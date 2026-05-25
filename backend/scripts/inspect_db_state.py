from app.db.session import SessionLocal
from app.db.models import ProcessingJob, TemplateAsset
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

def inspect():
    db = SessionLocal()
    try:
        # Get the latest jobs
        jobs = db.query(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(5).all()
        print(f"Found {len(jobs)} recent jobs.")
        for job in jobs:
            print(f"\n--- Job {job.id} ({job.job_type}) ---")
            print(f"Status: {job.status}, Stage: {job.stage}")
            print(f"Template Asset ID: {job.template_asset_id}")
            
            if job.template_asset_id:
                template = db.query(TemplateAsset).filter_by(id=job.template_asset_id).first()
                if template:
                    print(f"Template Name: {template.name}")
                    print(f"Template Expected Fields: {template.expected_fields}")
                    print(f"Template Manifest (First 100 chars): {str(template.field_extraction_manifest)[:100]}...")
                else:
                    print("Template record NOT FOUND!")
            
            if job.transformed_json:
                print(f"Transformed JSON (First 100 chars): {str(job.transformed_json)[:100]}...")
            
    finally:
        db.close()

if __name__ == "__main__":
    inspect()
