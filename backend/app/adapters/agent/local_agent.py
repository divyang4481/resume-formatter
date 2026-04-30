import json
import logging
from typing import Dict, Any
from app.domain.interfaces.agent import ResumeFormattingAgent
from app.domain.interfaces.llm import LlmRuntimeAdapter

logger = logging.getLogger(__name__)

class LocalLLMResumeFormattingAgent(ResumeFormattingAgent):
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
