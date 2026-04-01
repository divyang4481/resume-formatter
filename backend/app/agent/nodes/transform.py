from app.agent.state import AgentState
from app.adapters.base import LlmRuntimeAdapter
import json

def create_transform_node(llm_runtime: LlmRuntimeAdapter):
    """
    Creates the LangGraph node for document transformation and summarization using the LLM.
    """
    def transform_node(state: AgentState) -> dict:
        print("Executing Transform Node...")

        extracted_text = state.get("extracted_text", "")
        template_id = state.get("selected_template_id", "default")

        # In a real app, you'd fetch the schema/template rules from a database/registry
        # Here we mock it.
        prompt = f"""
        You are an expert document transformer. Your job is to extract and transform the provided
        resume/CV text into a structured JSON format according to the requested template ID.

        Template ID: {template_id}

        Please output ONLY valid JSON matching this structure:
        {{
            "personal_info": {{
                "name": "...",
                "email": "..."
            }},
            "summary": "Professional summary...",
            "experience": [
                {{
                    "title": "...",
                    "company": "...",
                    "dates": "...",
                    "description": "..."
                }}
            ],
            "skills": ["...", "..."]
        }}

        Document Text:
        {extracted_text}
        """

        try:
            # Call the injected LLM runtime adapter
            response_text = llm_runtime.generate(prompt=prompt, temperature=0.1)

            # Simple cleanup to remove potential markdown fences
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            # Validate it's actually JSON
            json.loads(response_text)

            return {
                "transformed_document_json": response_text.strip(),
                "status": "transformed"
            }
        except Exception as e:
            print(f"Error during transformation: {e}")
            return {
                "validation_passed": False,
                "validation_errors": [str(e)],
                "status": "transformation_failed"
            }

    return transform_node
