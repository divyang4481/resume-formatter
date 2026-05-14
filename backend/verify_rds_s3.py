import os
import asyncio
import logging
import json
import boto3
from app.services.resume_generator_service import ResumeGeneratorService
from app.db.session import SessionLocal
from app.db.models import ProcessingJob, TemplateAsset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VERIFY")

async def verify():
    job_id = "b9541d41-d238-4b27-9a18-447be16f6213"
    logger.info(f"Verifying job {job_id} using RDS and S3...")
    
    db = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            logger.error("Job not found in RDS")
            return
        
        logger.info(f"Job found: {job.status}. Template ID: {job.template_asset_id}")
        
        # 1. Load template from S3
        uri = job.render_docx_uri or ""
        # If it's a completed job, maybe it already has a render_docx_uri? 
        # No, we want the ORIGINAL template.
        template = db.query(TemplateAsset).filter(TemplateAsset.id == job.template_asset_id).first()
        if not template:
            logger.error("Template metadata not found in RDS")
            return
            
        logger.info(f"Loading template from S3 URI: {template.storage_uri}")
        
        # Use boto3 directly to avoid complexity
        s3 = boto3.client('s3')
        uri = template.storage_uri
        if uri.startswith("s3://"):
            parts = uri[5:].split("/", 1)
            bucket = parts[0]
            key = parts[1]
        else:
            from app.config import settings
            bucket = os.environ.get("S3_BUCKET_INPUT") or settings.s3_bucket_input
            key = uri

        response = s3.get_object(Bucket=bucket, Key=key)
        template_bytes = response['Body'].read()
        
        # 2. Render
        generator = ResumeGeneratorService()
        data = {}
        if job.transformed_json:
            try:
                data = json.loads(job.transformed_json)
            except:
                logger.error("Failed to parse transformed_json")
        
        manifest = []
        if template.analysis_json:
            try:
                analysis = json.loads(template.analysis_json)
                manifest = analysis.get("field_manifest", [])
            except:
                logger.error("Failed to parse analysis_json")

        docx_bytes, missing = generator.render_formatted_document(
            template_bytes=template_bytes,
            resume_data=data,
            expected_fields=template.expected_fields or "",
            field_manifest=manifest
        )
        
        # 3. Save locally for inspection
        output_file = "/app/verified_resume_rds.docx"
        with open(output_file, "wb") as f:
            f.write(docx_bytes)
            
        logger.info(f"SUCCESS: Rendered docx saved to {output_file}")
        logger.info(f"Missing fields: {missing}")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify())
