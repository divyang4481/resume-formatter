from app.adapters.base import LlmRuntimeAdapter
import httpx

class LocalOllamaLlmRuntime(LlmRuntimeAdapter):
    """
    Fallback adapter for Local LLM using Ollama (or compatible OpenAI API format).
    """

    def __init__(self, model_name: str = "llama3", endpoint: str = "http://localhost:11434/api/generate"):
        """
        Initializes the local Ollama runtime.

        Args:
            model_name: The Ollama model name to use.
            endpoint: The base URL of the local Ollama API.
        """
        self.model_name = model_name
        self.endpoint = endpoint

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Invokes the local Ollama model via HTTP request.
        """
        temperature = kwargs.get("temperature", 0.7)

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        try:
            with httpx.Client() as client:
                response = client.post(self.endpoint, json=payload, timeout=120.0)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "").strip()

        except httpx.RequestError as exc:
             raise RuntimeError(f"An error occurred while requesting {exc.request.url!r}. Ensure Ollama is running.") from exc
