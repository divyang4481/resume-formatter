import asyncio
import os
import sys
from typing import Optional

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.dependencies import (
    get_storage_provider,
    get_template_repository,
    get_message_queue,
    get_document_extraction_service,
    get_llm_runtime
)
from app.services.template_service import TemplateService
from app.services.resume_ai_service import ResumeAiService
from app.services.template_analysis_service import TemplateAnalysisService
from app.schemas.admin import AssetUploadRequestMetadata

TEMPLATE_DIR = r"C:\workspace\CCCTTNS\Hays_Resume_formater\real_template"

async def reprocess_templates():
    from app.db.session import SessionLocal
    from app.dependencies import (
        get_storage_provider,
        get_template_repository,
        get_message_queue,
        get_document_extraction_service,
        get_llm_runtime,
        get_template_analysis_service
    )
    
    db = SessionLocal()
    storage = get_storage_provider()
    repo = get_template_repository(db)
    queue = get_message_queue()
    extractor = get_document_extraction_service()
    llm = get_llm_runtime()
    analysis_service = get_template_analysis_service()
    
    tpl_service = TemplateService(
        storage_provider=storage,
        template_repository=repo,
        event_bus=queue,
        extraction_service=extractor,
        template_analysis_service=analysis_service
    )

    if not os.path.exists(TEMPLATE_DIR):
        print(f"Template directory not found: {TEMPLATE_DIR}")
        return

    files = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith(".docx")]
    print(f"Found {len(files)} templates to process.")

    for filename in files:
        file_path = os.path.join(TEMPLATE_DIR, filename)
        print(f"\nProcessing {filename}...")
        
        with open(file_path, "rb") as f:
            content = f.read()
            
        metadata = AssetUploadRequestMetadata(
            name=filename.replace(".docx", ""),
            industry="it", # Default, will be refined by AI purpose
            asset_type="template_docx",
            version="1.0.0"
        )
        
        try:
            asset_id = await tpl_service.upload_asset(
                filename=filename,
                content=content,
                metadata=metadata,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                uploaded_by="system-rebuild"
            )
            print(f"Successfully processed {filename}. Asset ID: {asset_id}")
        except Exception as e:
            print(f"Failed to process {filename}: {e}")

if __name__ == "__main__":
    asyncio.run(reprocess_templates())
