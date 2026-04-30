from typing import Dict, Any
from app.agent.state import AgentState
from app.domain.interfaces import LlmRuntimeAdapter
from app.agent.utils.llm_sanitizer import LlmSanitizer
from app.agent.prompt_manager import prompt_manager
import json
import logging

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


def create_resume_to_template_mapping_node():
    """
    Node that uses Agentic Core to map parsed resume data to the template contract.
    """
    async def resume_to_template_mapping_node(state: AgentState) -> dict:
        logger.info("Executing Resume to Template Mapping Node...")
        
        extracted_text = state.get("extracted_text", "")
        raw_parsed_data = state.get("raw_parsed_data") or {}
        template_contract = state.get("canonical_model") or {}
        formatting_guidance = state.get("formatting_guidance") or ""
        
        # Format structured metadata (tables/sections)
        structured_context = ""
        if raw_parsed_data:
            sections = raw_parsed_data.get("sections", [])
            tables = raw_parsed_data.get("tables", [])
            if sections:
                structured_context += "\nDETECTED SECTIONS:\n" + "\n".join([f"- {s.get('title')}" for s in sections])
            if tables:
                structured_context += f"\nDETECTED TABLES: {len(tables)} tables found."

        from app.dependencies import get_agent_provider
        agent = get_agent_provider()

        try:
            mapped_data = agent.map_resume_to_template(
                parsed_resume={"text": extracted_text, "structured_context": structured_context},
                template_contract=template_contract,
                template_rules={"formatting_guidance": formatting_guidance},
                pii_policy={},
                job_context={"job_id": state.get("session_id", "default")}
            )
            # Store as string if needed, or keep dict
            return {
                "transformed_document_json": mapped_data,
                "status": "extracted"
            }
        except Exception as e:
            logger.error(f"Mapping node failed: {e}")
            return {"status": "extraction_error"}

    return resume_to_template_mapping_node
