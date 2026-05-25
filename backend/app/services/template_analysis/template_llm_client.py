from app.config import settings
from app.agent.prompt_manager import prompt_manager

class TemplateLlmClient:
    def __init__(self, llm_adapter):
        self.llm_adapter = llm_adapter

    async def generate_manifest(self, prompt: str) -> str:
        """
        Calls the underlying Bedrock/LLM adapter to generate the template manifest.
        Does not parse JSON.
        """
        response = self.llm_adapter.generate(
            prompt,
            system_prompt=prompt_manager.get_prompt("template_analysis_system.jinja2"),
            task_name="template_analysis_v2",
            temperature=settings.bedrock_temperature_template_analysis,
            max_tokens=settings.bedrock_max_output_tokens_template_analysis,
        )
        return response
