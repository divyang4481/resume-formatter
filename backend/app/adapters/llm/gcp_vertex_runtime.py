from app.domain.interfaces import LlmRuntimeAdapter
from typing import Optional

class GcpVertexLlmRuntime(LlmRuntimeAdapter):
    """
    Adapter for GCP Vertex AI using Vertex AI Python SDK.
    Requires `google-cloud-aiplatform` package.
    """

    def __init__(self, project_id: str, location: str, model_name: str = "gemini-1.5-pro-preview-0409"):
        """
        Initializes the Vertex AI runtime.

        Args:
            project_id: The Google Cloud project ID.
            location: The GCP region.
            model_name: The Vertex AI model name.
        """
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel
        except ImportError:
             raise ImportError("The 'google-cloud-aiplatform' package is required for Vertex AI. Install it with `pip install google-cloud-aiplatform`.")

        vertexai.init(project=project_id, location=location)
        self.model = GenerativeModel(model_name)

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
        Invokes the Google Cloud Vertex AI generative model.
        """
        generation_config = {
            "max_output_tokens": max_tokens or kwargs.get("max_tokens", 8192),
            "temperature": temperature,
        }

        if response_format:
            generation_config["response_mime_type"] = "application/json"

        # Note: system instruction supported on gemini-1.5+
        from vertexai.generative_models import Content, Part

        # We can pass system instructions by initializing a new model if needed,
        # or appending to the prompt. Here we append if not supported natively easily via generate_content args.
        full_prompt = f"System: {system_prompt}\n\nUser: {prompt}" if system_prompt else prompt

        response = self.model.generate_content(
            full_prompt,
            generation_config=generation_config,
        )

        return response.text.strip()
