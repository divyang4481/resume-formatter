import asyncio
import json
import re
from app.agent.state import AgentState
from app.domain.interfaces import LlmRuntimeAdapter
from app.db.session import SessionLocal
from app.adapters.repositories.template_repository import SqlAlchemyTemplateRepository
from app.services.template_resolution_service import TemplateResolutionService
from app.services.resume_ai_service import ResumeAiService
from app.domain.interfaces import LlmRuntimeAdapter

def create_template_resolve_node(llm_runtime, storage_provider, doc_parser):
    """
    Creates the LangGraph node for resolving the appropriate template based on the
    document content or user request.
    """
    async def template_resolve_node(state: AgentState) -> dict:
        print("Executing Template Resolution Node...")
        
        from app.domain.interfaces import ExtractionContext
        
        extracted_text = state.get("extracted_text", "")
        chosen_template_id = state.get("selected_template_id")
        storage_uri = state.get("template_storage_uri")
        summary_guidance = None
        formatting_guidance = None
        validation_guidance = None
        pii_guidance = None
        expected_sections = None
        expected_fields = None
        field_manifest = None
        template_text = ""

        db = SessionLocal()
        try:
            repo = SqlAlchemyTemplateRepository(db)
            
            # Phase 1: Identify Template
            if not chosen_template_id:
                resolution_service = TemplateResolutionService(llm_runtime, repo)
                result = await resolution_service.recommend_template(
                    extracted_text=extracted_text,
                    mode=state.get("intent", "recruiter_runtime")
                )
                chosen_template_id = result.suggested_template_id
                
                if not chosen_template_id:
                    first_tpl = repo.list_active_templates()
                    if first_tpl:
                        chosen_template_id = first_tpl[0].id
                    else:
                        raise ValueError("No active templates found in RDS. Template resolution failed.")
                
                print(f"Resolved Template ID: {chosen_template_id}")

            # Phase 2: Load Metadata
            template_meta = repo.get_template(chosen_template_id)
            if not template_meta:
                raise ValueError(f"Template with ID {chosen_template_id} not found in database.")

            storage_uri = template_meta.original_file_ref
            summary_guidance = template_meta.summary_guidance
            formatting_guidance = template_meta.formatting_guidance
            validation_guidance = template_meta.validation_guidance
            pii_guidance = template_meta.pii_guidance
            expected_sections = template_meta.expected_sections
            expected_fields = template_meta.expected_fields
            
            # Fetch the manifest (JSON)
            if template_meta.field_extraction_manifest:
                try:
                    field_manifest = json.loads(template_meta.field_extraction_manifest)
                except:
                    field_manifest = template_meta.field_extraction_manifest

            # Phase 3: Extract Text & Analyze On-the-fly if needed
            content = None
            if storage_uri:
                try:
                    storage_key = storage_uri.replace("local://", "")
                    content = storage_provider.get_bytes(storage_key)
                    
                    context = ExtractionContext(intent="template_context_extraction", actor_role="system")
                    extracted_doc = await doc_parser.extract(
                        file_bytes=content,
                        filename="template.docx",
                        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        context=context
                    )
                    template_text = extracted_doc.extracted_text
                    
                    # --- AUTO-DISCOVERY: If DB is missing fields, find them in the docx text ---
                    if not expected_fields and template_text:
                        placeholders = re.findall(r'\{\{\s*(.*?)\s*\}\}', template_text)
                        if placeholders:
                            expected_fields = ",".join(list(set(placeholders)))

                    # --- ON-THE-FLY ANALYSIS: If manifest is missing, generate it now ---
                    if not field_manifest and content:
                        print(f"Manifest missing for template {chosen_template_id}. Triggering on-the-fly analysis...")
                        try:
                            ai_service = ResumeAiService(llm_runtime, doc_parser)
                            analysis = await ai_service.analyze_template(content=content, filename="template.docx")
                            if analysis and analysis.fields:
                                field_manifest = [f.dict(by_alias=True) for f in analysis.fields]
                                # Save back to DB
                                try:
                                    template_meta.field_extraction_manifest = json.dumps(field_manifest)
                                    repo.save_template(template_meta)
                                    db.commit()
                                except Exception as db_err:
                                    print(f"Non-critical: Failed to save on-the-fly manifest: {db_err}")
                        except Exception as ai_err:
                            print(f"Failed on-the-fly template analysis: {ai_err}")

                except Exception as ex:
                    print(f"Failed to extract raw text from template: {ex}")

            return {
                "selected_template_id": chosen_template_id,
                "template_storage_uri": storage_uri,
                "template_text": template_text,
                "summary_guidance": summary_guidance,
                "formatting_guidance": formatting_guidance,
                "validation_guidance": validation_guidance,
                "pii_guidance": pii_guidance,
                "expected_sections": expected_sections,
                "expected_fields": expected_fields,
                "field_extraction_manifest": field_manifest,
                "status": "template_resolved"
            }

        except Exception as e:
            print(f"Error during template resolution: {e}")
            return {
                "selected_template_id": state.get("selected_template_id") or "general_cv_v1",
                "status": "template_resolved_fallback"
            }
        finally:
            db.close()

    return template_resolve_node
