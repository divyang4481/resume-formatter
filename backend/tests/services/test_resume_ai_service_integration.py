import pytest
from app.services.resume_ai_service import ResumeAiService
import json

class DummyLLM:
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0
        self.prompts = []

    def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return "{}"

@pytest.mark.asyncio
async def test_harmonize_field_node_pipeline_returns_complete_result():
    manifest_fields = [{"field_name": f"field_{i}", "field_type": "scalar"} for i in range(17)]

    # We expect 3 batches (6, 6, 5)
    responses = [
        json.dumps({"nodes": [{"node_id": f"field_{i}", "fieldname": f"field_{i}", "field_extraction_manifest": {"status": "extracted", "value": "val"}} for i in range(6)]}),
        json.dumps({"nodes": [{"node_id": f"field_{i}", "fieldname": f"field_{i}", "field_extraction_manifest": {"status": "extracted", "value": "val"}} for i in range(6, 12)]}),
        json.dumps({"nodes": [{"node_id": f"field_{i}", "fieldname": f"field_{i}", "field_extraction_manifest": {"status": "extracted", "value": "val"}} for i in range(12, 17)]})
    ]

    llm = DummyLLM(responses)
    svc = ResumeAiService(llm)

    out = await svc.harmonize_data_to_template_style({}, "", [], manifest_fields)

    assert llm.call_count == 3
    assert len(out["filled_template_manifest"]["fields"]) == 17
    assert len(out["template_fill_result"]) == 17

@pytest.mark.asyncio
async def test_node_batch_parse_failure_creates_fallback_nodes():
    manifest_fields = [{"field_name": f"field_{i}", "field_type": "scalar"} for i in range(17)]

    # We expect 3 batches (6, 6, 5)
    # Make batch 2 fail by returning truncated JSON
    responses = [
        json.dumps({"nodes": [{"node_id": f"field_{i}", "fieldname": f"field_{i}", "field_extraction_manifest": {"status": "extracted", "value": "val"}} for i in range(6)]}),
        '{"nodes": [{"node_id": "field_6", ', # TRUNCATED
        json.dumps({"nodes": [{"node_id": f"field_{i}", "fieldname": f"field_{i}", "field_extraction_manifest": {"status": "extracted", "value": "val"}} for i in range(12, 17)]})
    ]

    llm = DummyLLM(responses)
    svc = ResumeAiService(llm)

    out = await svc.harmonize_data_to_template_style({}, "", [], manifest_fields)

    assert llm.call_count == 3

    fields = out["filled_template_manifest"]["fields"]
    assert len(fields) == 17
    assert len(out["template_fill_result"]) == 17

    not_found_count = 0
    extracted_count = 0
    for f in fields:
        if f["field_extraction_manifest"]["status"] == "not_found":
            not_found_count += 1
        elif f["field_extraction_manifest"]["status"] == "extracted":
            extracted_count += 1

    assert not_found_count == 6 # Batch 2 failed, creating 6 not_found fallback nodes
    assert extracted_count == 11 # 6 from batch 1, 5 from batch 3
