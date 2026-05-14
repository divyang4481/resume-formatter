import json
from typing import Dict, Any

from .models import TemplateEvidence, TemplateManifest


def build_manifest_critic_prompt(evidence: TemplateEvidence, manifest: TemplateManifest) -> str:
    return f"""
You are a strict QA reviewer for a DOCX Template Field Manifest.

The template may be in any language and any industry.

Check:
1. Are all placeholders covered?
2. Are generic placeholders mapped using context?
3. Are system/recruiter fields incorrectly marked as resume_fillable?
4. Are instruction blocks handled correctly?
5. Are repeat blocks represented correctly?
6. Are field types appropriate?
7. Are original labels preserved?
8. Are uncertain fields marked unknown_fillable instead of guessed?

Return JSON:
{{
  "approved": true,
  "issues": [
    {{
      "severity": "error|warning",
      "fieldname": "string|null",
      "issue": "string",
      "suggested_fix": "string"
    }}
  ]
}}

Evidence:
{json.dumps(evidence.model_dump(mode="json"), ensure_ascii=False, indent=2)}

Manifest:
{json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2)}
"""


async def review_manifest_with_critic(
    evidence: TemplateEvidence,
    manifest: TemplateManifest,
    llm_runtime,
    model_config,
) -> Dict[str, Any]:
    if not model_config.enabled:
        return {"approved": True, "issues": []}

    prompt = build_manifest_critic_prompt(evidence, manifest)

    response_text = await llm_runtime.generate_text(
        prompt=prompt,
        model_id=model_config.model_id,
        provider=model_config.provider,
        temperature=model_config.temperature,
        max_tokens=model_config.max_tokens,
    )

    from app.agent.utils.llm_sanitizer import LlmSanitizer
    cleaned_json = LlmSanitizer.clean_json(response_text)
    return json.loads(cleaned_json)
