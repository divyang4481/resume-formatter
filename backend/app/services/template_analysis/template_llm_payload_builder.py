from typing import Dict, Any
from .template_manifest_v2_models import TemplateManifestV2

class TemplateLlmPayloadBuilder:
    def build_payload(
        self,
        evidence: dict,
        template_context: dict,
    ) -> dict:
        return {
            "task": "generate_template_manifest_v2",
            "template_context": template_context,
            "template_evidence_package": evidence,
            "output_schema": TemplateManifestV2.model_json_schema(),
            "rules": [
                "Return only valid JSON.",
                "Do not create field names ending in _2, _3, _4.",
                "Do not create duplicate semantic fields.",
                "Do not create top-level fields for loop item markers.",
                "If TableStart/TableEnd exists, create one table_loop slot and one semantic array field.",
                "If a heading has bullet placeholders or empty bullets, create one array_simple field and one bullet_list slot.",
                "If a placeholder pattern repeats under one heading, create one array_complex field and one repeat_block slot.",
                "Instruction text must go into instructions[], not fields[].",
                "Every slot must have exactly one owner_field_id.",
                "Every field render.target_slot_ids must reference existing slots.",
                "Every marker must be covered either by slot locator, item_schema, block_schema, or instruction."
            ]
        }
