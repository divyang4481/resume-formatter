from typing import List, Optional
from pydantic import BaseModel
from app.adapters.base import LlmRuntimeAdapter
from app.domain.interfaces import TemplateRepository
from app.schemas.enums import AssetStatus

class TemplateRecommendationResult(BaseModel):
    suggested_industry_id: Optional[str] = None
    suggested_template_id: Optional[str] = None
    allowed_template_ids: List[str] = []
    confidence: Optional[float] = None
    reasoning_summary: Optional[str] = None

class TemplateResolutionService:
    def __init__(self, llm_runtime: LlmRuntimeAdapter, template_repository: TemplateRepository):
        self.llm_runtime = llm_runtime
        self.template_repository = template_repository

    async def recommend_template(
        self,
        extracted_text: str,
        industry_id: Optional[str] = None,
        job_description: Optional[str] = None,
        mode: str = "recruiter_runtime",
    ) -> TemplateRecommendationResult:
        # Fetch available templates
        # For recruiter_runtime, only active templates. For admin, we allow draft if we were testing a specific one,
        # but for guessing we should probably only guess from active, or all if admin?
        # Let's say we guess from all templates if admin, but only ACTIVE if recruiter

        status_filter = AssetStatus.ACTIVE if mode == "recruiter_runtime" else None

        # Simplified: if no specific filtering logic yet, get all templates and filter in python
        all_templates = self.template_repository.list_templates({})

        if status_filter:
            available_templates = [t for t in all_templates if t.status == status_filter]
        else:
            available_templates = all_templates

        if not available_templates:
            return TemplateRecommendationResult(
                suggested_template_id=None,
                allowed_template_ids=[]
            )

        options = []
        allowed_ids = []
        for idx, t in enumerate(available_templates, 1):
            desc = f"for {t.industry} / {t.role_family}" if t.industry else (t.description or "general template")
            if hasattr(t, "notes") and t.notes:
                desc += f". Guidance: {t.notes}"
            options.append(f"{idx}. {t.id} ({desc})")
            allowed_ids.append(t.id)

        template_options_str = "\n        ".join(options)
        default_template = allowed_ids[0]

        prompt = f"""
        Based on the following resume or document text, identify the industry and recommend
        the best template ID for formatting it.

        Available templates:
        {template_options_str}

        Document Text:
        {extracted_text[:2000]} ... (truncated)

        Respond ONLY with the exact Template ID from the list above that best fits this document.
        """

        try:
            response_text = self.llm_runtime.generate(prompt=prompt, temperature=0.0).strip()

            chosen_template = default_template
            # Try to find a matching ID from the available templates
            for t_id in allowed_ids:
                if t_id in response_text:
                    chosen_template = t_id
                    break

            # Basic guessing of industry from template
            guessed_industry = None
            for t in available_templates:
                if t.id == chosen_template:
                    guessed_industry = t.industry or "it"
                    break

            return TemplateRecommendationResult(
                suggested_industry_id=guessed_industry,
                suggested_template_id=chosen_template,
                allowed_template_ids=allowed_ids,
                confidence=0.85
            )
        except Exception as e:
            print(f"Error during template resolution: {e}")
            return TemplateRecommendationResult(
                suggested_template_id=default_template,
                allowed_template_ids=allowed_ids
            )
