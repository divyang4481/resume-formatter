from typing import Dict, Any, Optional, List
import json
import logging
from app.domain.interfaces import DocumentExtractionService
from app.domain.interfaces import LlmRuntimeAdapter
from app.agent.utils.llm_sanitizer import LlmSanitizer
from app.agent.prompt_manager import prompt_manager

logger = logging.getLogger(__name__)


class ResumeAiService:
    def __init__(
        self,
        llm: LlmRuntimeAdapter,
        extraction_service: Optional[DocumentExtractionService] = None,
    ):
        self.llm = llm
        self.extraction_service = extraction_service

    async def generate_summary(
        self,
        extracted_text: str,
        guidance: str,
        industry: Optional[str] = None,
        language: str = "en",
    ) -> str:
        """
        Generates a 100% human-grade professional summary.
        """
        prompt = prompt_manager.get_prompt(
            "resume_summary.jinja2",
            extracted_text=extracted_text[:12000],
            industry=industry,
            language=language,
            guidance=guidance,
        )

        print(f"\n--- [LLM PROMPT: SUMMARY] ---\n{prompt[:1000]}...\n")
        response = self.llm.generate(prompt)
        print(f"\n--- [LLM RAW RESPONSE: SUMMARY] ---\n{response[:1000]}...\n")
        
        blocks = LlmSanitizer.extract_tagged_blocks(response)
        summary = (
            blocks.get("Summary") or blocks.get("summary") or 
            blocks.get("SUMMARY") or blocks.get("__raw_content__") or 
            LlmSanitizer.clean_text(response)
        )
        
        return summary.strip()

    async def validate_output(
        self, transformed_data: Dict[str, Any], guidance: str
    ) -> Dict[str, Any]:
        """
        Uses LLM to perform semantic validation using Tags.
        """
        prompt = prompt_manager.get_prompt(
            "validation.jinja2",
            transformed_data_json=json.dumps(transformed_data, indent=2),
            guidance=guidance,
        )

        response = self.llm.generate(prompt)
        blocks = LlmSanitizer.extract_tagged_blocks(response)
        
        status = blocks.get("STATUS") or blocks.get("status") or "PASS"
        report = blocks.get("REPORT") or blocks.get("report") or "Validation logic missed tags."
        
        return {"status": status.upper().strip(), "errors": [report] if "FAIL" in status.upper() else []}

    async def harmonize_data_to_template_style(
        self,
        structured_data: Dict[str, Any],
        template_text: str,
        detected_placeholders: List[str] = None,
        field_manifest: List[Dict[str, Any]] = None,
        formatting_guidance: str = "",
    ) -> Dict[str, Any]:
        """
        AI HARMONIZATION: Transforms raw JSON into polished, human-readable prose 
        optimized for Word documents. Strictly prevents technical data dumps.
        """
        prompt = prompt_manager.get_prompt(
            "data_linearization.jinja2",
            structured_data_json=json.dumps(structured_data, indent=2),
            detected_placeholders_list=detected_placeholders or [],
            field_extraction_manifest=field_manifest or [],
            template_text_excerpt=template_text[:4000],
            formatting_guidance=formatting_guidance,
        )

        print(f"\n--- [LLM PROMPT: HARMONIZATION] ---\n{prompt[:2000]}...\n")

        try:
            response = self.llm.generate(prompt)
            print(f"\n--- [LLM RAW RESPONSE: HARMONIZATION] ---\n{response[:2000]}...\n")
            
            # 1. CORE STRATEGY: Tagged Block Extraction
            harmonized_data = LlmSanitizer.extract_tagged_blocks(response)
            
            if not harmonized_data:
                logger.error("AI harmonization FAILED to return any markers.")
                return structured_data

            return harmonized_data
        except Exception as e:
            logger.error(f"Critical failure in harmonization node: {e}")
            raise e
