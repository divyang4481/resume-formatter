import os
import subprocess
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
S3_BUCKET = os.getenv("S3_BUCKET_INPUT")

def clean_database():
    print(f"Cleaning database at {DATABASE_URL.split('@')[-1]}...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # List of tables to truncate
        tables = [
            "template_test_runs",
            "audit_events",
            "local_queue_messages",
            "template_knowledge_bindings",
            "knowledge_packs",
            "knowledge_assets",
            "validation_results",
            "processing_jobs",
            "candidate_resumes",
            "template_rules",
            "template_assets"
        ]
        
        # Build truncate command
        truncate_query = f"TRUNCATE TABLE {', '.join(tables)} CASCADE;"
        cur.execute(truncate_query)
        conn.commit()
        print("Database tables truncated successfully.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error cleaning database: {e}")

def clean_s3():
    if not S3_BUCKET:
        print("S3_BUCKET_INPUT not found in .env. Skipping S3 cleanup.")
        return
        
    print(f"Cleaning S3 bucket: {S3_BUCKET}...")
    try:
        # Using AWS CLI for speed and simplicity
        cmd = ["aws", "s3", "rm", f"s3://{S3_BUCKET}", "--recursive"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("S3 bucket emptied successfully.")
        else:
            print(f"Error cleaning S3: {result.stderr}")
    except Exception as e:
        print(f"Error executing AWS CLI: {e}")

if __name__ == "__main__":
    confirm = input("WARNING: This will delete ALL data in the database and S3 bucket. Type 'RESET' to confirm: ")
    if confirm == "RESET":
        clean_database()
        clean_s3()
        print("\nEnvironment cleanup complete. You can now start fresh.")
    else:
        print("Cleanup cancelled.")
