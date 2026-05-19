import pytest
from app.agent.nodes.agentic_nodes import create_missing_fields_identification_node

@pytest.mark.asyncio
async def test_missing_fields_node_uses_status():
    node=create_missing_fields_identification_node()
    state={
      "transformed_document_json":{"template_fill_result":{"candidate_name":{"value":"Divyang","status":"extracted"},"notice_period":{"value":None,"status":"needs_user_input"}}},
      "field_extraction_manifest":[{"fieldname":"candidate_name","field_type":"scalar"},{"fieldname":"notice_period","field_type":"scalar"}]
    }
    out=await node(state)
    assert out["missing_fields"]==["notice_period"]
