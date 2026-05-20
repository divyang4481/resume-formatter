import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.template_analysis import (
    TemplateAnalysisOrchestrator,
    TemplateDoclingAdapter,
    TemplateEvidenceExtractor,
    TemplateLlmPayloadBuilder,
    TemplateAnalysisPromptBuilder,
    TemplateLlmClient,
    TemplateLlmResponseParser,
    TemplateManifestV2Normalizer,
    TemplateManifestV2Validator
)

@pytest.fixture
def mock_evidence_extractor():
    extractor = MagicMock(spec=TemplateEvidenceExtractor)
    extractor.extract = AsyncMock(return_value={"mock_evidence": True})
    return extractor

@pytest.fixture
def mock_payload_builder():
    builder = MagicMock(spec=TemplateLlmPayloadBuilder)
    builder.build_payload = MagicMock(return_value={"mock_payload": True})
    return builder

@pytest.fixture
def mock_prompt_builder():
    builder = MagicMock(spec=TemplateAnalysisPromptBuilder)
    builder.build_prompt = MagicMock(return_value="mock prompt string")
    return builder

@pytest.fixture
def mock_llm_client():
    client = MagicMock(spec=TemplateLlmClient)
    client.generate_manifest = AsyncMock(return_value="mock llm response")
    return client

@pytest.fixture
def mock_response_parser():
    parser = MagicMock(spec=TemplateLlmResponseParser)
    parser.parse = MagicMock(return_value={"data": {"fields": []}, "parse_status": "success"})
    return parser

@pytest.fixture
def mock_normalizer():
    normalizer = MagicMock(spec=TemplateManifestV2Normalizer)
    normalizer.normalize = MagicMock(return_value={"fields": []})
    return normalizer

@pytest.fixture
def mock_validator():
    validator = MagicMock(spec=TemplateManifestV2Validator)
    validator.validate = MagicMock(return_value={"status": "PASS"})
    return validator

@pytest.mark.asyncio
async def test_orchestrator_sequence(
    mock_evidence_extractor,
    mock_payload_builder,
    mock_prompt_builder,
    mock_llm_client,
    mock_response_parser,
    mock_normalizer,
    mock_validator
):
    orchestrator = TemplateAnalysisOrchestrator(
        evidence_extractor=mock_evidence_extractor,
        payload_builder=mock_payload_builder,
        prompt_builder=mock_prompt_builder,
        llm_client=mock_llm_client,
        response_parser=mock_response_parser,
        normalizer=mock_normalizer,
        validator=mock_validator
    )

    result = await orchestrator.analyze_template(b"fake content", "test.docx", "123")

    mock_evidence_extractor.extract.assert_called_once()
    mock_payload_builder.build_payload.assert_called_once()
    mock_prompt_builder.build_prompt.assert_called_once()
    mock_llm_client.generate_manifest.assert_called_once()
    mock_response_parser.parse.assert_called_once()
    mock_normalizer.normalize.assert_called_once()
    mock_validator.validate.assert_called_once()

    assert "template_manifest_v2" in result
    assert "field_extraction_manifest" in result
    assert "fields" in result
    assert "_validation" in result
