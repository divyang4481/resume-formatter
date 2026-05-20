def update_job_model():
    with open('backend/app/db/models.py', 'r') as f:
        content = f.read()

    old_job = """    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)"""

    new_job = """    error_message = Column(Text, nullable=True)
    transform_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)"""

    if old_job in content:
        content = content.replace(old_job, new_job)
        with open('backend/app/db/models.py', 'w') as f:
            f.write(content)
        print("Updated ProcessingJob model with transform_json")
    else:
        print("Could not find block in models.py")

update_job_model()
