from dataclasses import dataclass
from typing import Optional, Dict, Any

from .model_roles import TemplateAnalysisModelRole


@dataclass(frozen=True)
class ModelInvocationConfig:
    provider: str
    model_id: str
    temperature: float = 0.0
    max_tokens: int = 8000
    enabled: bool = True


class TemplateAnalysisModelRouter:
    def __init__(self, settings):
        self.settings = settings

    def get_model_config(
        self,
        role: TemplateAnalysisModelRole,
        complexity_score: Optional[float] = None,
    ) -> ModelInvocationConfig:
        """
        Return model config for a given template-analysis role.

        complexity_score can later be used to route simple templates to smaller models
        and complex templates to stronger models.
        """
        # Resolve the model config from settings.
        # We expect settings.template_analysis_models to be a dict of roles to configs.
        template_analysis_models = getattr(self.settings, "template_analysis_models", {})
        
        config = template_analysis_models.get(role.value)

        if not config:
            # Fallback to defaults if role not found in explicit map
            logger_warning_triggered = False
            try:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"No model config found for role: {role.value}. Falling back to defaults.")
                logger_warning_triggered = True
            except:
                pass

            # Fallback logic: Use default bedrock settings
            return ModelInvocationConfig(
                provider="aws_bedrock",
                model_id=self.settings.bedrock_default_model_id or self.settings.llm_model_name,
                temperature=0.0,
                max_tokens=8000
            )

        return ModelInvocationConfig(**config)
