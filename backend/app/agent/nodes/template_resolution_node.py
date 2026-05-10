import asyncio
from app.agent.state import AgentState
from app.domain.interfaces import LlmRuntimeAdapter
from app.db.session import SessionLocal
from app.adapters.repositories.template_repository import SqlAlchemyTemplateRepository
from app.services.template_resolution_service import TemplateResolutionService

def create_template_resolve_node(llm_runtime, storage_provider, doc_parser):
    """
    Creates the LangGraph node for resolving the appropriate template based on the
    document content or user request.
    """
    async def template_resolve_node(state: AgentState) -> dict:
        print("Executing Template Resolution Node...")
        
        from app.domain.interfaces import ExtractionContext
        
        extracted_text = state.get("extracted_text", "")
        mode = state.get("intent", "recruiter_runtime")

        # Try to resolve or validate the template selection
        db = SessionLocal()
        try:
            repo = SqlAlchemyTemplateRepository(db)
            service = TemplateResolutionService(llm_runtime, repo)

            chosen_template_id = state.get("selected_template_id")
            
            if not chosen_template_id:
                # Use the shared TemplateResolutionService for classification-based recommendation
                result = await service.recommend_template(
                    extracted_text=extracted_text,
                    mode=mode
                )

                chosen_template_id = result.suggested_template_id
                
                if not chosen_template_id:
                    # Fallback to the first active template in RDS
                    first_tpl = repo.list_active_templates()
                    if first_tpl:
                        chosen_template_id = first_tpl[0].id
                        print(f"Fallback: Using first active RDS template ID: {chosen_template_id}")
                    else:
                        raise ValueError("No active templates found in RDS. Template resolution failed.")
                
                print(f"Resolved Template ID: {chosen_template_id}")

            # Fetch the actual storage URI and guidance from the repository
            template_meta = repo.get_template(chosen_template_id)
            if not template_meta:
                 raise ValueError(f"Template with ID {chosen_template_id} not found in database.")
            storage_uri = None
            summary_guidance = None
            formatting_guidance = None
            validation_guidance = None
            pii_guidance = None
            template_text = None

            if template_meta:
                storage_uri = template_meta.original_file_ref
                summary_guidance = template_meta.summary_guidance
                formatting_guidance = template_meta.formatting_guidance
                validation_guidance = template_meta.validation_guidance
                pii_guidance = template_meta.pii_guidance
                expected_sections = template_meta.expected_sections
                expected_fields = template_meta.expected_fields
                
                # Fetch the manifest (JSON)
                field_manifest = None
                if template_meta.field_extraction_manifest:
                    import json
                    try:
                        field_manifest = json.loads(template_meta.field_extraction_manifest)
                    except:
                        field_manifest = template_meta.field_extraction_manifest

                print(f"Found template storage URI: {storage_uri}")
                
                # ... (rest of doc extraction logic)
                try:
                    if storage_uri:
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
                            # Simple regex to find {{ placeholders }} or similar patterns
                            import re
                            placeholders = re.findall(r'\{\{\s*(.*?)\s*\}\}', template_text)
                            if placeholders:
                                expected_fields = ",".join(list(set(placeholders)))
                                print(f"Auto-discovered {len(placeholders)} placeholders from template: {expected_fields}")

                        print(f"Template text extracted successfully (length: {len(template_text)})")
                except Exception as ex:
                    print(f"Failed to extract raw text from template: {ex}")
            else:
                print(f"Warning: Template ID {chosen_template_id} not found in database.")
                expected_sections = None
                expected_fields = None


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
