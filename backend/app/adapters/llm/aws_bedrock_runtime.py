from app.domain.interfaces import LlmRuntimeAdapter
import boto3
from botocore.config import Config
import json
import logging
import random
import time
from typing import Optional
from botocore.exceptions import BotoCoreError, ClientError


logger = logging.getLogger(__name__)

class AwsBedrockLlmRuntime(LlmRuntimeAdapter):
    """
    Adapter for Amazon Bedrock using boto3.
    Requires AWS credentials to be configured in the environment.
    """

    def __init__(
        self,
        model_id: str = "meta.llama3-8b-instruct-v1:0",
        region_name: Optional[str] = None,
        max_retries: int = 8,
        base_backoff_seconds: float = 5.0,
        max_backoff_seconds: float = 90.0,
    ):
        """
        Initializes the Amazon Bedrock runtime.

        Args:
            model_id: The specific foundation model to use. Defaults to Claude 3 Haiku.
            region_name: The AWS region. If not provided, boto3 defaults are used.
        """
        self.model_id = model_id
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        # Disable botocore's own throttling retries so only our backoff loop controls timing.
        boto_config = Config(retries={"max_attempts": 1, "mode": "standard"})
        # Creates a bedrock-runtime client
        if region_name:
            self.client = boto3.client(service_name='bedrock-runtime', region_name=region_name, config=boto_config)
        else:
            self.client = boto3.client(service_name='bedrock-runtime', config=boto_config)

    def _is_retryable_bedrock_error(self, error: Exception) -> bool:
        if isinstance(error, ClientError):
            code = error.response.get("Error", {}).get("Code", "")
            message = error.response.get("Error", {}).get("Message", "")
            retryable_codes = {
                "ThrottlingException",
                "Throttling",
                "TooManyRequestsException",
                "RequestLimitExceeded",
                "ServiceUnavailableException",
                "ModelNotReadyException",
            }
            if code in retryable_codes:
                return True
            if "Too many tokens" in message:
                return True
            return False
        return isinstance(error, BotoCoreError)

    def _invoke_model_with_retry(self, body: str):
        attempts = self.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                return self.client.invoke_model(
                    modelId=self.model_id,
                    body=body,
                )
            except Exception as error:
                if attempt >= attempts or not self._is_retryable_bedrock_error(error):
                    raise

                backoff = min(
                    self.max_backoff_seconds,
                    self.base_backoff_seconds * (2 ** (attempt - 1)),
                )
                # Add jitter to avoid synchronized retries across tasks.
                sleep_for = backoff + random.uniform(0, 0.5)
                logger.warning(
                    "Bedrock invoke throttled/retryable error on attempt %s/%s for model %s. Retrying in %.2fs: %s",
                    attempt,
                    attempts,
                    self.model_id,
                    sleep_for,
                    error,
                )
                time.sleep(sleep_for)

    def _converse_with_retry(self, request_kwargs: dict):
        attempts = self.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                return self.client.converse(**request_kwargs)
            except Exception as error:
                if attempt >= attempts or not self._is_retryable_bedrock_error(error):
                    raise

                backoff = min(
                    self.max_backoff_seconds,
                    self.base_backoff_seconds * (2 ** (attempt - 1)),
                )
                sleep_for = backoff + random.uniform(0, 0.5)
                logger.warning(
                    "Bedrock converse throttled/retryable error on attempt %s/%s for model %s. Retrying in %.2fs: %s",
                    attempt,
                    attempts,
                    self.model_id,
                    sleep_for,
                    error,
                )
                time.sleep(sleep_for)

    @staticmethod
    def _extract_converse_text(response: dict) -> str:
        message = (response or {}).get("output", {}).get("message", {})
        content = message.get("content", [])
        text_parts = []
        for block in content:
            text = block.get("text") if isinstance(block, dict) else None
            if text:
                text_parts.append(text)
        if text_parts:
            return "\n".join(text_parts).strip()
        return ""

    def _generate_legacy_claude_completion(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> str:
        full_prompt = f"{system_prompt}\n\n" if system_prompt else ""
        full_prompt += f"\n\nHuman: {prompt}\n\nAssistant:"
        body = {
            "prompt": full_prompt,
            "max_tokens_to_sample": max_tokens or kwargs.get("max_tokens", 4096),
            "temperature": temperature,
        }
        response = self._invoke_model_with_retry(json.dumps(body))
        response_body = json.loads(response.get('body').read())
        return response_body['completion'].strip()

    def _build_converse_request(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> dict:
        request = {
            "modelId": self.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            "inferenceConfig": {
                "temperature": temperature,
                "maxTokens": max_tokens or kwargs.get("max_tokens", 2048),
            },
        }
        if system_prompt:
            request["system"] = [{"text": system_prompt}]
        return request

    def _fallback_invoke_model(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> str:
        if "amazon.titan" in self.model_id:
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            body = {
                "inputText": full_prompt,
                "textGenerationConfig": {
                    "maxTokenCount": max_tokens or kwargs.get("max_tokens", 4096),
                    "temperature": temperature,
                },
            }
            response = self._invoke_model_with_retry(json.dumps(body))
            response_body = json.loads(response.get('body').read())
            return response_body['results'][0]['outputText'].strip()

        if "meta.llama" in self.model_id:
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            body = {
                "prompt": full_prompt,
                "max_gen_len": max_tokens or kwargs.get("max_tokens", 2048),
                "temperature": temperature,
                "top_p": 0.9,
            }
            response = self._invoke_model_with_retry(json.dumps(body))
            response_body = json.loads(response.get('body').read())
            return response_body['generation'].strip()

        raise

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
        Invokes the Amazon Bedrock model.
        Uses the Converse API where supported.
        """
        # Legacy models that do not support Converse API.
        if "anthropic.claude-v2" in self.model_id or "anthropic.claude-instant-v1" in self.model_id:
            return self._generate_legacy_claude_completion(
                prompt,
                system_prompt,
                temperature,
                max_tokens,
                **kwargs,
            )

        converse_request = self._build_converse_request(
            prompt,
            system_prompt,
            temperature,
            max_tokens,
            **kwargs,
        )

        try:
            response = self._converse_with_retry(converse_request)
            text = self._extract_converse_text(response)
            if text:
                return text
            raise RuntimeError("Bedrock Converse returned an empty response payload")
        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code", "")
            error_message = error.response.get("Error", {}).get("Message", "")
            # Fallback for model IDs that do not yet support Converse in the configured region/account.
            if error_code == "ValidationException" and "converse" in error_message.lower():
                return self._fallback_invoke_model(
                    prompt,
                    system_prompt,
                    temperature,
                    max_tokens,
                    **kwargs,
                )
            raise
