def update_job_repo():
    with open('backend/app/adapters/repositories/job_repository.py', 'r') as f:
        content = f.read()

    old_map = """        if hasattr(job, 'selected_template_id'):
            model.template_asset_id = job.selected_template_id"""

    new_map = """        if hasattr(job, 'selected_template_id'):
            model.template_asset_id = job.selected_template_id
        if hasattr(job, 'transform_json'):
            model.transform_json = job.transform_json"""

    if old_map in content:
        content = content.replace(old_map, new_map)
        with open('backend/app/adapters/repositories/job_repository.py', 'w') as f:
            f.write(content)
        print("Updated job repository with transform_json")
    else:
        print("Could not find block in job_repository.py")

update_job_repo()
