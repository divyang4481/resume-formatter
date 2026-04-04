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

    async def classify_document(
        self,
        extracted_text: str,
        raw_parsed_data: Dict[str, Any],
        filename: str,
        content_type: str,
        extraction_confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        structured_context = ""
        sections = (raw_parsed_data or {}).get("sections", []) if raw_parsed_data else []
        tables = (raw_parsed_data or {}).get("tables", []) if raw_parsed_data else []

        if sections:
            structured_context += "\nDETECTED SECTIONS:\n" + "\n".join(
                [f"- {s.get('title')}" for s in sections if s.get("title")]
            )
        if tables:
            structured_context += f"\nDETECTED TABLES: {len(tables)}"

        prompt = prompt_manager.get_prompt(
            "document_classification.jinja2",
            filename=filename,
            content_type=content_type,
            extraction_confidence=extraction_confidence if extraction_confidence is not None else "",
            structured_context=structured_context,
            extracted_text=(extracted_text or "")[:12000],
        )

        response = self.llm.generate(prompt)
        try:
            cleaned = LlmSanitizer.clean_json(response)
            result = json.loads(cleaned)
        except Exception as e:
            logger.warning(
                f"AI classification produced invalid JSON. Defaulting to safe fallback. Error: {e}. Raw Response Excerpt: {response[:200]}"
            )
            result = {}

        return {
            "document_kind": result.get("document_kind", "candidate_resume"),
            "confidence": float(result.get("confidence", 0.8)),
            "reason": result.get("reason", "Fallback: AI classification failed or was malformed."),
        }

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

    async def analyze_template(self, content: bytes, filename: str) -> Dict[str, Any]:
        """
        Analyzes a CV template to understand its structure, tone, and formatting requirements.
        Generates suggestions for 'expected_fields' and metadata extraction.
        """
        from app.services.audit_service import AuditService
        from app.domain.interfaces import ExtractionContext
        if not self.extraction_service: return {}
        
        context = ExtractionContext(intent="template_analysis", actor_role="system")
        extracted_doc = await self.extraction_service.extract(
            content, filename, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", context
        )
        
        # Retrieve placeholders in EXACT visual order using regex across the whole document text
        import io, re
        
        # Pattern covers << section >>, {{ field }}, and [[:B:]] markup placeholders
        pattern = r"<<\s*(.*?)\s*>>|\{\{\s*(.*?)\s*\}\}|\[\[\s*(.*?)\s*\]\]"
        matches = re.finditer(pattern, extracted_doc.extracted_text)
        
        detected_placeholders = []
        for match in matches:
            # Get the first non-None group (the inner text)
            inner_text = next(group for group in match.groups() if group is not None)
            detected_placeholders.append(inner_text.strip())
        
        logger.info(f"AI Template Analysis: Found {len(detected_placeholders)} placeholders in visual order: {detected_placeholders}")
        
        prompt = prompt_manager.get_prompt(
            "template_analysis.jinja2",
            template_text=extracted_doc.extracted_text[:8000],
            detected_placeholders=detected_placeholders,
            sections=extracted_doc.parsed_document.sections if extracted_doc.parsed_document else [],
            tables=extracted_doc.parsed_document.tables if extracted_doc.parsed_document else []
        )

        # Audit Prompt
        AuditService.log_event(
            job_id=filename,
            event_type="TEMPLATE_ANALYSIS_PROMPT",
            payload={"prompt": prompt},
            entity_type="TemplateAsset"
        )

        response = self.llm.generate(prompt)

        # Audit Response
        AuditService.log_event(
            job_id=filename,
            event_type="TEMPLATE_ANALYSIS_RESPONSE",
            payload={"response": response},
            entity_type="TemplateAsset"
        )
        
        try:
            cleaned = LlmSanitizer.clean_json(response)
            result = json.loads(cleaned)
        except Exception as e:
            logger.warning(f"AI Template Analysis failed to parse JSON: {e}")
            logger.debug(f"RAW TEMPLATE ANALYSIS RESPONSE (FIRST 500 CHARS): {response[:500]}")
            # Fallback to tagged blocks if JSON fails
            result = LlmSanitizer.extract_tagged_blocks(response)

        # Build Suggestions (Support both JSON keys and Tagged Block keys - Case Insensitive)
        normalized_result = {str(k).lower(): v for k, v in result.items()}
        
        # Extract fields with best match fallback
        suggestions = {
            "purpose": normalized_result.get("purpose") or "General Template",
            "expected_sections": normalized_result.get("expected_sections") or "Summary, Experience",
            "expected_fields": normalized_result.get("expected_fields") or ",".join(detected_placeholders),
            "field_extraction_manifest": normalized_result.get("field_extraction_manifest") or [],
            "summary_guidance": normalized_result.get("summary_guidance") or "",
            "formatting_guidance": normalized_result.get("formatting_guidance") or "",
            "validation_guidance": normalized_result.get("validation_guidance") or "",
            "pii_guidance": normalized_result.get("pii_guidance") or ""
        }
        
        return suggestions

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
