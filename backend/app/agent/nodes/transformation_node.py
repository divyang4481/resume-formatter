from typing import Dict, Any, List
from app.agent.state import AgentState
from app.domain.interfaces import LlmRuntimeAdapter
from app.agent.utils.llm_sanitizer import LlmSanitizer
from app.agent.prompt_manager import prompt_manager
import json
import logging
from app.services.template_manifest_utils import normalize_template_manifest
from app.services.field_mapping_nodes import get_fieldname

logger = logging.getLogger(__name__)

def create_schema_builder_node():
    """
    Node to build the dynamic JSON schema based purely on template requirements.
    No hardcoding: driven by template metadata (expected_fields and expected_sections).
    """
    async def schema_builder_node(state: AgentState) -> dict:
        logger.info("Executing Schema Builder Node (Subgraph)...")
        expected_fields = state.get("expected_fields") or ""
        expected_sections = state.get("expected_sections") or ""
        
        dynamic_schema = {}
        
        # Add required specific fields
        fields = [f.strip() for f in expected_fields.split(",") if f.strip()]
        for f in fields:
            # Normalize key to lower_snake_case for consistent LLM output
            safe_key = f.lower().replace(" ", "_").strip()
            if safe_key:
                dynamic_schema[safe_key] = ""

        # Add mandatory sections
        sections = [s.strip() for s in expected_sections.split(",") if s.strip()]
        for s in sections:
            safe_key = s.lower().replace(" ", "_").strip()
            if safe_key and safe_key not in dynamic_schema:
                # Sections are treated as lists of items (objects) for better semantic mapping
                dynamic_schema[safe_key] = []

        return {"canonical_model": dynamic_schema}
    return schema_builder_node


def create_field_harmonization_node(ai_service=None):
    """
    Node that uses ResumeAiService to map and harmonize parsed resume data 
    to the specific template contract requirements.
    """
    async def field_harmonization_node(state: AgentState) -> dict:
        logger.info("Executing Field Harmonization Node...")
        
        extracted_text = state.get("extracted_text", "")
        raw_parsed_data = state.get("raw_parsed_data") or {}
        template_contract = state.get("canonical_model") or {}
        manifest_obj = normalize_template_manifest(state.get("field_extraction_manifest"))
        field_manifest = manifest_obj.get("fields", [])
        if not field_manifest:
            template_asset_id = state.get("template_asset_id")
            raise ValueError(
                f"Template manifest is empty for template_asset_id={template_asset_id}. "
                "Resume formatting cannot continue because there is no template contract."
            )

        logger.info(f"Harmonization Node: Contract has {len(field_manifest) if isinstance(field_manifest, list) else 0} fields.")
        formatting_guidance = state.get("formatting_guidance") or ""
        summary_guidance = state.get("summary_guidance") or ""
        validation_guidance = state.get("validation_guidance") or ""
        analysis_json = state.get("analysis_json") or ""
        template_text = state.get("template_text") or ""
        runtime_metadata = state.get("runtime_metadata") or {}
        extraction_field_groups = runtime_metadata.get("field_extraction_field_groups")
        
        # If ai_service is not provided, try to get it from dependencies or agent provider (fallback)
        if not ai_service:
            from app.dependencies import get_agent_provider
            agent = get_agent_provider()
            mapped_data = agent.map_resume_to_template(
                parsed_resume={"text": extracted_text, "raw_data": raw_parsed_data},
                template_contract=template_contract,
                template_rules={"formatting_guidance": formatting_guidance},
                pii_policy={},
                job_context={"job_id": state.get("session_id", "default")}
            )
        else:
            # Use the high-fidelity harmonization logic
            detected_placeholders = []
            if isinstance(template_contract, dict):
                detected_placeholders = list(template_contract.keys())
            elif isinstance(template_contract, list):
                detected_placeholders = [get_fieldname(f) for f in template_contract if get_fieldname(f)]

            mapped_data = await ai_service.harmonize_data_to_template_style(
                structured_data={"text": extracted_text, "raw_data": raw_parsed_data},
                template_text=template_text,
                detected_placeholders=detected_placeholders,
                field_manifest=field_manifest,
                formatting_guidance=formatting_guidance,
                summary_guidance=summary_guidance,
                validation_guidance=validation_guidance,
                analysis_json=analysis_json,
                extraction_field_groups=extraction_field_groups,
                job_id=state.get("session_id", "default")
            )
        
        return {
            "transformed_document_json": mapped_data,
            "status": "extracted"
        }

    return field_harmonization_node


def create_document_composition_reasoning_node(ai_service):
    """
    Node that performs the professional phrasing and formatting pass (Composition Intelligence).
    """
    async def document_composition_reasoning_node(state: AgentState) -> dict:
        logger.info("Executing Document Composition Reasoning Node...")
        
        harmonized_data = state.get("transformed_document_json") or {}
        template_text = state.get("template_text") or ""
        # FIX: Get manifest directly from state, as template_metadata might be missing or structured differently
        manifest = state.get("field_extraction_manifest")
        if isinstance(manifest, str):
            try:
                manifest = json.loads(manifest)
            except Exception:
                manifest = []
        manifest = manifest or []
        formatting_guidance = state.get("formatting_guidance") or ""
        field_manifest: List[Dict[str, Any]] = state.get("field_extraction_manifest") or []
        
        composed_data = await ai_service.apply_composition_logic(
            harmonized_data=harmonized_data,
            template_text=template_text,
            manifest=manifest,
            formatting_guidance=formatting_guidance
        )
        
        return {
            "transformed_document_json": composed_data,
            "status": "composed"
        }

    return document_composition_reasoning_node
