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
        resume/CV text into a canonical structured JSON format.

        CRITICAL INSTRUCTIONS:
        1. Extract the facts ONLY from the "Document Text" below.
        2. NEVER invent, hallucinate, or use placeholders (e.g., "<<FullName>>", "<<Skill1>>", "...", or similar).
        3. If information for a field is missing from the document, leave it empty (use "" for strings, [] for arrays).
        4. Do not output anything other than the JSON itself.

        Template ID: {template_id}

        Please output ONLY valid JSON matching exactly this structure:
        {{
            "personal_info": {{
                "name": "",
                "email": ""
            }},
            "experience": [
                {{
                    "title": "",
                    "company": "",
                    "dates": "",
                    "description": ""
                }}
            ],
            "education": [
                {{
                    "degree": "",
                    "school": "",
                    "dates": ""
                }}
            ],
            "skills": [],
            "certifications": []
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
            parsed_json = json.loads(cleaned_text)

            # Reject placeholders
            validation_errors = []
            if "<<" in cleaned_text or ">>" in cleaned_text:
                validation_errors.append("Output contains unresolved placeholders (<<...>>).")
            if '"..."' in cleaned_text or '...' in cleaned_text:
                validation_errors.append("Output contains generic string placeholders ('...').")

            # Additional structural checks on parsed JSON
            if isinstance(parsed_json, dict):
                # We can do deeper validation here if needed
                pass

            if validation_errors:
                return {
                    "transformed_document_json": cleaned_text.strip(),
                    "validation_passed": False,
                    "validation_errors": validation_errors,
                    "status": "transformation_failed"
                }

            return {
                "transformed_document_json": cleaned_text.strip(),
                "validation_passed": True,
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
