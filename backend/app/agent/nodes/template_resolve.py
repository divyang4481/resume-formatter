import asyncio
from app.agent.state import AgentState
from app.adapters.base import LlmRuntimeAdapter
from app.db.session import SessionLocal
from app.adapters.repositories.template_repository import SqlAlchemyTemplateRepository
from app.services.template_resolution_service import TemplateResolutionService

def create_template_resolve_node(llm_runtime: LlmRuntimeAdapter):
    """
    Creates the LangGraph node for resolving the appropriate template based on the
    document content or user request.
    """
    def template_resolve_node(state: AgentState) -> dict:
        print("Executing Template Resolution Node...")

        extracted_text = state.get("extracted_text", "")
        mode = state.get("intent", "recruiter_runtime")

        # We can use the LLM to classify the document and choose the best template if not provided
        if state.get("selected_template_id"):
             print(f"Template already selected: {state['selected_template_id']}")
             return {"status": "template_resolved"}

        # Use the shared TemplateResolutionService
        db = SessionLocal()
        try:
            repo = SqlAlchemyTemplateRepository(db)
            service = TemplateResolutionService(llm_runtime, repo)

            # Since LangGraph node is synchronous in our current implementation (using `def` not `async def` wrapper usually called by graph executor),
            # but our service method is async.
            # However `recommend_template` only does CPU blocking or synchronous requests if the adapter is sync.
            # Let's run the async function
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()

            result = asyncio.run(service.recommend_template(
                extracted_text=extracted_text,
                mode=mode
            ))

            chosen_template = result.suggested_template_id or "general_cv_v1"
            print(f"Resolved Template ID: {chosen_template}")

            return {
                "selected_template_id": chosen_template,
                "status": "template_resolved"
            }
        except Exception as e:
            print(f"Error during template resolution: {e}")
            return {
                "selected_template_id": "general_cv_v1", # fallback
                "status": "template_resolved_fallback"
            }
        finally:
            db.close()

    return template_resolve_node
