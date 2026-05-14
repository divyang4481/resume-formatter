import json
from typing import Any

from .models import TemplateEvidence


def build_evidence_normalization_prompt(evidence: TemplateEvidence) -> str:
    return f"""
You are a document evidence normalizer.

The template may be in any language and any industry.

Your job:
- Keep only information useful for template field manifest generation.
- Do not infer final field names.
- Do not translate original labels.
- Do not remove placeholders.
- Preserve table/paragraph/section locations.
- Summarize long static text.
- Keep structural features.

Return valid JSON only.

Input evidence:
{json.dumps(evidence.model_dump(mode="json"), ensure_ascii=False, indent=2)}
"""


from app.agent.prompt_manager import prompt_manager

async def normalize_evidence_with_model(
    evidence: TemplateEvidence,
    llm_runtime,
    model_config,
) -> dict[str, Any]:
    prompt = prompt_manager.get_prompt(
        "evidence_normalization.jinja2",
        evidence_json=json.dumps(evidence.model_dump(mode="json"), ensure_ascii=False, indent=2)
    )

    # Use the improved llm_runtime which supports model/provider overrides
    response_text = await llm_runtime.generate_text(
        prompt=prompt,
        model_id=model_config.model_id,
        provider=model_config.provider,
        temperature=model_config.temperature,
        max_tokens=model_config.max_tokens,
    )

    try:
        from app.agent.utils.llm_sanitizer import LlmSanitizer
        cleaned_json = LlmSanitizer.clean_json(response_text)
        return json.loads(cleaned_json)
    except Exception:
        # Fallback to returning raw evidence if normalization fails
        return evidence.model_dump(mode="json")
