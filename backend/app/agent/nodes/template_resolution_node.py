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

        chosen_template_id = state.get("selected_template_id")
        if not chosen_template_id:
            return {
                "status": "template_missing_after_triage"
            }

        db = SessionLocal()
        try:
            repo = SqlAlchemyTemplateRepository(db)
            template_meta = repo.get_template(chosen_template_id)
            if not template_meta:
                return {
                    "status": "template_not_found",
                    "validation_passed": False,
                    "validation_errors": [f"Template not found: {chosen_template_id}"],
                }

            storage_uri = template_meta.original_file_ref
            summary_guidance = template_meta.summary_guidance
            formatting_guidance = template_meta.formatting_guidance
            validation_guidance = template_meta.validation_guidance
            pii_guidance = template_meta.pii_guidance
            expected_sections = template_meta.expected_sections
            expected_fields = template_meta.expected_fields
            template_text = None

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
                except Exception as ex:
                    print(f"Failed to extract raw text from template: {ex}")

            return {
                "template_storage_uri": storage_uri,
                "template_text": template_text,
                "summary_guidance": summary_guidance,
                "formatting_guidance": formatting_guidance,
                "validation_guidance": validation_guidance,
                "pii_guidance": pii_guidance,
                "expected_sections": expected_sections,
                "expected_fields": expected_fields,
                "status": "template_resolved",
            }
        except Exception as e:
            print(f"Error during template resolution: {e}")
            return {
                "status": "template_resolve_error",
                "validation_passed": False,
                "validation_errors": [str(e)],
            }
        finally:
            db.close()

    return template_resolve_node
