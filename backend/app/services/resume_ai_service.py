from typing import Dict, Any, Optional, List
import json
import logging
from app.domain.interfaces import DocumentExtractionService
from app.domain.interfaces import LlmRuntimeAdapter
from app.agent.utils.llm_sanitizer import LlmSanitizer
from app.agent.prompt_manager import prompt_manager

logger = logging.getLogger(__name__)


class ResumeAiService:
    class TemplateAnalysisError(Exception):
        """Custom error for template analysis failures."""
        pass

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
        job_id: Optional[str] = None,
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

        system_prompt, prompt = prompt_manager.get_chat_prompt(
            "document_classification",
            filename=filename,
            content_type=content_type,
            extraction_confidence=extraction_confidence if extraction_confidence is not None else "",
            structured_context=structured_context,
            extracted_text=(extracted_text or "")[:12000],
        )
        
        from app.services.audit_service import AuditService
        AuditService.log_event(
            job_id=job_id,
            event_type="LLM_CLASSIFICATION_PROMPT",
            payload={"system_prompt": system_prompt, "user_prompt": prompt}
        )

        response = self.llm.generate(prompt, system_prompt=system_prompt)
        
        AuditService.log_event(
            job_id=job_id,
            event_type="LLM_CLASSIFICATION_OUTPUT",
            payload={"raw_output": response}
        )


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
        job_id: Optional[str] = None,
    ) -> str:

        """
        Generates a 100% human-grade professional summary.
        """
        system_prompt, prompt = prompt_manager.get_chat_prompt(
            "resume_summary",
            extracted_text=extracted_text[:12000],
            industry=industry,
            language=language,
            guidance=guidance,
        )

        print(f"\n--- [LLM PROMPT: SUMMARY] ---\n{prompt[:1000]}...\n")
        from app.services.audit_service import AuditService
        AuditService.log_event(
            job_id=job_id,
            event_type="LLM_SUMMARY_PROMPT",
            payload={"system_prompt": system_prompt, "user_prompt": prompt}
        )

        response = self.llm.generate(prompt, system_prompt=system_prompt)
        
        AuditService.log_event(
            job_id=job_id,
            event_type="LLM_SUMMARY_OUTPUT",
            payload={"raw_output": response}
        )


        print(f"\n--- [LLM RAW RESPONSE: SUMMARY] ---\n{response[:1000]}...\n")
        
        blocks = LlmSanitizer.extract_tagged_blocks(response)
        summary = (
            blocks.get("Summary") or blocks.get("summary") or 
            blocks.get("SUMMARY") or blocks.get("__raw_content__") or 
            LlmSanitizer.clean_text(response)
        )
        
        return summary.strip()

    async def generate_overall_summary(
        self,
        extracted_text: str,
        guidance: str,
        industry: Optional[str] = None,
        template_id: Optional[str] = None,
        template_text: Optional[str] = None,
        language: str = "en",
        job_id: Optional[str] = None,
    ) -> str:
        """
        Generates a pure-text professional summary for the overall resume overview.
        No rich text, no CVML markers.
        """
        system_prompt, prompt = prompt_manager.get_chat_prompt(
            "overall_summary",
            extracted_text=extracted_text[:12000],
            industry=industry,
            template_id=template_id,
            template_text=template_text[:4000] if template_text else None,
            language=language,
            guidance=guidance,
        )

        from app.services.audit_service import AuditService
        AuditService.log_event(
            job_id=job_id,
            event_type="LLM_OVERALL_SUMMARY_PROMPT",
            payload={"system_prompt": system_prompt, "user_prompt": prompt}
        )

        response = self.llm.generate(prompt, system_prompt=system_prompt)
        
        AuditService.log_event(
            job_id=job_id,
            event_type="LLM_OVERALL_SUMMARY_OUTPUT",
            payload={"raw_output": response}
        )

        blocks = LlmSanitizer.extract_tagged_blocks(response)
        summary = (
            blocks.get("Summary") or blocks.get("summary") or 
            blocks.get("SUMMARY") or blocks.get("__raw_content__") or 
            LlmSanitizer.clean_text(response)
        )
        
        # Strip any accidental CVML just in case
        return LlmSanitizer.strip_cvml(summary.strip())

    async def analyze_template_metadata(self, content: bytes, filename: str) -> 'TemplateAnalysisResult':
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
        
        if not (extracted_doc and extracted_doc.extracted_text and extracted_doc.extracted_text.strip()):
            logger.error(f"Extraction failed for {filename}. No text recovered.")
            raise self.TemplateAnalysisError(f"The template {filename} could not be read or is empty. Check parser logs.")
        
        # Retrieve placeholders in EXACT visual order using regex across the whole document text
        import io, re
        
        # Pattern covers << section >>, {{ field }}, [[:B:]] markup, and [field] single brackets
        pattern = r"<<\s*(.*?)\s*>>|\{\{\s*(.*?)\s*\}\}|\[\[\s*(.*?)\s*\]\]|\[\s*([A-Z_]{3,})\s*\]"
        matches = re.finditer(pattern, extracted_doc.extracted_text)
        
        detected_placeholders = []
        for match in matches:
            # Get the first non-None group (the inner text)
            inner_text = next(group for group in match.groups() if group is not None)
            detected_placeholders.append(inner_text.strip())
        
        if not detected_placeholders:
            logger.info(f"Programmatic AI Template Analysis: No markers matched regex in {filename}. Relying on LLM vision/discovery.")
        else:
            logger.info(f"Programmatic AI Template Analysis: Found {len(detected_placeholders)} placeholders: {detected_placeholders}")


        system_prompt, prompt = prompt_manager.get_chat_prompt(
            "template_analysis",
            template_text=extracted_doc.extracted_text[:8000],
            detected_placeholders=detected_placeholders,
            sections=extracted_doc.parsed_document.sections if extracted_doc.parsed_document else [],
            tables=extracted_doc.parsed_document.tables if extracted_doc.parsed_document else []
        )

        # Audit Prompt
        AuditService.log_event(
            job_id=filename,
            event_type="TEMPLATE_ANALYSIS_PROMPT",
            payload={"system_prompt": system_prompt, "user_prompt": prompt},
            entity_type="TemplateAsset"
        )

        from app.schemas.template import TemplateAnalysisResult
        schema = TemplateAnalysisResult.model_json_schema()

        # Provide system prompt and json schema hints for structured generation
        try:
            response = self.llm.generate(
                prompt,
                system_prompt=system_prompt,
                response_format=schema,
                temperature=0.1
            )

            
            AuditService.log_event(
            job_id=filename,
            event_type="TEMPLATE_ANALYSIS_RESPONSE",
            payload={"response": response},
            entity_type="TemplateAsset"
            )
            
        except Exception as e:
            logger.error(f"LLM generation failed during template analysis: {e}")
            raise self.TemplateAnalysisError(f"LLM generation failed: {e}")
        
        # Parse strict JSON
        try:
            result = LlmSanitizer.parse_json_object(response)
            
            # PROACTIVE SANITIZATION: Flatten any dicts into strings before Pydantic validation.
            # The LLM sometimes returns nested objects for fields that must be plain strings.
            import json

            # 1. Top-level guidance fields
            guidance_keys = ["global_guidance", "summary_guidance", "formatting_guidance"]
            for gk in guidance_keys:
                if gk in result and isinstance(result[gk], dict):
                    result[gk] = json.dumps(result[gk], indent=2)
                    logger.warning(f"Flattened dict guidance field '{gk}' in template analysis.")

            # 2. Per-manifest-item string fields
            # These must be plain strings per TemplateAnalysisResult schema
            MANIFEST_STRING_FIELDS = [
                "structure_expectation", "content_expectation", "constraints",
                "ambiguity_note", "field_intent", "source_hints", "meaning",
                "fieldname", "tag", "field_type",
            ]
            manifest_items = result.get("field_extraction_manifest", [])
            if isinstance(manifest_items, list):
                for idx, item in enumerate(manifest_items):
                    if not isinstance(item, dict):
                        continue
                    for field_key in MANIFEST_STRING_FIELDS:
                        val = item.get(field_key)
                        if isinstance(val, dict):
                            item[field_key] = json.dumps(val)
                            logger.warning(
                                f"Flattened dict manifest field '{field_key}' at index {idx} in template analysis."
                            )
                        elif isinstance(val, list):
                            # Join list of strings into a comma-separated string
                            item[field_key] = ", ".join(str(v) for v in val)
                            logger.warning(
                                f"Flattened list manifest field '{field_key}' at index {idx} in template analysis."
                            )

                    
        except ValueError as e:
            # Re-raise as domain error
            raise self.TemplateAnalysisError(str(e))

        from pydantic import ValidationError
        try:
            validated_result = TemplateAnalysisResult.model_validate(result)
            # Manifest length equals placeholder count check (if programmatic markers were found)
            if detected_placeholders and len(validated_result.field_extraction_manifest) != len(detected_placeholders):
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
        self, 
        transformed_data: Dict[str, Any], 
        guidance: str, 
        extracted_text: str = "",
        linearized_data: str = "",
        job_id: Optional[str] = None
    ) -> Dict[str, Any]:

        """
        Uses LLM to perform semantic validation using Tags.
        """
        system_prompt, prompt = prompt_manager.get_chat_prompt(
            "validation",
            transformed_data_json=json.dumps(transformed_data, indent=2),
            extracted_text=extracted_text[:12000],
            linearized_data=linearized_data,
            guidance=guidance,
        )



        from app.services.audit_service import AuditService
        AuditService.log_event(
            job_id=job_id,
            event_type="LLM_VALIDATION_PROMPT",
            payload={"system_prompt": system_prompt, "user_prompt": prompt}
        )

        response = self.llm.generate(prompt, system_prompt=system_prompt)

        AuditService.log_event(
            job_id=job_id,
            event_type="LLM_VALIDATION_OUTPUT",
            payload={"raw_output": response}
        )


        blocks = LlmSanitizer.extract_tagged_blocks(response)
        
        status = blocks.get("STATUS") or blocks.get("status") or "PASS"
        report = blocks.get("REPORT") or blocks.get("report") or "Validation logic missed tags."
        
        return {
            "status": status.upper().strip(), 
            "errors": [report] if "FAIL" in status.upper() else [],
            "report": report
        }


    async def harmonize_data_to_template_style(
        self,
        structured_data: Dict[str, Any],
        template_text: str,
        detected_placeholders: List[str] = None,
        field_manifest: List[Dict[str, Any]] = None,
        formatting_guidance: str = "",
        industry: str = "General Professional",
        summary_guidance: str = "",
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        """
        AI HARMONIZATION: Transforms raw JSON into polished, human-readable prose 
        optimized for Word documents. Strictly prevents technical data dumps.
        """
        import re
        system_prompt, prompt = prompt_manager.get_chat_prompt(

            "data_linearization",
            structured_data_json=json.dumps(structured_data, indent=2),
            detected_placeholders_list=detected_placeholders or [],
            field_extraction_manifest=field_manifest or [],
            template_text_excerpt=template_text[:4000],
            formatting_guidance=formatting_guidance,
            industry=industry,
            summary_guidance=summary_guidance,
        )


        print(f"\n--- [LLM PROMPT: HARMONIZATION] ---\n{prompt[:2000]}...\n")

        from app.services.audit_service import AuditService
        AuditService.log_event(
            job_id=job_id,
            event_type="LLM_HARMONIZATION_PROMPT",
            payload={"system_prompt": system_prompt, "user_prompt": prompt}
        )

        try:
            response = self.llm.generate(prompt, system_prompt=system_prompt)
            
            AuditService.log_event(
                job_id=job_id,
                event_type="LLM_HARMONIZATION_OUTPUT",
                payload={"raw_output": response}
            )

            print(f"\n--- [LLM RAW RESPONSE: HARMONIZATION] ---\n{response[:2000]}...\n")

            
            # 1. CORE STRATEGY: Tagged Block Extraction
            harmonized_data = LlmSanitizer.extract_tagged_blocks(response)
            
            # 2. META-TALK SCRUBBING: Total suppression of AI reasoning/residue
            meta_talk_patterns = [
                r'(?i)\(no .*? provided\)',
                r'(?i)Note: .*? remain empty',
                r'(?i)No .*? found in source',
                r'(?i)Since no .*? data exists',
                r'(?i)This section has been left blank',
                r'(?i)The following .*? is blank',
                r'(?i)There is no .*? listed',
                r'(?i)candidate has not provided'
            ]
            
            clean_data = {}
            for k, v in harmonized_data.items():
                if not isinstance(v, str):
                    clean_data[k] = v
                    continue
                    
                cur_val = v
                # Remove common empty-section indicators
                for pattern in meta_talk_patterns:
                    cur_val = re.sub(pattern, '', cur_val, flags=re.IGNORECASE).strip()
                
                # Clean up tiny residue like ":" or "(): "
                if len(cur_val) < 5 and any(c in cur_val for c in "(): "):
                    cur_val = ""
                    
                clean_data[k] = cur_val

            if not clean_data:
                logger.error("AI harmonization FAILED to return any markers.")
                return structured_data

            return clean_data


        except Exception as e:
            logger.error(f"Critical failure in harmonization node: {e}")
            logger.warning("Falling back to raw structured_data — document will still render.")
            return structured_data
