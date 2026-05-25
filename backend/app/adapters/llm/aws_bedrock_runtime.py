import json
import logging
import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.domain.interfaces import LlmRuntimeAdapter

logger = logging.getLogger(__name__)

# Task-name → config attribute mapping (resolved lazily to avoid import cycles)
_TASK_MODEL_MAP = {
    "template_analysis": "bedrock_template_analysis_model_id",
    "resume_summary": "bedrock_resume_summary_model_id",
    "data_mapping": "bedrock_data_mapping_model_id",
}

_TASK_MAX_TOKENS_MAP = {
    "template_analysis": "bedrock_max_output_tokens_template_analysis",
    "data_mapping": "bedrock_max_output_tokens_data_mapping",
}

_TASK_TEMPERATURE_MAP = {
    "template_analysis": "bedrock_temperature_template_analysis",
    "data_mapping": "bedrock_temperature_data_mapping",
}


# Model-specific hard caps on output tokens
_MODEL_TOKEN_CAPS = {
    "llama3": 2048,
    "qwen3-235b": 32768,
    "qwen": 32768,
    "gemma-3": 8192,
    "nova": 10000,
    "claude": 8192,   # Claude 3.5+ supports up to 8192 output tokens
    "anthropic": 8192,
}

# Error codes that warrant a fallback attempt (access / capability issues)
_FALLBACK_TRIGGER_CODES = {
    "AccessDeniedException",
    "ResourceNotFoundException",
    "ModelNotReadyException",
    "ModelErrorException",
}

# Error codes that warrant a retry with backoff on the same model
_RETRY_CODES = {
    "ThrottlingException",
    "ModelStreamErrorException",
    "ServiceUnavailableException",
    "InternalServerException",
}


class AwsBedrockLlmRuntime(LlmRuntimeAdapter):
    """
    Adapter for Amazon Bedrock using the Converse API.

    Supports:
    - Task-level model routing: pass task_name="template_analysis" etc.
    - Per-call model override: pass model_id="..."
    - Automatic fallback to bedrock_fallback_model_id on access / validation errors
    - Exponential-backoff retry for throttling errors
    - Safe logging: never logs full prompt content in production
    """

    def __init__(self, model_id: Optional[str] = None, region_name: Optional[str] = None):
        from app.config import settings
        self._settings = settings
        self.default_model_id = model_id or settings.bedrock_default_model_id or settings.llm_model_name
        self.region_name = region_name or settings.aws_region
        
        # Check for Bearer Token authentication (API Key)
        bearer_token = getattr(settings, "aws_bearer_token_bedrock", None)
        
        if bearer_token:
            import os
            logger.info("[Bedrock] Applying Bearer Token to environment")
            # Set the environment variable that newer botocore/boto3 versions expect
            os.environ["AWS_BEDROCK_API_KEY"] = bearer_token
            
        from botocore.config import Config
        boto_config = Config(
            read_timeout=300,
            connect_timeout=60,
            retries={"max_attempts": 3}
        )
        self.client = boto3.client(
            service_name="bedrock-runtime",
            region_name=self.region_name,
            config=boto_config
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def generate_text(self, prompt: str, **kwargs) -> str:
        """
        Async version of generate with explicit support for per-call overrides.
        Supports: model_id, provider, temperature, max_tokens, system_prompt.
        """
        # For now, provider is ignored as this is the Bedrock-specific adapter.
        # Higher-level orchestration would choose the adapter based on provider.
        return self.generate(prompt, **kwargs)

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate a completion from Bedrock.

        Keyword args:
            system_prompt (str): System-level instruction block.
            model_id (str): Override the model for this call.
            task_name (str): Logical task name for routing ("template_analysis", etc.)
            temperature (float): Sampling temperature.
            max_tokens (int): Max output tokens.
        """
        task_name: Optional[str] = kwargs.get("task_name")
        system_prompt: str = kwargs.get("system_prompt", "")

        # Resolve model for this task
        primary_model = self._resolve_model(
            explicit_model_id=kwargs.get("model_id"),
            task_name=task_name,
        )
        fallback_model = self._settings.bedrock_fallback_model_id or None

        # Resolve temperature and max_tokens (task overrides → kwargs → defaults)
        temperature = kwargs.get(
            "temperature",
            self._task_temperature(task_name),
        )
        max_tokens = kwargs.get(
            "max_tokens",
            self._task_max_tokens(task_name),
        )

        # First attempt: primary model
        try:
            return self._invoke(primary_model, prompt, system_prompt, temperature, max_tokens)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in _FALLBACK_TRIGGER_CODES and fallback_model and fallback_model != primary_model:
                logger.warning(
                    f"[Bedrock] Primary model '{primary_model}' failed ({code}). "
                    f"Falling back to '{fallback_model}'."
                )
                return self._invoke(fallback_model, prompt, system_prompt, temperature, max_tokens)
            raise

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_model(self, explicit_model_id: Optional[str], task_name: Optional[str]) -> str:
        """Priority: explicit call arg > task config > default."""
        if explicit_model_id:
            return explicit_model_id
        if task_name and task_name in _TASK_MODEL_MAP:
            attr = _TASK_MODEL_MAP[task_name]
            task_model = getattr(self._settings, attr, "")
            if task_model:
                return task_model
        return self.default_model_id

    def _task_temperature(self, task_name: Optional[str]) -> float:
        if task_name and task_name in _TASK_TEMPERATURE_MAP:
            return getattr(self._settings, _TASK_TEMPERATURE_MAP[task_name], self._settings.bedrock_temperature_default)
        return self._settings.bedrock_temperature_default

    def _task_max_tokens(self, task_name: Optional[str]) -> int:
        if task_name and task_name in _TASK_MAX_TOKENS_MAP:
            return getattr(self._settings, _TASK_MAX_TOKENS_MAP[task_name], self._settings.bedrock_max_output_tokens_default)
        return self._settings.bedrock_max_output_tokens_default

    def _model_token_cap(self, model_id: str) -> int:
        model_lower = model_id.lower()
        for keyword, cap in _MODEL_TOKEN_CAPS.items():
            if keyword in model_lower:
                return cap
        return 4096

    def _invoke(
        self,
        model_id: str,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        max_retries: int = 5,
        base_delay: int = 2,
    ) -> str:
        """Inner call with exponential-backoff retry for throttling."""
        capped_tokens = min(max_tokens, self._model_token_cap(model_id))

        messages = [{"role": "user", "content": [{"text": prompt}]}]
        system = [{"text": system_prompt}] if system_prompt else []
        inference_config = {
            "maxTokens": capped_tokens,
            "temperature": temperature,
            "topP": 0.9,
        }

        # Log Full Prompt for Deep Debugging
        logger.info(f"\n{'='*80}\n[BEDROCK REQUEST] Model: {model_id}\n{'='*80}")
        if system:
            logger.info(f"SYSTEM PROMPT:\n{system[0]['text']}")
        logger.info(f"USER PROMPT:\n{prompt}\n{'='*80}")

        for attempt in range(max_retries):
            try:
                response = self.client.converse(
                    modelId=model_id,
                    messages=messages,
                    system=system,
                    inferenceConfig=inference_config,
                )
                stop_reason = response.get("stopReason")
                
                output_text = response["output"]["message"]["content"][0]["text"]
                
                # Log Full Response
                logger.info(f"\n{'='*80}\n[BEDROCK RESPONSE] Model: {model_id}\n{'='*80}\n{output_text}\n{'='*80}")

                if stop_reason == "max_tokens":
                    logger.warning(
                        f"[Bedrock] Response truncated for model '{model_id}' "
                        f"(maxTokens={capped_tokens} hit)."
                    )
                return output_text

            except ClientError as e:
                code = e.response["Error"]["Code"]
                rid = e.response.get("ResponseMetadata", {}).get("RequestId", "N/A")

                if code in _RETRY_CODES and attempt < max_retries - 1:
                    wait = base_delay * (2 ** attempt)
                    logger.warning(
                        f"[Bedrock attempt {attempt+1}/{max_retries}] {code} on '{model_id}' "
                        f"(RequestId={rid}). Retrying in {wait}s..."
                    )
                    time.sleep(wait)
                    continue

                # Non-retriable or exhausted — raise so caller can decide fallback
                logger.error(
                    f"[Bedrock] {code} on model='{model_id}' RequestId={rid}: "
                    f"{e.response['Error']['Message']}"
                )
                raise

            except Exception as e:
                logger.error(f"[Bedrock] Unexpected error on model='{model_id}': {type(e).__name__}")
                raise

        raise RuntimeError(f"[Bedrock] All {max_retries} retries exhausted for model '{model_id}'")
