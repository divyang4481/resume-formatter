from app.adapters.base import LlmRuntimeAdapter
import google.generativeai as genai
from typing import Any

class GeminiLlmRuntime(LlmRuntimeAdapter):
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-pro"):
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

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text using Google's Gemini API.
        """
        temperature = kwargs.get("temperature", 0.7)
        
        generation_config = genai.GenerationConfig(
            temperature=temperature
        )
        
        # Generate the response
        response = self.model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        return response.text
