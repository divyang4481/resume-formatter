import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json

load_dotenv('.env')

db_url = os.getenv('DATABASE_URL')
engine = create_engine(db_url)

query = text("""
    SELECT id, name, field_extraction_manifest 
    FROM template_assets 
    WHERE name = 'UK Telecoms.docx' OR name LIKE 'UK Telecoms%';
""")

with engine.connect() as conn:
    result = conn.execute(query)
    for row in result:
        print(f"ID: {row[0]}")
        print(f"Name: {row[1]}")
        manifest = json.loads(row[2]) if row[2] else []
        print("Manifest:")
        print(json.dumps(manifest, indent=2))
        print("-" * 50)
