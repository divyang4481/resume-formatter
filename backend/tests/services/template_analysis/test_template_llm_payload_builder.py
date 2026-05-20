import pytest
from app.services.template_analysis.template_llm_payload_builder import TemplateLlmPayloadBuilder

def test_build_payload():
    builder = TemplateLlmPayloadBuilder()
    evidence = {"mock_evidence": True}
    template_context = {"mock_context": True}

    payload = builder.build_payload(evidence, template_context)

    assert payload["task"] == "generate_template_manifest_v2"
    assert payload["template_evidence_package"] == evidence
    assert payload["template_context"] == template_context
    assert "output_schema" in payload
    # Assert actual json schema is injected, not just a string stub
    assert isinstance(payload["output_schema"], dict)
    assert payload["output_schema"].get("title") == "TemplateManifestV2"
    assert len(payload["rules"]) >= 11
    assert any("paste_zone" in rule for rule in payload["rules"])
