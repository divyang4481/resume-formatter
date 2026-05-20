import pytest
from app.services.template_analysis.template_manifest_v2_normalizer import TemplateManifestV2Normalizer

def test_numbered_suffix_cleanup():
    draft_manifest = {
        "fields": [
            {"field_id": "cv_comments_2", "fieldname": "cv_comments_2", "source_kind": "merge_marker", "field_type": "scalar"},
            {"field_id": "professional_qualifications_3", "fieldname": "professional_qualifications_3", "source_kind": "merge_marker", "field_type": "scalar"},
            {"field_id": "current_position", "fieldname": "current_position", "source_kind": "merge_marker", "field_type": "scalar"},
            {"field_id": "current_position_2", "fieldname": "current_position_2", "source_kind": "merge_marker", "field_type": "scalar"}
        ],
        "slots": [],
        "blocks": [],
        "instructions": []
    }

    normalizer = TemplateManifestV2Normalizer()
    normalized = normalizer.normalize(draft_manifest, {})

    fields = normalized["fields"]
    # cv_comments_2 becomes cv_comments
    # professional_qualifications_3 becomes professional_qualifications
    # current_position_2 merged into current_position

    assert len(fields) == 3
    field_ids = [f["field_id"] for f in fields]
    assert "cv_comments" in field_ids
    assert "professional_qualifications" in field_ids
    assert "current_position" in field_ids
    assert "cv_comments_2" not in field_ids
    assert "professional_qualifications_3" not in field_ids

def test_paste_zone():
    evidence = {
        "docx_structure_view": {
            "paste_zones": ["CANDIDATE’S OWN CV"]
        }
    }
    draft_manifest = {
        "fields": [],
        "slots": [],
        "blocks": [],
        "instructions": []
    }

    normalizer = TemplateManifestV2Normalizer()
    normalized = normalizer.normalize(draft_manifest, evidence)

    fields = normalized["fields"]
    assert len(fields) == 1
    assert fields[0]["field_type"] == "paste_zone"
    assert fields[0]["original_heading"] == "CANDIDATE’S OWN CV"

    slots = normalized["slots"]
    assert len(slots) == 1
    assert slots[0]["slot_type"] == "paste_zone"

    instructions = normalized["instructions"]
    assert len(instructions) == 1
    assert instructions[0]["action"] == "remove"
