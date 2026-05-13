import sys
import os

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import SessionLocal
from app.db.models import TemplateAsset, ProcessingJob, TemplateTestRun, CandidateResume, ValidationResult

def clean_all():
    db = SessionLocal()
    try:
        print("Cleaning template and job related tables...")
        
        # Order matters for foreign keys
        db.query(TemplateTestRun).delete()
        db.query(ValidationResult).delete()
        db.query(ProcessingJob).delete()
        db.query(CandidateResume).delete()
        db.query(TemplateAsset).delete()
        
        db.commit()
        print("Database cleaned successfully.")
    except Exception as e:
        db.rollback()
        print(f"Failed to clean database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clean_all()
