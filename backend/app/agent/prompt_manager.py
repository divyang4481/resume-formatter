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
        Loads and renders a single prompt template (User instructions).
        Now supports recursive search in subdirectories.
        """
        if not template_name.endswith(".jinja2"):
            template_name += ".jinja2"
            
        # Try to find the file in subdirectories if not in root
        found_template = None
        
        # 1. Check relative path as provided
        try:
            found_template = self.env.get_template(template_name)
        except:
            # 2. Search in all sub-loaders/directories
            for template in self.env.list_templates():
                if template.endswith(f"/{template_name}") or template == template_name:
                    found_template = self.env.get_template(template)
                    break
        
        if not found_template:
            raise FileNotFoundError(f"Template '{template_name}' not found in any prompt subdirectory.")
            
        return found_template.render(**kwargs)

    def get_chat_prompt(self, feature_name: str, **kwargs) -> tuple[str, str]:
        """
        Loads and renders a dual-part prompt for chat models.
        Automatically resolves subdirectories for '{feature_name}.jinja2' and '{feature_name}_system.jinja2'.
        """
        user_prompt = self.get_prompt(feature_name, **kwargs)
        
        system_prompt = ""
        try:
            # Check if system template exists (feature_name_system)
            system_prompt = self.get_prompt(f"{feature_name}_system", **kwargs)
        except Exception:
            # Fallback to a generic persona
            system_prompt = "You are a professional AI coding and document assistant."
            
        return system_prompt, user_prompt



# Singleton instance for easy access
prompt_manager = PromptManager()
