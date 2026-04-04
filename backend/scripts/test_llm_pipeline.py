import asyncio
import os
import sys
import json
import logging
from datetime import datetime

# Set up simple logging for the script
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("test_pipeline")

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.db.models import TemplateAsset
from app.dependencies import get_llm_runtime, get_document_extraction_service, get_storage_provider
from app.services.resume_ai_service import ResumeAiService
from app.services.resume_generator_service import ResumeGeneratorService
from app.agent.nodes.transformation_node import create_schema_builder_node, create_context_aware_extraction_node
from app.domain.interfaces import ExtractionContext

async def run_simple_test(resume_path: str, template_id: str):
    logger.info(f"Starting End-to-End LLM Pipeline Validation...")
    logger.info(f"Target Template: {template_id}")
    logger.info(f"Target Resume: {resume_path}")
    
    if not os.path.exists(resume_path):
        logger.error(f"Resume file not found at: {resume_path}")
        return

    llm = get_llm_runtime()
    extractor = get_document_extraction_service()
    storage = get_storage_provider()
    ai_service = ResumeAiService(llm, extractor)
    generator = ResumeGeneratorService()
    
    db = SessionLocal()
    try:
        # STEP 1: LOAD TEMPLATE & ASSET
        template_asset = db.query(TemplateAsset).filter(TemplateAsset.id == template_id).first()
        if not template_asset:
            logger.error(f"Template {template_id} not found in database.")
            return

        logger.info(f"Matched Template Asset: {template_asset.name}")

        # STEP 2: EXTRACT DATA FROM RESUME
        with open(resume_path, "rb") as f:
            resume_content = f.read()
        
        # PROVIDE REQUIRED EXTRACTION CONTEXT
        context = ExtractionContext(intent="test_run", actor_role="admin")
        
        parsed_doc = await extractor.extract(
            file_bytes=resume_content, 
            filename=os.path.basename(resume_path), 
            content_type="application/pdf",
            context=context
        )
        
        # Build state for the graph nodes
        state = {
            "extracted_text": parsed_doc.extracted_text,
            "raw_parsed_data": {"sections": []}, # Simplified for test
            "expected_fields": template_asset.expected_fields or "",
            "expected_sections": template_asset.expected_sections or "",
            "field_extraction_manifest": json.loads(template_asset.field_extraction_manifest) if template_asset.field_extraction_manifest else [],
            "template_text": "Sample Template Context Content Placeholder",
        }

        # Use our actual node logic
        builder = create_schema_builder_node()
        builder_result = await builder(state)
        state.update(builder_result)
        
        transformer = create_context_aware_extraction_node(llm)
        transform_result = await transformer(state)
        
        if transform_result.get("status") == "extraction_error":
            logger.error("Extraction Node failed during transformation.")
            return

        final_json = transform_result.get("transformed_document_json")
        logger.info(f"Extracted JSON Snippet: {final_json[:500]}...")

        # STEP 3: GENERATE DOCUMENT
        logger.info(f"[STEP 3] Generating final document for Template: {template_id}")
        
        resume_data = json.loads(final_json)
        # Force a fresh summary using our latest prompt logic
        resume_data["summary"] = await ai_service.generate_summary(
            parsed_doc.extracted_text, 
            guidance=template_asset.summary_guidance or "Professional Executive Summary"
        )

        template_storage_key = template_asset.storage_uri.replace("local://", "")
        template_bytes = storage.get_bytes(template_storage_key)
        
        output_data = generator.render_formatted_document(
            template_bytes=template_bytes, 
            resume_data=resume_data,
            expected_fields=template_asset.expected_fields,
            field_extraction_manifest=state.get("field_extraction_manifest")
        )
        
        output_filename = f"repaired_resume_{datetime.now().strftime('%H%M%S')}.docx"
        with open(output_filename, "wb") as out:
            out.write(output_data)
            
        logger.info(f"SUCCESS: End-to-End Test finished perfectly.")
        logger.info(f"Final Repaired Resume saved to: {os.path.abspath(output_filename)}")

    except Exception as e:
        logger.error(f"Global Test Failure: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    # Allow command line arguments
    # Usage: python scripts/test_llm_pipeline.py <resume_path> [template_id]
    
    # Default verified values if no args provided
    default_resume = r"c:\workspace\CTS\Hays_Resume_formater\Code\resume-formatter\backend\data\templates\87e92d50-a42d-427c-8f9c-6f8a15ad70b8\tests\00a15fcd-dac8-41dd-8a9a-1c14fbd06ce8\input\Divyang_Panchasara-2026.pdf"
    default_template = "87e92d50-a42d-427c-8f9c-6f8a15ad70b8"
    
    target_resume = sys.argv[1] if len(sys.argv) > 1 else default_resume
    target_template = sys.argv[2] if len(sys.argv) > 2 else default_template
    
    asyncio.run(run_simple_test(target_resume, target_template))
