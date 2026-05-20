import json
import logging
import os
import re
import zipfile
import lxml.etree as ET
from typing import Dict, List, Any, Optional

from app.config import settings
from app.agent.prompt_manager import prompt_manager
from app.agent.utils.llm_sanitizer import LlmSanitizer
from app.services.template_manifest_utils import normalize_template_manifest

logger = logging.getLogger(__name__)


class ResumeAiService:
    def __init__(self, llm_adapter, extraction_service=None):
        self.llm = llm_adapter
        self.extraction_service = extraction_service

    async def generate_summary(
        self,
        extracted_text: str,
        guidance: str = "",
        industry: str = None,
        language: str = "en",
    ) -> str:
        """Restored method for worker nodes to generate professional summaries."""
        prompt = f"Summarize the following professional experience into 3 punchy bullet points. Language: {language}. Industry: {industry}.\nGuidance: {guidance}\n\n{extracted_text[:10000]}"

        logger.info("\n" + "=" * 60 + "\n--- GENERATE SUMMARY PROMPT ---\n" + "=" * 60)
        logger.info(prompt)
        logger.info("=" * 60 + "\n")

        try:
            summary = self.llm.generate(prompt)
        except Exception as e:
            logger.critical(
                f"[Summary] CRITICAL FAILURE: LLM summary generation failed: {e}",
                exc_info=True
            )
            raise e

        logger.info(
            "\n" + "=" * 60 + "\n--- GENERATE SUMMARY RESPONSE ---\n" + "=" * 60
        )
        logger.info(summary)
        logger.info("=" * 60 + "\n")

        return summary.strip()

    async def summarize_experience(self, experience_text: str) -> str:
        """Alias for short-form summarization."""
        return await self.generate_summary(experience_text)


    async def analyze_template(self, content: bytes, filename: str) -> Dict[str, Any]:
        from app.services.template_analysis import (
            TemplateAnalysisOrchestrator,
            TemplateDoclingAdapter,
            TemplateEvidenceExtractor,
            TemplateLlmPayloadBuilder,
            TemplateAnalysisPromptBuilder,
            TemplateLlmClient,
            TemplateLlmResponseParser,
            TemplateManifestV2Normalizer,
            TemplateManifestV2Validator
        )

        orchestrator = TemplateAnalysisOrchestrator(
            evidence_extractor=TemplateEvidenceExtractor(
                docling_adapter=TemplateDoclingAdapter(self.extraction_service)
            ),
            payload_builder=TemplateLlmPayloadBuilder(),
            prompt_builder=TemplateAnalysisPromptBuilder(),
            llm_client=TemplateLlmClient(self.llm),
            response_parser=TemplateLlmResponseParser(),
            normalizer=TemplateManifestV2Normalizer(),
            validator=TemplateManifestV2Validator()
        )

        return await orchestrator.analyze_template(content, filename)

    async def harmonize_data_to_template_style(
        self,
        structured_data: Dict[str, Any],
        template_text: str,
        detected_placeholders: List[str],
        field_manifest: List[Dict[str, Any]],
        formatting_guidance: str = "",
        summary_guidance: str = "",
        validation_guidance: str = "",
        analysis_json: str = "",
        extraction_field_groups: Optional[List[List[str]]] = None,
        job_id: str = "N/A",
    ) -> Dict[str, Any]:
        """
        NEW SIMPLIFIED APPROACH:
        1. LLM receives the template manifest + resume facts.
        2. LLM returns the SAME manifest enriched with field_extraction_manifest per field.
        3. Python derives template_fill_result deterministically (no second LLM call).

        Flow:
            LLM → enriched_manifest (fields with field_extraction_manifest)
            Python → template_fill_result (from enriched_manifest)
            Python → filled_template_manifest (same as enriched_manifest, {"fields": [...]})
        """
        # --- Normalise manifest input ---
        manifest_obj = normalize_template_manifest(field_manifest)
        instruction_blocks = manifest_obj.get("instruction_blocks", [])
        field_manifest = manifest_obj.get("fields", [])

        logger.info(
            f"[FieldMapping] START — Manifest has {len(field_manifest)} fields | Job: {job_id}"
        )
        if field_manifest:
            logger.info(f"[FieldMapping] First field sample: {list(field_manifest[0].keys())}")
        else:
            logger.critical(
                "[FieldMapping] CRITICAL: field_manifest is EMPTY. "
                "Check that template_resolution_node stores 'field_extraction_manifest' "
                "in state and that it is not wiped by a subsequent node."
            )

        # --- Raw resume text for LLM evidence ---
        raw_resume_text = ""
        raw_data_for_prompt = {}
        if isinstance(structured_data, dict):
            raw_resume_text = structured_data.get("text", "") or str(
                structured_data.get("raw_data", "")
            )
            raw_data_for_prompt = structured_data.get("raw_data", {})
        elif isinstance(structured_data, str):
            raw_resume_text = structured_data

        structured_data_for_prompt = {
            "raw_data": raw_data_for_prompt,
            "text_length": len(raw_resume_text),
        }

        # --- Convert to FieldMappingNodes and Batch ---
        from app.services.field_mapping_nodes import (
    get_fieldname,

            fields_to_mapping_nodes,
            batch_field_nodes,
            compact_node_for_llm,
            extract_mapped_nodes_from_response,
            make_fallback_mapped_node,
            synthesize_filled_fields_from_nodes
        )

        field_nodes = fields_to_mapping_nodes(field_manifest)
        logger.info(f"[FieldMapping] Normalized manifest fields={len(field_nodes)}")

        node_batches = batch_field_nodes(field_nodes, batch_size=6)
        logger.info(f"[FieldMapping] Prepared {len(node_batches)} node batch(es). batch_size=6 total_nodes={len(field_nodes)}")

        all_mapped_nodes: List[Dict[str, Any]] = []

        def _looks_truncated_json(s: str) -> bool:
            stripped = s.rstrip()
            if not stripped:
                return True
            return not (stripped.endswith("}") or stripped.endswith("]"))

        for idx, node_batch in enumerate(node_batches):
            logger.info(f"[FieldMapping] Node batch {idx + 1}/{len(node_batches)} node_ids={[n.get('node_id') for n in node_batch]}")
            
            compact_nodes = [compact_node_for_llm(n) for n in node_batch]
            field_mapping_nodes_json = json.dumps({"nodes": compact_nodes}, indent=2, default=str)

            prompt = prompt_manager.get_prompt(
                "data_linearization.jinja2",
                structured_data_json=json.dumps(structured_data_for_prompt, indent=2, default=str),
                field_mapping_nodes_json=field_mapping_nodes_json,
                raw_resume_text=raw_resume_text[:6000],
                formatting_guidance=formatting_guidance,
                summary_guidance=summary_guidance,
                validation_guidance=validation_guidance,
                analysis_json=analysis_json,
                recruiter_input_json="{}",
            )

            try:
                system_prompt = prompt_manager.get_prompt("data_mapping_system.jinja2")
            except Exception as se:
                logger.error(f"[FieldMapping] Failed to load system prompt: {se}. Using fallback.")
                system_prompt = (
                    "You are a strict resume-to-template FieldMappingNode mapper. "
                    "Return only valid JSON {'nodes': [...]}. No markdown, no explanation."
                )

            try:
                logger.info(f"[FieldMapping] Sending request for batch {idx + 1} to LLM...")
                response = self.llm.generate(
                    prompt,
                    system_prompt=system_prompt,
                    task_name="data_mapping",
                    temperature=0.0,
                    max_tokens=8192,
                )
            except Exception as llm_err:
                logger.critical(f"[FieldMapping] CRITICAL FAILURE: LLM generation failed for batch {idx + 1}: {llm_err}", exc_info=True)
                raise llm_err

            # Parse the response for this chunk
            mapped_nodes_for_batch = []
            try:
                cleaned = LlmSanitizer.clean_json(response)

                if _looks_truncated_json(cleaned):
                     raise ValueError("LLM node response appears truncated")

                parsed = json.loads(cleaned)
                mapped_nodes_for_batch = extract_mapped_nodes_from_response(parsed)

                if not mapped_nodes_for_batch:
                     raise ValueError("LLM response parsed but no mapped nodes found")

                logger.info(f"[FieldMapping] Batch {idx + 1} parsed successfully. extracted {len(mapped_nodes_for_batch)} nodes.")

            except Exception as parse_err:
                logger.error(
                    f"[FieldMapping] Node batch {idx + 1} failed. Creating fallback nodes. Error={parse_err}",
                    exc_info=True
                )
                mapped_nodes_for_batch = [make_fallback_mapped_node(n) for n in node_batch]

            all_mapped_nodes.extend(mapped_nodes_for_batch)

        logger.info(f"[FieldMapping] Mapped node count={len(all_mapped_nodes)}")

        filled_fields = synthesize_filled_fields_from_nodes(
            original_nodes=field_nodes,
            mapped_nodes=all_mapped_nodes,
        )

        logger.info(f"[FieldMapping] Synthesized filled fields={len(filled_fields)}")

        expected_non_instruction = sum(1 for f in field_manifest if f.get("field_type") != "instruction_block")
        if expected_non_instruction > 0 and len(filled_fields) == 0:
             logger.critical(f"[FieldMapping] CRITICAL: Synthesized 0 filled fields when {expected_non_instruction} expected. Failsafe triggered.")
             filled_fields = synthesize_filled_fields_from_nodes(field_nodes, []) # empty fem for all

        # --- Derive template_fill_result deterministically (no LLM) ---
        template_fill_result = _build_template_fill_result(filled_fields)
        logger.info(f"[FieldMapping] template_fill_result key count={len(template_fill_result)}")

        missing_fields = [
            f["fieldname"]
            for f in filled_fields
            if f.get("field_extraction_manifest", {}).get("status")
            in ("not_found", "needs_user_input")
        ]

        result = {
            "filled_template_manifest": {
                "fields": filled_fields,
                "instruction_blocks": instruction_blocks,
                "missing_fields_requiring_recruiter_or_ats_input": missing_fields,
            },
            "template_fill_result": template_fill_result,
            "missing_fields_requiring_recruiter_or_ats_input": missing_fields,
        }

        return result
    async def linearize_data(
        self, structured_data: Dict[str, Any], template_metadata: Dict[str, Any]
    ) -> str:
        """Linearizes structured resume data into a narrative format (Legacy support)."""
        result = await self.harmonize_data_to_template_style(
            structured_data=structured_data,
            template_text="",
            detected_placeholders=template_metadata.get("expected_fields", "").split(
                ", "
            ),
            field_manifest=template_metadata.get("field_extraction_manifest", []),
        )
        return json.dumps(result)


# ---------------------------------------------------------------------------
# Module-level helpers (pure Python, no LLM)
# ---------------------------------------------------------------------------


def _build_template_fill_result(filled_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deterministically derive template_fill_result from the enriched manifest fields.
    No LLM call — pure Python projection.

    Each entry: { value, marker_text, field_type, confidence, status, field_extraction_manifest }
    """
    result: Dict[str, Any] = {}
    from app.services.field_mapping_nodes import get_fieldname
    for field in filled_fields:
        fieldname = get_fieldname(field)
        if not fieldname:
            continue
        fem = field.get("field_extraction_manifest") or {}
        result[fieldname] = {
            "value": fem.get("value"),
            "marker_text": field.get("marker_text") or ((field.get("render_locator") or {}).get("marker") if isinstance(field.get("render_locator"), dict) else ""),
            "field_type": field.get("field_type", "scalar"),
            "confidence": fem.get("confidence", 0.0),
            "status": fem.get("status", "not_found"),
            "field_extraction_manifest": fem,
        }
    return result
