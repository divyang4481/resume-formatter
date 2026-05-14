import json
from typing import Dict, Any, List

from .models import TemplateEvidence, TemplateManifest, TemplateField


def build_manifest_generation_prompt(
    evidence: TemplateEvidence,
    normalized_evidence: Dict[str, Any]
) -> str:
    return f"""
You are an expert Document Template Architect.
Your task is to generate a comprehensive TemplateManifest JSON for a resume template.

INPUTS:
1. RAW STRUCTURAL EVIDENCE (Ground Truth):
{json.dumps(evidence.model_dump(mode="json"), ensure_ascii=False, indent=2)}

2. NORMALIZED EVIDENCE (Helper Summary):
{json.dumps(normalized_evidence, ensure_ascii=False, indent=2)}

INSTRUCTIONS:
- Use RAW EVIDENCE as the primary source of truth.
- Identify all placeholders and map them to canonical field names.
- Determine the field type (scalar, array_simple, array_complex, table_loop).
- Infer the semantic meaning and provide source hints for resume data extraction.
- Preserve original labels and detect the document language.
- Identify repeat blocks and instruction blocks.
- If a marker is TableStart:X or TableEnd:X, it MUST be a table_loop.

Return ONLY a valid TemplateManifest JSON object.
"""


from app.agent.prompt_manager import prompt_manager

async def generate_manifest_with_llm(
    evidence: TemplateEvidence,
    normalized_evidence: Dict[str, Any],
    llm_runtime,
    model_config,
) -> TemplateManifest:
    prompt = prompt_manager.get_prompt(
        "manifest_generation.jinja2",
        evidence_json=json.dumps(evidence.model_dump(mode="json"), ensure_ascii=False, indent=2),
        normalized_evidence=json.dumps(normalized_evidence, ensure_ascii=False, indent=2)
    )

    response_text = await llm_runtime.generate_text(
        prompt=prompt,
        model_id=model_config.model_id,
        provider=model_config.provider,
        temperature=model_config.temperature,
        max_tokens=model_config.max_tokens,
    )

    from app.agent.utils.llm_sanitizer import LlmSanitizer
    cleaned_json = LlmSanitizer.clean_json(response_text)
    data = json.loads(cleaned_json)
    
    # Add template_id if missing
    if "template_id" not in data:
        data["template_id"] = "auto-generated"
    
    # Add purpose if missing to satisfy Pydantic
    if "purpose" not in data:
        data["purpose"] = "Resume Formatting"
        
    return TemplateManifest.model_validate(data)
