import os
from supabase import create_client

supabase_url = os.environ.get("SUPABASE_URL", "http://supabase:8000")
supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN5c3RlbSIsInJvbGUiOiJzZXJ2aWNlX3JvbGUiLCJpYXQiOjE3MDU2OTkzODAsImV4cCI6MjAyMTI3NTM4MH0.xxx")

try:
    client = create_client(supabase_url, supabase_key)
    response = client.table("jobs").select("*").eq("id", "1c22b543-e1e2-4ed9-a722-767645736d2c").execute()
    if response.data:
        job = response.data[0]
        # print the skills and work_experience keys from result_data
        result_data = job.get("result_data", {})
        print("Skills mapping:", result_data.get("template_fill_result", {}).get("skills"))
        print("Work experience mapping:", result_data.get("template_fill_result", {}).get("work_experience"))
        
        manifest = job.get("result_data", {}).get("filled_template_manifest", {})
        for field in manifest.get("fields", []):
            if field.get("fieldname") in ["skills", "work_experience"]:
                print(f"Manifest Field: {field.get('fieldname')}")
                print(f"Locator: {field.get('render_locator')}")
    else:
        print("Job not found.")
except Exception as e:
    print("Error:", e)
