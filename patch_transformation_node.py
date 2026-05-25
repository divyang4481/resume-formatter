def update_transformation_node():
    content = """from typing import Dict, Any, List
from app.agent.state import AgentState
from app.domain.interfaces import LlmRuntimeAdapter
from app.agent.utils.llm_sanitizer import LlmSanitizer
from app.agent.prompt_manager import prompt_manager
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

def create_context_aware_extraction_node(llm_runtime: LlmRuntimeAdapter):
    \"\"\"
    The core extraction node that uses all available context (Raw Text + Structured Data + Schema).
    It loops over the field_extraction_manifest to extract data field by field.
    \"\"\"
    async def context_aware_extraction_node(state: AgentState) -> dict:
        logger.info("Executing Context-Aware Extraction Node (Subgraph)...")

        extracted_text = state.get("extracted_text", "")
        raw_parsed_data = state.get("raw_parsed_data") or {}
        template_text = state.get("template_text") or "Not provided"
        formatting_guidance = state.get("formatting_guidance") or ""
        field_manifest: List[Dict[str, Any]] = state.get("field_extraction_manifest") or []

        # Format structured metadata (tables/sections) for the prompt
        structured_context = ""
        if raw_parsed_data:
            sections = raw_parsed_data.get("sections", [])
            tables = raw_parsed_data.get("tables", [])
            if sections:
                structured_context += "\\nDETECTED SECTIONS:\\n" + "\\n".join([f"- {s.get('title')}" for s in sections])
            if tables:
                structured_context += f"\\nDETECTED TABLES: {len(tables)} tables found. Use table content for precise facts like dates and roles."

        if not field_manifest:
            logger.warning("No field manifest found, falling back to legacy dynamic schema behavior.")
            # Fallback legacy behavior if no manifest is present
            expected_fields = state.get("expected_fields") or ""
            fields = [f.strip() for f in expected_fields.split(",") if f.strip()]

            prompt = prompt_manager.get_prompt(
                "context_aware_extraction.jinja2",
                field_name="ALL_FIELDS",
                field_meaning="Extract all standard resume fields",
                source_hints="Extract data for all requested fields",
                target_schema=json.dumps({f: "" for f in fields}, indent=2),
                template_text_excerpt=template_text[:3000],
                structured_context=structured_context,
                extracted_text=extracted_text,
                formatting_guidance=formatting_guidance
            )

            try:
                response = llm_runtime.generate(prompt=prompt, temperature=0.1)
                cleaned = LlmSanitizer.clean_json(response)
                return {
                    "transformed_document_json": cleaned,
                    "status": "extracted"
                }
            except Exception as e:
                logger.error(f"Extraction node failed: {e}")
                return {"status": "extraction_error"}

        # Loop over field manifest
        transformed_data = {}
        logger.info(f"Extracting {len(field_manifest)} fields based on manifest.")

        # We can do this sequentially or concurrently. Doing it sequentially for simplicity and stability,
        # but concurrent could be faster. Let's do it concurrently.

        async def extract_field(field_def: Dict[str, Any]) -> tuple:
            field_name = field_def.get("fieldname", "")
            field_meaning = field_def.get("meaning", "")
            source_hints = field_def.get("source_hints", "")

            prompt = prompt_manager.get_prompt(
                "context_aware_extraction.jinja2",
                field_name=field_name,
                field_meaning=field_meaning,
                source_hints=source_hints,
                target_schema=json.dumps({field_name: ""}, indent=2),
                template_text_excerpt=template_text[:3000],
                structured_context=structured_context,
                extracted_text=extracted_text,
                formatting_guidance=formatting_guidance
            )

            try:
                # Need to use loop.run_in_executor if generate is synchronous, but llm_runtime.generate might be sync
                response = llm_runtime.generate(prompt=prompt, temperature=0.1)
                cleaned = LlmSanitizer.clean_json(response)
                parsed = json.loads(cleaned)
                return (field_name, parsed.get(field_name, parsed))
            except Exception as e:
                logger.error(f"Failed to extract field {field_name}: {e}")
                return (field_name, None)

        # Since llm_runtime.generate is likely synchronous (based on other usages like in ai_service),
        # we'll execute sequentially to avoid blocking the event loop or we can just loop.

        for field_def in field_manifest:
            field_name = field_def.get("fieldname", "")
            field_meaning = field_def.get("meaning", "")
            source_hints = field_def.get("source_hints", "")

            logger.info(f"Extracting field: {field_name}")

            prompt = prompt_manager.get_prompt(
                "context_aware_extraction.jinja2",
                field_name=field_name,
                field_meaning=field_meaning,
                source_hints=source_hints,
                target_schema=json.dumps({field_name: ""}, indent=2),
                template_text_excerpt=template_text[:3000],
                structured_context=structured_context,
                extracted_text=extracted_text,
                formatting_guidance=formatting_guidance
            )

            try:
                response = llm_runtime.generate(prompt=prompt, temperature=0.1)
                cleaned = LlmSanitizer.clean_json(response)
                if cleaned:
                    parsed = json.loads(cleaned)
                    # The LLM might return {"field_name": "value"} or just the value or a list
                    # We will map whatever it returns to the field_name
                    if isinstance(parsed, dict) and field_name in parsed:
                        transformed_data[field_name] = parsed[field_name]
                    else:
                        transformed_data[field_name] = parsed
            except Exception as e:
                logger.error(f"Failed to extract field {field_name}: {e}")
                transformed_data[field_name] = None

        return {
            "transformed_document_json": json.dumps(transformed_data),
            "status": "extracted"
        }

    return context_aware_extraction_node
"""
    with open('backend/app/agent/nodes/transformation_node.py', 'w') as f:
        f.write(content)
    print("Updated transformation_node.py")

update_transformation_node()
