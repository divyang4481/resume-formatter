import json
import logging
from typing import Dict, Any
from app.domain.interfaces.agent import ResumeFormattingAgent
from app.domain.interfaces.llm import LlmRuntimeAdapter

logger = logging.getLogger(__name__)

class PythonOrchestratedResumeFormattingAgent(ResumeFormattingAgent):
    def __init__(self, llm: LlmRuntimeAdapter):
        self.llm = llm

    def map_resume_to_template(
        self,
        *,
        parsed_resume: Dict[str, Any],
        template_contract: Dict[str, Any],
        template_rules: Dict[str, Any],
        pii_policy: Dict[str, Any],
        job_context: Dict[str, Any]
    ) -> Dict[str, Any]:

        # In a real local setup, we'd use a Jinja prompt template here
        prompt = f"""
        Map the following parsed resume strictly to the provided JSON schema.

        Rules:
        {json.dumps(template_rules, indent=2)}

        PII Policy:
        {json.dumps(pii_policy, indent=2)}

        Schema (Template Contract):
        {json.dumps(template_contract, indent=2)}

        Resume Data:
        {json.dumps(parsed_resume, indent=2)}

        Output MUST be pure JSON with no markdown wrapping.
        """

        try:
            response_text = self.llm.generate(prompt=prompt, temperature=0.1)
            logger.info(f"LLM Response (raw): {response_text}")

            import re
            json_match = re.search(r"```(?:json)?\n?(.*?)```", response_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(1).strip()
            else:
                # Fallback: try to find the first '{' and last '}'
                start = response_text.find('{')
                end = response_text.rfind('}')
                if start != -1 and end != -1:
                    cleaned_text = response_text[start:end+1].strip()
                else:
                    cleaned_text = response_text.strip()

            if not cleaned_text:
                logger.error("LLM returned an empty response or no JSON found.")
                raise ValueError("LLM returned an empty response or no JSON found")

            return json.loads(cleaned_text)
        except Exception as e:
            logger.error(f"Local Agent Extraction failed: {e}")
            raise

    def generate_template_contract(
        self,
        *,
        template_text: str,
        template_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        import os
        from jinja2 import Template
        
        # Load the Jinja2 template
        template_path = os.path.join(os.path.dirname(__file__), "..", "..", "agent", "prompts", "template_analysis.jinja2")
        with open(template_path, "r") as f:
            jinja_template = Template(f.read())
        
        # Prepare variables for the template
        # We'll extract potential placeholders from the text using a simple regex if not provided
        import re
        # Support multiple placeholder styles: <<key>>, {{key}}, [[key]]
        detected_placeholders = re.findall(r"(?:<<|\{\{|\[\[)(.*?)(?:>>|\}\}|\]\])", template_text)
        
        prompt = jinja_template.render(
            template_text=template_text,
            detected_placeholders=detected_placeholders
        )

        try:
            response_text = self.llm.generate(prompt=prompt, temperature=0.1)
            logger.info(f"LLM Response (raw): {response_text}")

            import re
            json_match = re.search(r"```(?:json)?\n?(.*?)```", response_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(1).strip()
            else:
                # Fallback: try to find the first '{' and last '}'
                start = response_text.find('{')
                end = response_text.rfind('}')
                if start != -1 and end != -1:
                    cleaned_text = response_text[start:end+1].strip()
                else:
                    cleaned_text = response_text.strip()

            if not cleaned_text:
                logger.error("LLM returned an empty response or no JSON found.")
                raise ValueError("LLM returned an empty response or no JSON found")

            try:
                return json.loads(cleaned_text)
            except json.JSONDecodeError:
                repaired = self._repair_json(cleaned_text)
                return json.loads(repaired)
        except Exception as e:
            logger.error(f"Local Agent generate_template_contract failed: {e}")
            raise

    def _repair_json(self, json_str: str) -> str:
        """Robustly repairs truncated JSON by rolling back to a structural point and then closing it."""
        json_str = json_str.strip()
        if not json_str:
            return "{}"
            
        # 1. Roll back to the last safe structural point (comma, brace, bracket)
        # This prevents being in the middle of a key name or value
        last_comma = json_str.rfind(',')
        last_open_brace = json_str.rfind('{')
        last_open_bracket = json_str.rfind('[')
        
        safe_point = max(last_comma, last_open_brace, last_open_bracket)
        
        if safe_point != -1:
            # Cut at the safe point
            json_str = json_str[:safe_point]
            # If we cut at a comma, strip it
            if safe_point == last_comma:
                json_str = json_str.rstrip(',')

        # 2. Handle unclosed quotes AFTER rolling back
        # Count non-escaped quotes in the new string
        import re
        if len(re.findall(r'(?<!\\)"', json_str)) % 2 != 0:
            json_str += '"'

        # 3. Count remaining imbalances and close them
        open_braces = json_str.count('{') - json_str.count('}')
        open_brackets = json_str.count('[') - json_str.count(']')
        
        json_str += ']' * max(0, open_brackets)
        json_str += '}' * max(0, open_braces)
        
        logger.info(f"Repaired truncated JSON. New length: {len(json_str)}")
        return json_str

    def extract_structured_data(
        self,
        *,
        extracted_text: str,
        dynamic_schema: Dict[str, Any],
        template_context: str = "",
        formatting_guidance: str = ""
    ) -> Dict[str, Any]:
        import os
        from jinja2 import Template
        
        template_path = os.path.join(os.path.dirname(__file__), "..", "..", "agent", "prompts", "context_aware_extraction.jinja2")
        with open(template_path, "r") as f:
            jinja_template = Template(f.read())
            
        prompt = jinja_template.render(
            dynamic_schema_json=json.dumps(dynamic_schema, indent=2),
            template_text_excerpt=template_context[:1000],
            extracted_text=extracted_text,
            formatting_guidance=formatting_guidance
        )

        try:
            response_text = self.llm.generate(prompt=prompt, temperature=0.0)
            
            import re
            json_match = re.search(r"```(?:json)?\n?(.*?)```", response_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(1).strip()
            else:
                start = response_text.find('{')
                end = response_text.rfind('}')
                if start != -1:
                    if end != -1 and end > start:
                        cleaned_text = response_text[start:end+1].strip()
                    else:
                        cleaned_text = response_text[start:].strip()
                else:
                    cleaned_text = response_text.strip()

            if not cleaned_text:
                raise ValueError("LLM returned an empty response or no JSON found")

            try:
                return json.loads(cleaned_text)
            except json.JSONDecodeError:
                # Try repair
                repaired = self._repair_json(cleaned_text)
                return json.loads(repaired)
        except Exception as e:
            logger.error(f"Local Agent Extraction failed: {e}")
            raise

    def evaluate_output_quality(
        self,
        *,
        mapped_data: Dict[str, Any],
        template_contract: Dict[str, Any],
        job_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        prompt = f"""
        Evaluate the quality of the mapped resume data against the template contract.

        Template Contract:
        {json.dumps(template_contract, indent=2)}

        Mapped Data:
        {json.dumps(mapped_data, indent=2)}

        Provide a quality assessment JSON with "needs_review" (boolean), "reason" (string, optional), "suggested_admin_action" (string, optional), and "confidence" (float). Output ONLY JSON.
        """
        try:
            response_text = self.llm.generate(prompt=prompt, temperature=0.1)
            logger.info(f"LLM Response (raw): {response_text}")

            import re
            json_match = re.search(r"```(?:json)?\n?(.*?)```", response_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(1).strip()
            else:
                # Fallback: try to find the first '{' and last '}'
                start = response_text.find('{')
                end = response_text.rfind('}')
                if start != -1 and end != -1:
                    cleaned_text = response_text[start:end+1].strip()
                else:
                    cleaned_text = response_text.strip()

            if not cleaned_text:
                logger.error("LLM returned an empty response or no JSON found.")
                raise ValueError("LLM returned an empty response or no JSON found")

            return json.loads(cleaned_text)
        except Exception as e:
            logger.error(f"Local Agent evaluate_output_quality failed: {e}")
            raise
