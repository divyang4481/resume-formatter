import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load env from root
load_dotenv('.env')

db_url = os.getenv('DATABASE_URL')
if not db_url:
    print("DATABASE_URL not found in .env")
    exit(1)

engine = create_engine(db_url)

query = text("""
    SELECT id, name, expected_fields, field_extraction_manifest 
    FROM template_assets 
    LIMIT 5;
""")

try:
    with engine.connect() as conn:
        result = conn.execute(query)
        print(f"{'ID':<40} | {'Name':<30} | {'Expected Fields'}")
        print("-" * 100)
        for row in result:
            fields = row[2] or "EMPTY"
            manifest = "PRESENT" if row[3] else "MISSING"
            print(f"{str(row[0]):<40} | {str(row[1]):<30} | {fields[:50]}... (Manifest: {manifest})")
except Exception as e:
    print(f"Error querying database: {e}")
