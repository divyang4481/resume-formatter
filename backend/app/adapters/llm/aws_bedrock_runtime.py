from app.domain.interfaces import LlmRuntimeAdapter
import boto3
import json
from typing import Optional

class AwsBedrockLlmRuntime(LlmRuntimeAdapter):
    """
    Adapter for Amazon Bedrock using boto3.
    Requires AWS credentials to be configured in the environment.
    """

    def __init__(self, model_id: Optional[str] = None, region_name: Optional[str] = None):
        from app.config import settings
        self.model_id = model_id or settings.llm_model_name
        self.region_name = region_name or settings.aws_region
        self.client = boto3.client(service_name='bedrock-runtime', region_name=self.region_name)

    def generate(self, prompt: str, **kwargs) -> str:
        import time
        from botocore.exceptions import ClientError

        system_prompt = kwargs.get("system_prompt", "")
        max_retries = 5
        base_delay = 2

        for attempt in range(max_retries):
            try:
                # Use the Converse API for standard, robust handling of all Bedrock models
                messages = [{"role": "user", "content": [{"text": prompt}]}]
                system = [{"text": system_prompt}] if system_prompt else []
                
                # Determine max tokens based on model limits
                max_tokens = kwargs.get("max_tokens", 4096)
                if "meta.llama3" in self.model_id:
                    max_tokens = min(max_tokens, 2048)
                
                inference_config = {
                    "maxTokens": max_tokens,
                    "temperature": kwargs.get("temperature", 0.5),
                    "topP": kwargs.get("top_p", 0.9)
                }

                response = self.client.converse(
                    modelId=self.model_id,
                    messages=messages,
                    system=system,
                    inferenceConfig=inference_config
                )
                
                return response['output']['message']['content'][0]['text']

            except ClientError as e:
                error_code = e.response['Error']['Code']
                error_message = e.response['Error']['Message']
                request_id = e.response.get('ResponseMetadata', {}).get('RequestId', 'N/A')
                import logging
                logger = logging.getLogger(__name__)

                log_details = f"Model: {self.model_id} | Region: {self.region_name} | RequestID: {request_id}"

                if error_code in ['ThrottlingException', 'ModelStreamErrorException', 'ModelNotReadyException'] and attempt < max_retries - 1:
                    wait_time = base_delay * (2 ** attempt)
                    logger.warning(f"[Bedrock Attempt {attempt+1}/{max_retries}] Throttled: {error_code} - {error_message}. {log_details}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                logger.error(f"[Bedrock Final Error] {error_code}: {error_message}. {log_details}")
                raise e
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"[Bedrock Unexpected Error] {str(e)} | Model: {self.model_id}")
                raise e

