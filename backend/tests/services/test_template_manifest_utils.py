from app.services.template_manifest_utils import normalize_template_manifest

def test_field_name_is_canonicalized_to_fieldname():
    raw_manifest = {
        "fields": [{"field_name": "candidate_id", "field_type": "scalar"}]
    }
    normalized = normalize_template_manifest(raw_manifest)
    fields = normalized["fields"]
    assert len(fields) == 1
    assert fields[0]["fieldname"] == "candidate_id"
    assert "field_name" not in fields[0]
