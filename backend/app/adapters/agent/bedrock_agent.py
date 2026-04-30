import boto3
import json
import logging
from typing import Dict, Any
from app.domain.interfaces.agent import ResumeFormattingAgent
from app.config import settings

logger = logging.getLogger(__name__)

class BedrockResumeFormattingAgent(ResumeFormattingAgent):
    def __init__(self, agent_id: str = None, agent_alias_id: str = None):
        self.agent_id = agent_id or settings.bedrock_agent_id
        self.agent_alias_id = agent_alias_id or settings.bedrock_agent_alias_id
        self.client = boto3.client('bedrock-agent-runtime', region_name=settings.aws_region)

    def map_resume_to_template(
        self,
        *,
        parsed_resume: Dict[str, Any],
        template_contract: Dict[str, Any],
        template_rules: Dict[str, Any],
        pii_policy: Dict[str, Any],
        job_context: Dict[str, Any]
    ) -> Dict[str, Any]:

        session_id = job_context.get("job_id", "default-session")

        prompt = json.dumps({
            "instruction": "Map the parsed resume strictly to the template_contract JSON schema. Follow template_rules and pii_policy.",
            "parsed_resume": parsed_resume,
            "template_contract": template_contract,
            "template_rules": template_rules,
            "pii_policy": pii_policy
        })

        try:
            response = self.client.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
                inputText=prompt
            )

            completion = ""
            for event in response.get('completion', []):
                if 'chunk' in event:
                    completion += event['chunk']['bytes'].decode('utf-8')

            # Basic cleanup if the agent adds markdown blocks
            if completion.startswith("```json"):
                completion = completion[7:]
            if completion.endswith("```"):
                completion = completion[:-3]

            return json.loads(completion.strip())
        except Exception as e:
            logger.error(f"Failed to invoke Bedrock Agent: {e}")
            raise

    def generate_template_contract(
        self,
        *,
        template_text: str,
        template_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        session_id = "template-contract-" + template_metadata.get("template_id", "default")

        prompt = json.dumps({
            "instruction": "Analyze the template text and generate a structured JSON contract matching the required format. Include sections, placeholders, quality_rules, and rendering_rules.",
            "template_text": template_text,
            "template_metadata": template_metadata
        })

        try:
            response = self.client.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
                inputText=prompt
            )

            completion = ""
            for event in response.get('completion', []):
                if 'chunk' in event:
                    completion += event['chunk']['bytes'].decode('utf-8')

            if completion.startswith("```json"):
                completion = completion[7:]
            if completion.endswith("```"):
                completion = completion[:-3]

            return json.loads(completion.strip())
        except Exception as e:
            logger.error(f"Failed to invoke Bedrock Agent for contract generation: {e}")
            raise

    def evaluate_output_quality(
        self,
        *,
        mapped_data: Dict[str, Any],
        template_contract: Dict[str, Any],
        job_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        session_id = job_context.get("job_id", "default-session")

        prompt = json.dumps({
            "instruction": "Evaluate the quality of the mapped resume data against the template contract. Provide a quality assessment JSON with 'needs_review', 'reason', 'suggested_admin_action', and 'confidence'.",
            "mapped_data": mapped_data,
            "template_contract": template_contract
        })

        try:
            response = self.client.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
                inputText=prompt
            )

            completion = ""
            for event in response.get('completion', []):
                if 'chunk' in event:
                    completion += event['chunk']['bytes'].decode('utf-8')

            if completion.startswith("```json"):
                completion = completion[7:]
            if completion.endswith("```"):
                completion = completion[:-3]

            return json.loads(completion.strip())
        except Exception as e:
            logger.error(f"Failed to invoke Bedrock Agent for quality evaluation: {e}")
            raise
