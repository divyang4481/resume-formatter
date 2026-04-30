from app.domain.interfaces import LlmRuntimeAdapter
import boto3
import json
from typing import Optional

class AwsBedrockLlmRuntime(LlmRuntimeAdapter):
    """
    Adapter for Amazon Bedrock using boto3.
    Requires AWS credentials to be configured in the environment.
    """

    def __init__(self, model_id: str = "meta.llama3-8b-instruct-v1:0", region_name: Optional[str] = None):
        """
        Initializes the Amazon Bedrock runtime.

        Args:
            model_id: The specific foundation model to use. Defaults to Llama 3.
            region_name: The AWS region. If not provided, boto3 defaults are used.
        """
        self.model_id = model_id
        # Creates a bedrock-runtime client
        region_name = region_name or 'us-east-1'
        if region_name:
            self.client = boto3.client(service_name='bedrock-runtime', region_name=region_name)
        else:
            self.client = boto3.client(service_name='bedrock-runtime')

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Invokes the Amazon Bedrock model.
        Assumes the Converse API or direct invoke format for Llama 3 models.
        """
        system_prompt = kwargs.get("system_prompt", "")
        formatted_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        # Determine format based on model family
        if "meta.llama3" in self.model_id or "meta.llama2" in self.model_id:
            # Llama 3 payload format for standard invoke_model
            body = {
                "prompt": formatted_prompt,
                "max_gen_len": kwargs.get("max_tokens", 2048),
                "temperature": kwargs.get("temperature", 0.5),
                "top_p": kwargs.get("top_p", 0.9)
            }

            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )
            response_body = json.loads(response.get('body').read())
            # For Llama models on Bedrock, output is usually under 'generation'
            return response_body.get('generation', '').strip()

        elif "anthropic.claude-3" in self.model_id:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": kwargs.get("max_tokens", 4096),
                "messages": [
                    {
                        "role": "user",
                        "content": formatted_prompt
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
                "prompt": f"\n\nHuman: {formatted_prompt}\n\nAssistant:",
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
                 "inputText": formatted_prompt,
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
