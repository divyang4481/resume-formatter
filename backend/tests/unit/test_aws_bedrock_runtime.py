import pytest
from app.adapters.llm.aws_bedrock_runtime import AwsBedrockLlmRuntime, _MODEL_TOKEN_CAPS, _FALLBACK_TRIGGER_CODES
from app.config import settings

def test_qwen_token_caps():
    # Verify Qwen model output capacity limits are increased to 32k tokens
    assert _MODEL_TOKEN_CAPS.get("qwen3-235b") == 32768
    assert _MODEL_TOKEN_CAPS.get("qwen") == 32768

def test_fallback_trigger_codes():
    # Verify ValidationException is not trigger code for silent fallbacks
    assert "ValidationException" not in _FALLBACK_TRIGGER_CODES

def test_model_token_cap_method():
    # Verify that the internal capping logic properly resolves qwen models
    # We can instantiate the runtime adapter with dummy values to test internal capping
    runtime = AwsBedrockLlmRuntime(model_id="qwen.qwen3-235b-a22b-2507-v1:0")
    cap = runtime._model_token_cap("qwen.qwen3-235b-a22b-2507-v1:0")
    assert cap == 32768

    cap_legacy = runtime._model_token_cap("qwen-old-model")
    assert cap_legacy == 32768

def test_config_token_caps():
    # Verify the settings have the updated token limits
    assert settings.bedrock_max_output_tokens_template_analysis == 32768
    
    # Verify manifest generator and repair configuration limits
    assert settings.template_analysis_models["manifest_generator"]["max_tokens"] == 32768
    assert settings.template_analysis_models["manifest_repair"]["max_tokens"] == 32768
