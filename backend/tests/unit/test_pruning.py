from unittest.mock import MagicMock, patch
import pytest
import json

from app.template_analysis.models import TemplateEvidence, TemplateManifest
from app.template_analysis.evidence_normalizer import normalize_evidence_with_model, build_evidence_normalization_prompt
from app.template_analysis.llm_manifest_generator import generate_manifest_with_llm, build_manifest_generation_prompt
from app.template_analysis.manifest_repair import repair_manifest_with_model, build_manifest_repair_prompt
from app.template_analysis.manifest_critic import review_manifest_with_critic, build_manifest_critic_prompt

@pytest.fixture
def dummy_evidence():
    return TemplateEvidence(
        placeholder_candidates=[],
        section_candidates=[],
        tables=[],
        raw_structure={"extremely_verbose_key": "some XML data"},
        raw_text_summary="This is sequential plain text summary",
        docling_markdown="# Docling markdown structural text"
    )

@pytest.fixture
def dummy_manifest():
    return TemplateManifest(
        template_id="dummy",
        purpose="Resume Formatting",
        fields=[]
    )

def test_evidence_normalizer_pruning(dummy_evidence):
    prompt = build_evidence_normalization_prompt(dummy_evidence)
    assert "extremely_verbose_key" not in prompt
    assert "raw_structure" not in prompt
    assert "This is sequential plain text summary" not in prompt
    assert "# Docling markdown structural text" not in prompt

@pytest.mark.asyncio
@patch("app.template_analysis.evidence_normalizer.prompt_manager.get_prompt")
async def test_evidence_normalizer_with_model_pruning(mock_get_prompt, dummy_evidence):
    from unittest.mock import AsyncMock
    mock_runtime = MagicMock()
    mock_runtime.generate_text = AsyncMock(return_value="{}")
    
    mock_config = MagicMock()
    mock_config.model_id = "mock-model"
    mock_config.provider = "mock-provider"
    
    await normalize_evidence_with_model(dummy_evidence, mock_runtime, mock_config)
    
    assert mock_get_prompt.called
    kwargs = mock_get_prompt.call_args[1]
    evidence_json = kwargs["evidence_json"]
    assert "extremely_verbose_key" not in evidence_json
    assert "raw_structure" not in evidence_json
    assert "raw_text_summary" not in evidence_json
    assert "docling_markdown" not in evidence_json
    assert kwargs["raw_text_summary"] == "This is sequential plain text summary"
    assert kwargs["docling_markdown"] == "# Docling markdown structural text"

def test_manifest_repair_pruning(dummy_evidence, dummy_manifest):
    prompt = build_manifest_repair_prompt(dummy_evidence, dummy_manifest, [], [])
    assert "extremely_verbose_key" not in prompt
    assert "raw_structure" not in prompt
    assert "raw_text_summary" not in prompt
    assert "docling_markdown" not in prompt

@pytest.mark.asyncio
@patch("app.template_analysis.manifest_repair.prompt_manager.get_prompt")
async def test_manifest_repair_with_model_pruning(mock_get_prompt, dummy_evidence, dummy_manifest):
    from unittest.mock import AsyncMock
    mock_runtime = MagicMock()
    mock_runtime.generate_text = AsyncMock(return_value='{"template_id": "dummy", "purpose": "Resume Formatting", "fields": []}')
    mock_config = MagicMock()
    
    await repair_manifest_with_model(dummy_evidence, dummy_manifest, [], [], mock_runtime, mock_config)
    
    assert mock_get_prompt.called
    kwargs = mock_get_prompt.call_args[1]
    evidence_json = kwargs["evidence_json"]
    assert "extremely_verbose_key" not in evidence_json
    assert "raw_structure" not in evidence_json
    assert "raw_text_summary" not in evidence_json
    assert "docling_markdown" not in evidence_json
    assert kwargs["raw_text_summary"] == "This is sequential plain text summary"
    assert kwargs["docling_markdown"] == "# Docling markdown structural text"

def test_manifest_critic_pruning(dummy_evidence, dummy_manifest):
    prompt = build_manifest_critic_prompt(dummy_evidence, dummy_manifest)
    assert "extremely_verbose_key" not in prompt
    assert "raw_structure" not in prompt
    assert "raw_text_summary" not in prompt
    assert "docling_markdown" not in prompt

@pytest.mark.asyncio
@patch("app.template_analysis.manifest_critic.prompt_manager.get_prompt")
async def test_manifest_critic_with_model_pruning(mock_get_prompt, dummy_evidence, dummy_manifest):
    from unittest.mock import AsyncMock
    mock_runtime = MagicMock()
    mock_runtime.generate_text = AsyncMock(return_value="{}")
    mock_config = MagicMock()
    mock_config.enabled = True
    
    await review_manifest_with_critic(dummy_evidence, dummy_manifest, mock_runtime, mock_config)
    
    assert mock_get_prompt.called
    kwargs = mock_get_prompt.call_args[1]
    evidence_json = kwargs["evidence_json"]
    assert "extremely_verbose_key" not in evidence_json
    assert "raw_structure" not in evidence_json
    assert "raw_text_summary" not in evidence_json
    assert "docling_markdown" not in evidence_json
    assert kwargs["raw_text_summary"] == "This is sequential plain text summary"
    assert kwargs["docling_markdown"] == "# Docling markdown structural text"
