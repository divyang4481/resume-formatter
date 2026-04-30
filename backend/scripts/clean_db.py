import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

script_path = Path(__file__).resolve()
backend_path = script_path.parent.parent
sys.path.insert(0, str(backend_path))
load_dotenv(backend_path / ".env.local")

from app.config import Settings


def clean_db():
    settings = Settings()
    url = settings.database_url or os.getenv("DATABASE_URL")
    if not url:
        print("Error: DATABASE_URL not set.")
        return

    print(f"Cleaning database: {url}")
    engine = create_engine(url)

    # List of tables to clean in order (or use CASCADE)
    tables = [
        "local_queue_messages",
        "processing_jobs",
        "candidate_resumes",
        "template_test_runs",
        "audit_events",
        "validation_results",
        "template_rules",
        "template_knowledge_bindings",
        "template_assets",
        # We might want to keep template_assets and knowledge_packs/assets if they are seeds
    ]

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            for table in tables:
                print(f"Truncating {table}...")
                conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            transaction.commit()
            print("Successfully cleaned database.")
        except Exception as e:
            transaction.rollback()
            print(f"Failed to clean database: {e}")


if __name__ == "__main__":
    clean_db()
