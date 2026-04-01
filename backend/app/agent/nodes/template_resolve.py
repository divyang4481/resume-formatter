from app.agent.state import AgentState
from app.adapters.base import LlmRuntimeAdapter

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

        prompt = f"""
        Based on the following resume or document text, identify the industry and recommend
        the best template ID for formatting it.

        Available templates:
        1. tech_resume_v1 (for software engineering, IT, data science)
        2. finance_resume_v1 (for banking, accounting, finance)
        3. creative_portfolio_v1 (for design, marketing, content creation)
        4. general_cv_v1 (for academic, research, or general professional)

        Document Text:
        {extracted_text[:1500]} ... (truncated)

        Respond ONLY with the exact Template ID from the list above that best fits this document.
        """

        try:
            response_text = llm_runtime.generate(prompt=prompt, temperature=0.0).strip()

            # Simple fuzzy match in case the model is wordy
            chosen_template = "general_cv_v1"
            if "tech" in response_text.lower():
                 chosen_template = "tech_resume_v1"
            elif "finance" in response_text.lower():
                 chosen_template = "finance_resume_v1"
            elif "creative" in response_text.lower():
                 chosen_template = "creative_portfolio_v1"

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

    return template_resolve_node
