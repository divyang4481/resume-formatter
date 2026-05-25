import pytest
from app.services.template_analysis.template_manifest_v2_validator import TemplateManifestV2Validator

def test_validation_failure_on_duplicate_ids():
    manifest = {
        "fields": [
            {"field_id": "duplicate_id", "fieldname": "first"},
            {"field_id": "duplicate_id", "fieldname": "second"}
        ],
        "slots": [],
        "instructions": []
    }

    validator = TemplateManifestV2Validator()
    result = validator.validate(manifest, {})

    assert result["status"] == "FAIL"
    assert any("Duplicate field_id" in err for err in result["errors"])

def test_validation_failure_on_numbered_suffix():
    manifest = {
        "fields": [
            {"field_id": "current_position_2", "fieldname": "current_position_2"}
        ],
        "slots": [],
        "instructions": []
    }

    validator = TemplateManifestV2Validator()
    result = validator.validate(manifest, {})

    assert result["status"] == "FAIL"
    assert any("numbered suffix" in err for err in result["errors"])

def test_warning_on_unscoped_generic_placeholder_slot():
    manifest = {
        "fields": [{"field_id": "skills", "fieldname": "skills"}],
        "slots": [{
            "slot_id": "slot_skills_1",
            "owner_field_id": "skills",
            "locator": {"marker_text": "[Type text]"}
        }],
        "instructions": []
    }
    validator = TemplateManifestV2Validator()
    result = validator.validate(manifest, {})
    assert any("generic placeholder" in w for w in result["warnings"])
