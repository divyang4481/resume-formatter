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
        
        print(f"Transforming text (Length: {len(extracted_text)} chars) using template: {template_id}")

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
            
            if not response_text.strip():
                print("LLM returned empty response!")

            # Smarter cleanup for JSON blocks
            cleaned_text = response_text.strip()
            if "```json" in cleaned_text:
                cleaned_text = cleaned_text.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_text:
                cleaned_text = cleaned_text.split("```")[1].split("```")[0].strip()
            
            # Remove any leading/trailing text outside the first { and last }
            start_index = cleaned_text.find('{')
            end_index = cleaned_text.rfind('}')
            if start_index != -1 and end_index != -1:
                cleaned_text = cleaned_text[start_index:end_index+1]

            # Validate it's actually JSON
            json.loads(cleaned_text)

            return {
                "transformed_document_json": cleaned_text.strip(),
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
