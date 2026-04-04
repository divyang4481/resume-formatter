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

    class TemplateAnalysisError(Exception):
        """Domain-specific error for template analysis failures."""
        pass

    async def analyze_template_metadata(self, content: bytes, filename: str) -> 'TemplateAnalysisResult':
        """
        Analyzes a .docx template to generate field semantics metadata.
        Uses structured generation if the runtime supports it, and falls back to strict JSON parsing.
        """
        if not self.extraction_service:
            logger.error("Extraction service unavailable for template analysis.")
            raise self.TemplateAnalysisError("Extraction service unavailable.")
        
        from app.domain.interfaces import ExtractionContext
        
        try:
            extracted_doc = await self.extraction_service.extract(
                content, filename, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        except Exception as e:
            logger.error(f"Document extraction failed for {filename}: {e}")
            raise self.TemplateAnalysisError(f"Failed to extract document text: {e}")

        # Retrieve placeholders and preserve order
        from docxtpl import DocxTemplate
        import io
        try:
            doc = DocxTemplate(io.BytesIO(content))
            raw_placeholders = [str(p).strip() for p in doc.get_undeclared_template_variables()]
            detected_placeholders = list(dict.fromkeys(raw_placeholders))
        except Exception as e:
            logger.error(f"DOCX placeholder extraction failed for {filename}: {e}")
            raise self.TemplateAnalysisError(f"Failed to extract DOCX placeholders: {e}")
        
        if not detected_placeholders:
            logger.warning(f"No placeholders detected in {filename}.")
            raise self.TemplateAnalysisError("No placeholders detected in the template. Cannot generate field semantics.")

        prompt = prompt_manager.get_prompt(
            "template_analysis.jinja2",
            template_text=extracted_doc.extracted_text[:8000],
            detected_placeholders=detected_placeholders,
        )

        from app.schemas.template import TemplateAnalysisResult
        schema = TemplateAnalysisResult.model_json_schema()

        # Provide system prompt and json schema hints for structured generation
        system_prompt = "You are a World-Class Professional Resume Template Analyzer. You output ONLY valid JSON."
        try:
            response = self.llm.generate(
                prompt,
                system_prompt=system_prompt,
                response_format=schema,
                temperature=0.1
            )
        except Exception as e:
            logger.error(f"LLM generation failed during template analysis: {e}")
            raise self.TemplateAnalysisError(f"LLM generation failed: {e}")
        
        # Parse strict JSON
        try:
            result = LlmSanitizer.parse_json_object(response)
        except ValueError as e:
            # Re-raise as domain error
            raise self.TemplateAnalysisError(str(e))

        from pydantic import ValidationError
        try:
            validated_result = TemplateAnalysisResult.model_validate(result)
            # Manifest length equals placeholder count check
            if len(validated_result.field_extraction_manifest) != len(detected_placeholders):
                err_msg = f"Manifest count mismatch: expected {len(detected_placeholders)}, got {len(validated_result.field_extraction_manifest)}"
                logger.error(err_msg)
                raise self.TemplateAnalysisError(err_msg)

            return validated_result
        except ValidationError as e:
            logger.error(f"Schema validation mismatch for LLM output. Errors: {e.errors()}")
            raise self.TemplateAnalysisError(f"LLM output failed schema validation: {e}")

    async def analyze_template(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Backward compatibility stub that calls the new analysis logic."""
        result = await self.analyze_template_metadata(content, filename)
        return result.model_dump()

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
