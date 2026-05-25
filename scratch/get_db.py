import psycopg2
import json

conn = psycopg2.connect("postgresql://dbadmin:HaysDemo_%23123@agentic-platform-db-dev.ctgoo20ag6cj.ap-south-1.rds.amazonaws.com:5432/agenticdb")
cur = conn.cursor()
cur.execute("SELECT template_manifest FROM processing_jobs WHERE id = '68dab7c4-9acf-4d26-af5b-679553c10d9'")
res = cur.fetchone()
if res:
    manifest = res[0]
    if isinstance(manifest, str):
        manifest = json.loads(manifest)
    
    for f in manifest.get('fields', []):
        fn = f.get('fieldname') or f.get('canonical_fieldname')
        if fn in ('core_technical_skills', 'skills', 'work_experience'):
            print(f"Field: {fn}")
            print(json.dumps(f.get('render_locator', {}), indent=2))
