from app.domain.interfaces import LlmRuntimeAdapter
import boto3
import json
from typing import Optional

class AwsBedrockLlmRuntime(LlmRuntimeAdapter):
    """
    Adapter for Amazon Bedrock using boto3.
    Requires AWS credentials to be configured in the environment.
    """

    def __init__(self, model_id: str = "anthropic.claude-3-haiku-20240307-v1:0", region_name: Optional[str] = None):
        """
        Initializes the Amazon Bedrock runtime.

        Args:
            model_id: The specific foundation model to use. Defaults to Claude 3 Haiku.
            region_name: The AWS region. If not provided, boto3 defaults are used.
        """
        self.model_id = model_id
        # Creates a bedrock-runtime client
        if region_name:
            self.client = boto3.client(service_name='bedrock-runtime', region_name=region_name)
        else:
            self.client = boto3.client(service_name='bedrock-runtime')

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Invokes the Amazon Bedrock model.
        Assumes the Anthropic Messages API format if using Claude 3 models.
        """
        # Determine format based on model family
        if "anthropic.claude-3" in self.model_id:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": kwargs.get("max_tokens", 4096),
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            if "temperature" in kwargs:
                body["temperature"] = kwargs["temperature"]

            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )

            response_body = json.loads(response.get('body').read())
            return response_body['content'][0]['text']

        elif "anthropic.claude-v2" in self.model_id or "anthropic.claude-instant-v1" in self.model_id:
            # Fallback for older Claude Text Completions API
            body = {
                "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
                "max_tokens_to_sample": kwargs.get("max_tokens", 4096)
            }
            if "temperature" in kwargs:
                body["temperature"] = kwargs["temperature"]

            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )
            response_body = json.loads(response.get('body').read())
            return response_body['completion'].strip()

        elif "amazon.titan" in self.model_id:
             body = {
                 "inputText": prompt,
                 "textGenerationConfig": {
                     "maxTokenCount": kwargs.get("max_tokens", 4096),
                     "temperature": kwargs.get("temperature", 0.7)
                 }
             }
             response = self.client.invoke_model(
                 modelId=self.model_id,
                 body=json.dumps(body)
             )
             response_body = json.loads(response.get('body').read())
             return response_body['results'][0]['outputText'].strip()

        else:
            raise NotImplementedError(f"Bedrock model integration format for {self.model_id} is not implemented yet.")
