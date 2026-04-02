from app.agent.state import AgentState
from app.adapters.base import LlmRuntimeAdapter
from app.db.session import SessionLocal
from app.adapters.repositories.template_repository import SqlAlchemyTemplateRepository

def create_template_resolve_node(llm_runtime: LlmRuntimeAdapter):
    """
    Creates the LangGraph node for resolving the appropriate template based on the
    document content or user request.
    """
    def template_resolve_node(state: AgentState) -> dict:
        print("Executing Template Resolution Node...")

        extracted_text = state.get("extracted_text", "")

        # We can use the LLM to classify the document and choose the best template if not provided
        if state.get("selected_template_id"):
             print(f"Template already selected: {state['selected_template_id']}")
             return {"status": "template_resolved"}

        # Fetch available templates from DB
        db = SessionLocal()
        try:
            repo = SqlAlchemyTemplateRepository(db)
            available_templates = repo.list_templates({})

            if not available_templates:
                template_options_str = "No templates available in database."
                default_template = "general_cv_v1"
            else:
                options = []
                for idx, t in enumerate(available_templates, 1):
                    desc = f"for {t.industry} / {t.role_family}" if t.industry else (t.description or "general template")
                    options.append(f"{idx}. {t.id} ({desc})")
                template_options_str = "\n        ".join(options)
                default_template = available_templates[0].id
        finally:
            db.close()

        prompt = f"""
        Based on the following resume or document text, identify the industry and recommend
        the best template ID for formatting it.

        Available templates:
        {template_options_str}

        Document Text:
        {extracted_text[:1500]} ... (truncated)

        Respond ONLY with the exact Template ID from the list above that best fits this document.
        """

        try:
            response_text = llm_runtime.generate(prompt=prompt, temperature=0.0).strip()

            chosen_template = default_template
            # Try to find a matching ID from the available templates
            if available_templates:
                for t in available_templates:
                    if t.id in response_text:
                        chosen_template = t.id
                        break

            print(f"Resolved Template ID: {chosen_template}")

            return {
                "selected_template_id": chosen_template,
                "status": "template_resolved"
            }
        except Exception as e:
            print(f"Error during template resolution: {e}")
            return {
                "selected_template_id": default_template, # fallback
                "status": "template_resolved_fallback"
            }

    return template_resolve_node
