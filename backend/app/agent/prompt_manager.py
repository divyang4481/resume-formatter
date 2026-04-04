import os
from jinja2 import Environment, FileSystemLoader, select_autoescape

class PromptManager:
    """
    Manages loading and rendering of LLM prompts from the prompts directory.
    Uses Jinja2 for flexible template interpolation.
    """
    
    def __init__(self):
        # Determine the absolute path to the prompts directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        prompts_path = os.path.join(current_dir, "prompts")
        
        self.env = Environment(
            loader=FileSystemLoader(prompts_path),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def get_prompt(self, template_name: str, **kwargs) -> str:
        """
        Loads and renders a prompt template with the provided context.
        
        Args:
            template_name: The name of the template file (e.g., 'resume_summary.jinja2')
            **kwargs: Context variables for interpolation
            
        Returns:
            The fully rendered prompt string.
        """
        template = self.env.get_template(template_name)
        return template.render(**kwargs)

# Singleton instance for easy access
prompt_manager = PromptManager()
