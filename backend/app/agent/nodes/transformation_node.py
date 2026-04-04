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
    Driven by the High-IQ field_extraction_manifest (Stage 1).
    """
    async def schema_builder_node(state: AgentState) -> dict:
        logger.info("Executing Schema Builder Node (Subgraph: High-IQ)...")
        manifest_raw = state.get("field_extraction_manifest")
        
        dynamic_schema = {}
        manifest = []
        
        # 1. Load the manifest (JSON list of objects)
        if manifest_raw:
            try:
                if isinstance(manifest_raw, str):
                    manifest = json.loads(manifest_raw)
                else:
                    manifest = manifest_raw
            except:
                logger.warning("Manifest parsing failed in Schema Builder. Falling back to legacy strings.")
        
        # 2. Build schema from Manifest (SMART)
        if manifest:
            for item in manifest:
                meaning = item.get("meaning")
                item_type = item.get("type", "field")
                if not meaning: continue
                
                # Handle nested dot-notation (e.g. personal_information.name)
                parts = meaning.split(".")
                curr = dynamic_schema
                for i, part in enumerate(parts):
                    if i == len(parts) - 1:
                        # Leaf node initialization
                        if part not in curr:
                            curr[part] = [] if item_type == "section" else ""
                    else:
                        # Intermediate node
                        if part not in curr:
                            curr[part] = {}
                        curr = curr[part]
        
        # 3. FALLBACK: Legacy Comma-Separated Logic
        else:
            expected_fields = state.get("expected_fields") or ""
            expected_sections = state.get("expected_sections") or ""
            fields = [f.strip() for f in expected_fields.split(",") if f.strip()]
            for f in fields:
                dynamic_schema[f.lower().replace(" ", "_")] = ""
            sections = [s.strip() for s in expected_sections.split(",") if s.strip()]
            for s in sections:
                dynamic_schema[s.lower().replace(" ", "_")] = []

        return {"canonical_model": dynamic_schema}
    return schema_builder_node


def create_context_aware_extraction_node(llm_runtime: LlmRuntimeAdapter):
    """
    The core extraction node that uses all available context (Raw Text + Structured Data + Schema).
    """
    async def context_aware_extraction_node(state: AgentState) -> dict:
        logger.info("Executing Context-Aware Extraction Node (Subgraph)...")
        
        extracted_text = state.get("extracted_text", "")
        raw_parsed_data = state.get("raw_parsed_data") or {}
        dynamic_schema = state.get("canonical_model") or {}
        template_text = state.get("template_text") or "Not provided"
        formatting_guidance = state.get("formatting_guidance") or ""
        
        # Format structured metadata (tables/sections) for the prompt
        structured_context = ""
        if raw_parsed_data:
            sections = raw_parsed_data.get("sections", [])
            tables = raw_parsed_data.get("tables", [])
            if sections:
                structured_context += "\nDETECTED SECTIONS:\n" + "\n".join([f"- {s.get('title')}" for s in sections])
            if tables:
                structured_context += f"\nDETECTED TABLES: {len(tables)} tables found. Use table content for precise facts like dates and roles."

        # RENDER EXTERNALIZED PROMPT
        manifest = state.get("field_extraction_manifest") or []
        prompt = prompt_manager.get_prompt(
            "context_aware_extraction.jinja2",
            dynamic_schema_json=json.dumps(dynamic_schema, indent=2),
            field_extraction_manifest_json=json.dumps(manifest, indent=2),
            template_text_excerpt=template_text[:3000],
            structured_context=structured_context,
            extracted_text=extracted_text,
            formatting_guidance=formatting_guidance
        )
        
        try:
            # Lower temperature for maximum structural consistency
            response = llm_runtime.generate(prompt=prompt, temperature=0.0)
            cleaned = LlmSanitizer.clean_json(response)
            
            # CRITICAL: Verify JSON integrity BEFORE returning to state
            try:
                json.loads(cleaned)
                logger.info("Extraction Node: Successfully validated AI-generated JSON.")
            except Exception as json_e:
                logger.error(f"Extraction Node: AI produced malformed JSON at Line 70+. Error: {json_e}")
                # Fallback to minimal schema if AI fails
                fallback_data = {
                    "personal_information": {"name": "Candidate (AI JSON Error)"},
                    "professional_summary": extracted_text[:500] + "..."
                }
                cleaned = json.dumps(fallback_data)
                
            return {
                "transformed_document_json": cleaned,
                "status": "extracted"
            }
        except Exception as e:
            logger.error(f"Extraction node failed: {e}")
            return {"status": "extraction_error"}

    return context_aware_extraction_node
