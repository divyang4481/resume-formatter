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

            # Simple cleanup
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            return json.loads(response_text.strip())
        except Exception as e:
            logger.error(f"Local Agent Extraction failed: {e}")
            raise

    def generate_template_contract(
        self,
        *,
        template_text: str,
        template_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        prompt = f"""
        You are an expert HR template analyzer. I am providing you with the parsed text of a Resume Template.
        Your task is to identify all the fields and sections that need to be extracted from a candidate's resume to fill out this template.

        Template metadata:
        {json.dumps(template_metadata, indent=2)}

        Parsed Template Text:
        {template_text}

        Output ONLY a valid JSON object matching this structure:
        {{
            "sections": [
                {{
                    "section_key": "string",
                    "required": boolean,
                    "repeatable": boolean,
                    "expected_content_type": "string"
                }}
            ],
            "placeholders": ["string"],
            "quality_rules": ["string"],
            "rendering_rules": ["string"]
        }}
        """
        try:
            response_text = self.llm.generate(prompt=prompt, temperature=0.1)
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            return json.loads(response_text.strip())
        except Exception as e:
            logger.error(f"Local Agent generate_template_contract failed: {e}")
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
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            return json.loads(response_text.strip())
        except Exception as e:
            logger.error(f"Local Agent evaluate_output_quality failed: {e}")
            raise
