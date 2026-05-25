import psycopg2, json, os

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
job_id = '68dab7c4-9acf-4d26-af5b-679553c10d9'

cur.execute(f"SELECT template_asset_id FROM processing_jobs WHERE id = '{job_id}'")
res = cur.fetchone()
template_id = None
if res and res[0]:
    template_id = res[0]
else:
    cur.execute(f"SELECT template_id FROM template_test_runs WHERE id = '{job_id}'")
    res = cur.fetchone()
    if res and res[0]:
        template_id = res[0]
    else:
        # maybe processing_job_id
        cur.execute(f"SELECT template_id FROM template_test_runs WHERE processing_job_id = '{job_id}'")
        res = cur.fetchone()
        if res and res[0]:
            template_id = res[0]

if not template_id:
    # Just try to get the manifest for the template the user mentioned: f12b7dfe-97f6-425c-8721-eb119c009c1f
    template_id = 'f12b7dfe-97f6-425c-8721-eb119c009c1f'

print(f"Using template_id: {template_id}")
cur.execute(f"SELECT field_extraction_manifest FROM template_assets WHERE id = '{template_id}'")
asset_res = cur.fetchone()
if asset_res and asset_res[0]:
    manifest = json.loads(asset_res[0]) if isinstance(asset_res[0], str) else asset_res[0]
    for f in manifest.get('fields', []):
        fn = f.get('fieldname') or f.get('canonical_fieldname')
        if fn in ('core_technical_skills', 'skills', 'work_experience'):
            print(f"Field: {fn}")
            print(json.dumps(f.get('render_locator', {}), indent=2))
    print("Done.")
else:
    print("No manifest found on template.")
