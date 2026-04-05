from app.domain.interfaces import LlmRuntimeAdapter
from typing import Optional
import json

class AzureOpenAiLlmRuntime(LlmRuntimeAdapter):
    """
    Adapter for Azure OpenAI Service.
    Assumes standard Azure OpenAI setup with `openai` python package.
    """

    def __init__(self, endpoint: str, api_key: str, deployment_name: str, api_version: str = "2024-02-15-preview"):
        """
        Initializes the Azure OpenAI runtime.

        Args:
            endpoint: The base URL of the Azure OpenAI endpoint.
            api_key: The Azure OpenAI API key.
            deployment_name: The deployment name for the deployed model (e.g. gpt-4o).
            api_version: Azure OpenAI API version.
        """
        try:
            from openai import AzureOpenAI
        except ImportError:
            raise ImportError("The 'openai' package is required for Azure OpenAI. Install with `pip install openai`.")

        self.deployment_name = deployment_name
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )

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
        Invokes the deployed Azure OpenAI model using Chat Completions API.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        # Merge kwargs
        actual_max_tokens = max_tokens or kwargs.get("max_tokens", 4096)

        # Determine if json schema supported (e.g. gpt-4o), if not fallback to generic json object
        format_kwargs = {}
        if response_format:
            # Note: Azure OpenAI SDK requires specific handling for full JSON Schema vs type='json_object'
            # Here we provide a simple fallback by requesting json_object if any format is specified
            format_kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(
            model=self.deployment_name,
            messages=messages,
            temperature=temperature,
            max_tokens=actual_max_tokens,
            **format_kwargs
        )

        return response.choices[0].message.content.strip()
