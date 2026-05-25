import sys
import os
sys.path.append(os.path.abspath('.'))
import json
from app.core.database import SessionLocal
from app.models.job import ProcessJob

db = SessionLocal()
job = db.query(ProcessJob).filter(ProcessJob.id == '68dab7c4-9acf-4d26-af5b-679553c10d9').first()

if job:
    manifest = job.template_manifest
    if 'fields' in manifest:
        for f in manifest['fields']:
            fn = f.get('fieldname') or f.get('canonical_fieldname')
            if fn in ('core_technical_skills', 'skills', 'work_experience'):
                print(f"Field: {fn}")
                print(json.dumps(f.get('render_locator', {}), indent=2))
else:
    print("Job not found!")
