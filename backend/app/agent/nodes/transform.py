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
        template_id = state.get("selected_template_id") or "default"
        
        formatting_guidance = state.get("formatting_guidance") or ""
        pii_guidance = state.get("pii_guidance") or ""
        expected_sections = state.get("expected_sections") or "Summary, Experience, Education, Skills"
        expected_fields = state.get("expected_fields") or ""
        template_text = state.get("template_text") or "Not provided"

        # Build a dynamic JSON structure based on the current template's requirements

        # Fallback to standard info if no requirements are specified
        dynamic_schema = {
            "personal_info": {"name": "", "email": ""},
            "summary": ""
        }
        
        if expected_fields:
            fields = [f.strip() for f in expected_fields.split(",") if f.strip()]
            for f in fields:
                # Merge into root or nested structure? Keeping it flat for simplicity in generic templates
                dynamic_schema[f] = ""

        if expected_sections:
            sections = [s.strip() for s in expected_sections.split(",") if s.strip()]
            for s in sections:
                if s.lower() not in ["summary", "personal_info"]:
                     dynamic_schema[s.lower().replace(" ", "_")] = [] # Sections are usually arrays of objects or strings

        prompt = f"""
        You are an expert document transformer. Your job is to extract and transform the provided
        resume/CV text into a canonical structured JSON format that will be rendered INTO a specific template.

        TARGET TEMPLATE STRUCTURE (EXTRACTED TEXT):
        {template_text[:4000]}

        TEMPLATE EXPECTATIONS:
        Mandatory Sections to Identify: {expected_sections}
        Required Specific Fields to Extract: {expected_fields}

        TEMPLATE GUIDANCE & POLICIES:
        {formatting_guidance}
        {pii_guidance}

        CRITICAL INSTRUCTIONS:
        1. Extract facts ONLY from the "Resume Document Text" below.
        2. Output ONLY the JSON structure defined below.
        3. Use the structural layout of the TARGET TEMPLATE above to decide how to best map and summarize the candidate's data.
        4. If a field is missing, leave it as "" or [].
        5. DO NOT invent data or use placeholders.

        Please output ONLY valid JSON matching exactly this dynamic structure:
        {json.dumps(dynamic_schema, indent=2)}


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
