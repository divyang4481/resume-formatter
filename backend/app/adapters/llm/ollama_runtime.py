from app.domain.interfaces import LlmRuntimeAdapter
import httpx

class LocalOllamaLlmRuntime(LlmRuntimeAdapter):
    """
    Fallback adapter for Local LLM using Ollama (or compatible OpenAI API format).
    """

    def __init__(
        self, 
        model_name: str = "llama3", 
        endpoint: str = "http://localhost:11434/api/generate",
        timeout: int = 120,
        num_predict: int = 2048,
        context_window: int = 8192,
        keep_alive: str = "10m",
        retry_count: int = 2
    ):
        """
        Initializes the local Ollama runtime.

        Args:
            model_name: The Ollama model name to use.
            endpoint: The base URL of the local Ollama API.
            timeout: Request timeout in seconds.
            num_predict: Maximum number of tokens to generate.
            context_window: Size of the context window.
            keep_alive: Duration to keep the model loaded in memory.
            retry_count: Number of times to retry failed requests.
        """
        self.model_name = model_name
        self.endpoint = endpoint
        self.timeout = timeout
        self.num_predict = num_predict
        self.context_window = context_window
        self.keep_alive = keep_alive
        self.retry_count = retry_count

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
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens or self.num_predict,
                "num_ctx": self.context_window
            }
        }

        if system_prompt:
            payload["system"] = system_prompt
        if response_format:
            # Ollama expects "json" as string for format if we want JSON mode
            payload["format"] = "json"
        if raw is not None:
            payload["raw"] = raw

        last_error = None
        for attempt in range(self.retry_count + 1):
            try:
                with httpx.Client() as client:
                    response = client.post(self.endpoint, json=payload, timeout=float(self.timeout))
                    
                    if response.status_code != 200:
                        raise RuntimeError(f"Ollama returned status code {response.status_code}: {response.text}")

                    data = response.json()
                    result_text = data.get("response", "").strip()
                    return result_text

            except (httpx.RequestError, RuntimeError) as exc:
                 last_error = exc
                 print(f"Ollama attempt {attempt + 1} failed: {exc}. Retrying...")
                 continue
            except Exception as e:
                 print(f"Exception during Ollama generation: {e}")
                 raise e
        
        raise RuntimeError(f"Ollama failed after {self.retry_count + 1} attempts. Last error: {last_error}")
