from app.services.field_mapping_nodes import (
    fields_to_mapping_nodes,
    batch_field_nodes,
    compact_node_for_llm,
    extract_mapped_nodes_from_response,
    synthesize_filled_fields_from_nodes
)

def test_fields_to_mapping_nodes_preserves_original_field():
    raw_fields = [{"field_name": "candidate_id", "field_type": "scalar", "marker_text": "<<ID>>"}]
    nodes = fields_to_mapping_nodes(raw_fields)
    assert len(nodes) == 1
    node = nodes[0]
    assert node["node_id"] == "candidate_id"
    assert node["fieldname"] == "candidate_id"
    assert "original_field" in node
    assert node["original_field"]["fieldname"] == "candidate_id"
    assert "field_name" not in node["original_field"]

def test_batch_field_nodes_17_by_6():
    nodes = [{"node_id": str(i)} for i in range(17)]
    batches = batch_field_nodes(nodes, batch_size=6)
    assert [len(b) for b in batches] == [6, 6, 5]

def test_extract_mapped_nodes_from_nodes_response():
    parsed = {
        "nodes": [
            {"node_id": "candidate_id", "fieldname": "candidate_id", "field_extraction_manifest": {"status": "extracted"}}
        ]
    }
    extracted = extract_mapped_nodes_from_response(parsed)
    assert len(extracted) == 1
    assert extracted[0]["node_id"] == "candidate_id"
    assert extracted[0]["field_extraction_manifest"]["status"] == "extracted"

def test_synthesize_filled_fields_from_nodes_preserves_manifest_properties():
    original_nodes = [
        {
            "node_id": "candidate_id",
            "fieldname": "candidate_id",
            "field_type": "scalar",
            "original_field": {
                "fieldname": "candidate_id",
                "marker_text": "<<ID>>",
                "render_locator": {"x": 10}
            }
        }
    ]
    mapped_nodes = [
        {
            "node_id": "candidate_id",
            "fieldname": "candidate_id",
            "field_extraction_manifest": {"status": "extracted", "value": "123"}
        }
    ]
    synthesized = synthesize_filled_fields_from_nodes(original_nodes, mapped_nodes)
    assert len(synthesized) == 1
    field = synthesized[0]
    assert field["fieldname"] == "candidate_id"
    assert field["marker_text"] == "<<ID>>"
    assert field["render_locator"] == {"x": 10}
    assert field["field_extraction_manifest"]["value"] == "123"

def test_compact_node_for_llm_includes_extract_and_slots():
    node = {
        "node_id": "skills",
        "fieldname": "skills",
        "field_type": "array_simple",
        "original_field": {
            "extract": {"expected_value_shape": "array[string]", "sub_fields": []},
            "render": {"target_slot_ids": ["slot_skills"]},
            "slots": [{"slot_id": "slot_skills"}],
            "blocks": [],
        },
    }
    compact = compact_node_for_llm(node)
    assert compact["extract"]["expected_value_shape"] == "array[string]"
    assert compact["slots"][0]["slot_id"] == "slot_skills"

def test_fields_to_mapping_nodes_skips_raw_resume_passthrough_paste_zone():
    raw_fields = [
        {"fieldname": "skills", "field_type": "array_simple", "source_kind": "resume_fact"},
        {"fieldname": "candidate_own_cv", "field_type": "paste_zone", "source_kind": "raw_resume_passthrough"},
    ]
    nodes = fields_to_mapping_nodes(raw_fields)
    assert [n["fieldname"] for n in nodes] == ["skills"]
