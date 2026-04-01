from app.adapters.base import LlmRuntimeAdapter
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

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Invokes the Google Cloud Vertex AI generative model.
        """
        temperature = kwargs.get("temperature", 0.7)
        max_output_tokens = kwargs.get("max_tokens", 8192)

        generation_config = {
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
        }

        response = self.model.generate_content(
            prompt,
            generation_config=generation_config,
        )

        return response.text.strip()