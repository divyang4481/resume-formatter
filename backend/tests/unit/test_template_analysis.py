import pytest
import json
from app.agent.utils.llm_sanitizer import LlmSanitizer
from app.schemas.template import TemplateAnalysisResult

def test_placeholder_extraction_order():
    # Simulate docxtpl get_undeclared_template_variables()
    raw_placeholders = ["Summary", "Experience", "Summary", "Education", "Experience"]

    # The logic we added to resume_ai_service.py
    detected_placeholders = list(dict.fromkeys(raw_placeholders))

    assert detected_placeholders == ["Summary", "Experience", "Education"]

def test_json_parsing_valid():
    text = '{"purpose": "Test", "expected_sections": "A", "field_extraction_manifest": [], "global_guidance": "G"}'
    result = LlmSanitizer.parse_json_object(text)
    assert result == {"purpose": "Test", "expected_sections": "A", "field_extraction_manifest": [], "global_guidance": "G"}

def test_json_parsing_markdown():
    text = '```json\n{"purpose": "Test", "expected_sections": "A", "field_extraction_manifest": [], "global_guidance": "G"}\n```'
    result = LlmSanitizer.parse_json_object(text)
    assert result == {"purpose": "Test", "expected_sections": "A", "field_extraction_manifest": [], "global_guidance": "G"}

def test_json_parsing_invalid():
    text = "Not JSON"
    with pytest.raises(ValueError, match="LLM did not return valid JSON"):
        LlmSanitizer.parse_json_object(text)

def test_schema_validation_valid():
    data = {
        "purpose": "Test",
        "expected_sections": "A",
        "field_extraction_manifest": [
            {
                "fieldname": "Summary",
                "meaning": "M",
                "field_type": "narrative",
                "field_intent": "I",
                "source_hints": "S",
                "content_expectation": "C",
                "structure_expectation": "S",
                "constraints": "C"
            }
        ],
        "global_guidance": "G"
    }
    result = TemplateAnalysisResult.model_validate(data)
    assert len(result.field_extraction_manifest) == 1
    assert result.field_extraction_manifest[0].field_type == "narrative"

def test_schema_validation_invalid_type():
    data = {
        "purpose": "Test",
        "expected_sections": "A",
        "field_extraction_manifest": [
            {
                "fieldname": "Summary",
                "meaning": "M",
                "field_type": "invalid_type",
                "field_intent": "I",
                "source_hints": "S",
                "content_expectation": "C",
                "structure_expectation": "S",
                "constraints": "C"
            }
        ],
        "global_guidance": "G"
    }
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        TemplateAnalysisResult.model_validate(data)

def test_schema_validation_extra_keys():
    data = {
        "purpose": "Test",
        "expected_sections": "A",
        "field_extraction_manifest": [],
        "global_guidance": "G",
        "extra_key": "V"
    }
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        TemplateAnalysisResult.model_validate(data)
