from app.domain.interfaces import LlmRuntimeAdapter
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

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        response_format: dict | None = None,
        temperature: float = 0.1,
        max_tokens: int | None = None,
        **kwargs
    ) -> str:
        """
        Invokes the local Ollama model via HTTP request.
        """
        raw = kwargs.get("raw")

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        if system_prompt:
            payload["system"] = system_prompt
        if response_format:
            payload["format"] = response_format
        if raw is not None:
            payload["raw"] = raw

        try:
            with httpx.Client() as client:
                response = client.post(self.endpoint, json=payload, timeout=180.0)
                
                if response.status_code != 200:
                    raise RuntimeError(f"Ollama returned status code {response.status_code}: {response.text}")

                data = response.json()
                result_text = data.get("response", "").strip()
                return result_text

        except httpx.RequestError as exc:
             raise RuntimeError(f"An error occurred while requesting {exc.request.url!r}. Ensure Ollama is running.") from exc
        except Exception as e:
             print(f"Exception during Ollama generation: {e}")
             raise e
