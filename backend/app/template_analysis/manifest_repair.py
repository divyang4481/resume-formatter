import json
from typing import List

from .models import TemplateEvidence, TemplateManifest


def build_manifest_repair_prompt(
    evidence: TemplateEvidence,
    manifest: TemplateManifest,
    errors: List[str],
    warnings: List[str],
) -> str:
    evidence_dict = evidence.model_dump(mode="json")
    evidence_dict.pop("raw_structure", None)
    evidence_dict.pop("raw_text_summary", None)
    evidence_dict.pop("docling_markdown", None)
    return f"""
You are a Template Manifest Repair Engine.

The manifest below failed validation.

Rules:
1. Fix only issues supported by evidence.
2. Do not invent unsupported fields.
3. Preserve original labels and language.
4. Cover all explicit placeholders.
5. Repeat markers must become repeat_block fields.
6. Instruction blocks must not be resume_fillable=true.
7. Return only the corrected TemplateManifest JSON.

Validation errors:
{json.dumps(errors, ensure_ascii=False, indent=2)}

Validation warnings:
{json.dumps(warnings, ensure_ascii=False, indent=2)}

Original evidence:
{json.dumps(evidence_dict, ensure_ascii=False, indent=2)}

Invalid manifest:
{json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2)}
"""


from app.agent.prompt_manager import prompt_manager

async def repair_manifest_with_model(
    evidence: TemplateEvidence,
    manifest: TemplateManifest,
    errors: List[str],
    warnings: List[str],
    llm_runtime,
    model_config,
) -> TemplateManifest:
    evidence_dict = evidence.model_dump(mode="json")
    evidence_dict.pop("raw_structure", None)
    evidence_dict.pop("raw_text_summary", None)
    evidence_dict.pop("docling_markdown", None)

    prompt = prompt_manager.get_prompt(
        "manifest_repair.jinja2",
        errors_json=json.dumps(errors, ensure_ascii=False, indent=2),
        warnings_json=json.dumps(warnings, ensure_ascii=False, indent=2),
        evidence_json=json.dumps(evidence_dict, ensure_ascii=False, indent=2),
        manifest_json=json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2),
        raw_text_summary=evidence.raw_text_summary or "",
        docling_markdown=evidence.docling_markdown or ""
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
    
    # We might need to handle the case where the LLM returns only the fields list or the whole object
    if "fields" in data and len(data) < 5: # likely just the fields part
         manifest.fields = data["fields"]
         return manifest
         
    return TemplateManifest.model_validate(data)
