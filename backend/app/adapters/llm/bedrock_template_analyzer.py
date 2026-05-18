import json
import logging
from typing import Dict, List, Any, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError

from app.adapters.llm.aws_bedrock_runtime import AwsBedrockLlmRuntime
from app.agent.utils.llm_sanitizer import LlmSanitizer
from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

class BedrockTemplateAnalyzer:
    """
    Orchestrates high-level template and resume analysis using AWS Bedrock.
    Provides strict JSON enforcement and Pydantic validation.
    """

    def __init__(self, runtime: Optional[AwsBedrockLlmRuntime] = None):
        self.runtime = runtime or AwsBedrockLlmRuntime()

    def analyze_template(self, prompt: str, schema: Type[T]) -> T:
        """
        Sends extracted template structure to Bedrock and returns a validated Pydantic model.
        Retries once with JSON repair if validation fails.
        """
        system_prompt = (
            "You are an expert document architect. Your task is to analyze document structure and produce a strict JSON manifest. "
            "Follow the provided JSON schema exactly. Do not include markdown code fences or any conversational text. "
            "Always return a single JSON object."
        )

        model_id = settings.bedrock_template_analysis_model_id or "qwen.qwen3-235b-a22b-2507-v1:0"

        response = self.runtime.generate(
            prompt,
            system_prompt=system_prompt,
            model_id=model_id,
            task_name="template_analysis",
            temperature=0.0  # Maximum determinism
        )

        return self._parse_and_validate(response, schema, prompt, system_prompt, model_id)

    def extract_facts(self, prompt: str, schema: Type[T]) -> T:
        """
        Extracts candidate facts from resume text into a structured schema.
        Uses the RESUME_EXTRACTION_MODEL (Haiku).
        """
        system_prompt = (
            "You are a professional resume parser. Extract all relevant facts into the requested JSON structure. "
            "If a field is not present in the source, set it to null or an empty list. Do not hallucinate. "
            "Provide a confidence score for each section."
        )

        # Map to specific Qwen model for high capacity and 8192 token limit
        model_id = getattr(settings, "bedrock_resume_extraction_model_id", "qwen.qwen3-235b-a22b-2507-v1:0")

        response = self.runtime.generate(
            prompt,
            system_prompt=system_prompt,
            model_id=model_id,
            task_name="resume_extraction",
            temperature=0.0
        )

        return self._parse_and_validate(response, schema, prompt, system_prompt, model_id)

    def _parse_and_validate(self, response: str, schema: Type[T], original_prompt: str, system_prompt: str, model_id: str) -> T:
        """Internal helper to clean, parse, and validate LLM output."""
        try:
            cleaned_json = LlmSanitizer.clean_json(response)
            data = json.loads(cleaned_json)
            return schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"[BedrockAnalyzer] Validation failed: {e}. Attempting JSON repair...")
            
            # Phase 2: Attempt repair
            repair_prompt = (
                f"Your previous response failed validation with error: {str(e)}\n\n"
                f"Original Response:\n{response}\n\n"
                f"Fix the JSON to perfectly match the requested schema. Return ONLY the valid JSON."
            )
            
            repair_response = self.runtime.generate(
                repair_prompt,
                system_prompt=system_prompt,
                model_id=model_id,
                temperature=0.0
            )
            
            try:
                cleaned_repair = LlmSanitizer.clean_json(repair_response)
                data_repair = json.loads(cleaned_repair)
                return schema.model_validate(data_repair)
            except Exception as e_final:
                logger.error(f"[BedrockAnalyzer] JSON repair failed: {e_final}")
                raise ValueError(f"Failed to produce valid JSON manifest after repair: {e_final}")
