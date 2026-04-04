from app.domain.interfaces import LlmRuntimeAdapter
import google.generativeai as genai
from typing import Any

class GeminiLlmRuntime(LlmRuntimeAdapter):
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        """
        Initializes the Gemini LLM Runtime.
        
        Args:
            api_key: Google Gemini API key.
            model_name: The Gemini model to use (e.g., 'gemini-1.5-pro').
        """
        genai.configure(api_key=api_key)
        self.model_name = model_name
        
        # Initialize the generative model
        self.model = genai.GenerativeModel(self.model_name)

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        response_format: Optional[dict] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Generate text using Google's Gemini API.
        """
        config_args = {"temperature": temperature}
        if response_format:
            config_args["response_mime_type"] = "application/json"

        generation_config = genai.GenerationConfig(**config_args)
        
        full_prompt = f"System: {system_prompt}\n\nUser: {prompt}" if system_prompt else prompt
        
        # Generate the response
        response = self.model.generate_content(
            full_prompt,
            generation_config=generation_config
        )
        
        return response.text
