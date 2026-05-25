import sys
import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), 'backend')))

from app.db.models import TemplateAsset

DATABASE_URL = "postgresql://dbadmin:HaysDemo_%23123@agentic-platform-db-dev.ctgoo20ag6cj.ap-south-1.rds.amazonaws.com:5432/agenticdb"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

template_id = "77c01dba-11ae-4298-9d3f-3b401b91a1e5"
template = db.query(TemplateAsset).filter(TemplateAsset.id == template_id).first()

if template:
    print(f"Template Name: {template.name}")
    manifest = json.loads(template.field_extraction_manifest)
    print("\nManifest Fields:")
    for f in manifest:
        print(f"  Field: {f['fieldname']} | Marker: {f.get('marker_text')} | Strategy: {f['render_locator']['strategy']}")
else:
    print(f"Template {template_id} not found.")

db.close()
