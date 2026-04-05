import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Import the adapters
from app.adapters.llm.ollama_runtime import LocalOllamaLlmRuntime
from app.adapters.llm.azure_openai_runtime import AzureOpenAiLlmRuntime
from app.adapters.llm.aws_bedrock_runtime import AwsBedrockLlmRuntime
# Note: gcp and gemini might fail to import if their sdks are missing, but we'll mock them or test signatures.
import inspect
from app.domain.interfaces.llm import LlmRuntimeAdapter

def test_all_llm_adapters_have_correct_signature():
    adapters = [
        LocalOllamaLlmRuntime,
        AzureOpenAiLlmRuntime,
        AwsBedrockLlmRuntime
    ]

    # Try importing others if possible
    try:
        from app.adapters.llm.gcp_vertex_runtime import GcpVertexLlmRuntime
        adapters.append(GcpVertexLlmRuntime)
    except ImportError:
        pass

    try:
        from app.adapters.llm.gemini_runtime import GeminiLlmRuntime
        adapters.append(GeminiLlmRuntime)
    except ImportError:
        pass

    for adapter in adapters:
        sig = inspect.signature(adapter.generate)
        params = list(sig.parameters.keys())

        assert 'self' in params
        assert 'prompt' in params
        assert 'system_prompt' in params
        assert 'response_format' in params
        assert 'temperature' in params
        assert 'max_tokens' in params

        # Verify kwargs
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        assert has_kwargs, f"{adapter.__name__} must accept **kwargs"

def test_azure_openai_system_prompt():
    # The AzureOpenAI class is imported inside __init__, so we can patch the openai module
    with patch("openai.AzureOpenAI") as mock_openai:
        mock_client_instance = MagicMock()
        mock_openai.return_value = mock_client_instance
        mock_client_instance.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="response"))]
        )

        adapter = AzureOpenAiLlmRuntime(endpoint="test", api_key="test", deployment_name="test")
        adapter.generate(
            prompt="Hello",
            system_prompt="You are an AI",
            response_format={"type": "object"},
            temperature=0.5
        )

        # Verify call
        mock_client_instance.chat.completions.create.assert_called_once()
        call_kwargs = mock_client_instance.chat.completions.create.call_args.kwargs
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][0]["content"] == "You are an AI"
        assert call_kwargs["messages"][1]["role"] == "user"
        assert call_kwargs["messages"][1]["content"] == "Hello"
        assert call_kwargs["temperature"] == 0.5
        assert call_kwargs["response_format"] == {"type": "json_object"}

def test_aws_bedrock_system_prompt():
    with patch("app.adapters.llm.aws_bedrock_runtime.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client

        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=lambda: b'{"content": [{"text": "response"}]}')
        }

        adapter = AwsBedrockLlmRuntime(model_id="anthropic.claude-3-haiku-20240307-v1:0")
        adapter.generate(
            prompt="Hello",
            system_prompt="You are an AI",
            temperature=0.5
        )

        mock_client.invoke_model.assert_called_once()
        call_kwargs = mock_client.invoke_model.call_args.kwargs

        import json
        body = json.loads(call_kwargs["body"])
        assert body["system"] == "You are an AI"
        assert body["messages"][0]["content"] == "Hello"
        assert body["temperature"] == 0.5
