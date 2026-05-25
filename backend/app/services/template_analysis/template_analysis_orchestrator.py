from typing import Dict, Any, Optional
import json

from .template_evidence_extractor import TemplateEvidenceExtractor
from .template_llm_payload_builder import TemplateLlmPayloadBuilder
from .template_analysis_prompt_builder import TemplateAnalysisPromptBuilder
from .template_llm_client import TemplateLlmClient
from .template_llm_response_parser import TemplateLlmResponseParser
from .template_manifest_v2_normalizer import TemplateManifestV2Normalizer
from .template_manifest_v2_validator import TemplateManifestV2Validator

class TemplateAnalysisOrchestrator:
    def __init__(
        self,
        evidence_extractor: TemplateEvidenceExtractor,
        payload_builder: TemplateLlmPayloadBuilder,
        prompt_builder: TemplateAnalysisPromptBuilder,
        llm_client: TemplateLlmClient,
        response_parser: TemplateLlmResponseParser,
        normalizer: TemplateManifestV2Normalizer,
        validator: TemplateManifestV2Validator,
    ):
        self.evidence_extractor = evidence_extractor
        self.payload_builder = payload_builder
        self.prompt_builder = prompt_builder
        self.llm_client = llm_client
        self.response_parser = response_parser
        self.normalizer = normalizer
        self.validator = validator

    def build_template_context(self, content: bytes, filename: str, template_id: Optional[str]) -> Dict[str, Any]:
        return {
            "filename": filename,
            "template_id": template_id,
            "semantic_discovery_rules": {
                "field_naming": {
                    "method": "derive_from_template_text",
                    "preserve_original_label": True,
                    "canonicalize_to": "stable_snake_case",
                    "do_not_translate_original_label": True
                },
                "dedupe_rules": [
                    "no_numbered_suffix_fields",
                    "one_array_field_per_bullet_section",
                    "one_array_complex_per_repeated_sequence",
                    "one_array_field_per_table_loop",
                    "child_placeholders_inside_blocks_are_not_top_level_fields"
                ]
            }
        }

    async def analyze_template(
        self,
        content: bytes,
        filename: str,
        template_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        template_context = self.build_template_context(content, filename, template_id)

        evidence = await self.evidence_extractor.extract(content, filename, template_context)

        llm_payload = self.payload_builder.build_payload(evidence, template_context)

        prompt = self.prompt_builder.build_prompt(llm_payload)

        raw_llm_response = await self.llm_client.generate_manifest(prompt)

        parsed = self.response_parser.parse(raw_llm_response)
        draft_manifest = parsed.get("data", {})

        normalized_manifest = self.normalizer.normalize(draft_manifest, evidence)

        validation_result = self.validator.validate(normalized_manifest, evidence)

        return self.build_final_response(
            manifest=normalized_manifest,
            evidence=evidence,
            validation=validation_result,
            raw_llm_response=raw_llm_response,
        )

    def build_final_response(
        self,
        manifest: dict,
        evidence: dict,
        validation: dict,
        raw_llm_response: str,
    ) -> Dict[str, Any]:
        return {
            "template_manifest_v2": manifest,
            "field_extraction_manifest": self.legacy_fields_adapter(manifest),
            "fields": self.legacy_fields_adapter(manifest),
            "instruction_blocks": manifest.get("instructions", []),
            "_validation": validation,
        }

    def legacy_fields_adapter(self, manifest: dict) -> list:
        """
        Converts TemplateManifestV2 fields to legacy field_extraction_manifest format.
        """
        legacy_fields = []
        for field in manifest.get("fields", []):
            f_type = field.get("field_type", "scalar")
            legacy_field = {
                "fieldname": field.get("fieldname", field.get("field_id", "")),
                "field_type": f_type,
                "source_kind": field.get("source_kind", "generated"),
                "meaning": field.get("meaning", ""),
                "required": field.get("required", False)
            }

            # Simple marker mappings
            slots = [s for s in manifest.get("slots", []) if s.get("owner_field_id") == field.get("field_id")]
            if slots:
                first_slot = slots[0]
                marker = first_slot.get("locator", {}).get("marker_text")
                if marker:
                    legacy_field["marker_text"] = marker
                    legacy_field["render_locator"] = {
                        "strategy": first_slot.get("render_mode", "replace_marker"),
                        "marker_text": marker
                    }

            legacy_fields.append(legacy_field)

        return legacy_fields
