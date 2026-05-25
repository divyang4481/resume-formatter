import json
with open(r'scratch\latest_job_data.json', 'r', encoding='utf-8') as f:
    job_data = json.load(f)

manifest = job_data.get('template_manifest', {})
if 'fields' not in manifest and 'template_manifest' in job_data.get('job', {}):
    manifest = job_data['job']['template_manifest']

if 'fields' in manifest:
    for f in manifest['fields']:
        fn = f.get('fieldname') or f.get('canonical_fieldname')
        if fn in ('core_technical_skills', 'skills', 'work_experience'):
            print(f"Field: {fn}")
            print(json.dumps(f.get('render_locator', {}), indent=2))
