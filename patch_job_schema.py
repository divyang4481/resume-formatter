def update_job_schema():
    with open('backend/app/schemas/job.py', 'r') as f:
        content = f.read()

    old_job = """    # Generated Outputs
    summary_uri: Optional[str] = None
    render_docx_uri: Optional[str] = None"""

    new_job = """    # Generated Outputs
    summary_uri: Optional[str] = None
    render_docx_uri: Optional[str] = None
    transform_json: Optional[str] = None"""

    if old_job in content:
        content = content.replace(old_job, new_job)
        with open('backend/app/schemas/job.py', 'w') as f:
            f.write(content)
        print("Updated ProcessingJob schema with transform_json")
    else:
        print("Could not find block in schemas/job.py")

update_job_schema()
