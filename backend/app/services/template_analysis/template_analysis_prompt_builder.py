from app.agent.prompt_manager import prompt_manager

class TemplateAnalysisPromptBuilder:
    def build_prompt(self, payload: dict) -> str:
        """
        Uses the shared prompt_manager to load the template analysis prompt.
        """
        # We merge payload with whatever context the jinja template expects
        return prompt_manager.get_prompt(
            "template_analysis_v2.jinja2",
            payload=payload,
            semantic_discovery_rules=payload.get("template_context", {}).get("semantic_discovery_rules", {})
        )
