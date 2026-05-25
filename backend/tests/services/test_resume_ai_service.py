import pytest
from app.services.resume_ai_service import ResumeAiService, _build_template_fill_result

class DummyLLM:
    def __init__(self, responses): self.responses=responses; self.i=0
    def generate(self,*args,**kwargs):
        r=self.responses[self.i]; self.i+=1; return r

MANIFEST=[
    {"fieldname":"candidate_name","field_type":"scalar","marker_text":"«candidate_name»"},
    {"fieldname":"email","field_type":"scalar","marker_text":"«email»"},
    {"fieldname":"skills","field_type":"array_simple","marker_text":"«skills»"},
]

@pytest.mark.asyncio
async def test_harmonize_preserves_manifest_parity():
    llm=DummyLLM(['{"fields":[{"fieldname":"candidate_name","field_extraction_manifest":{"value_type":"scalar","value":"Divyang","status":"extracted","confidence":0.9,"reason":"x","source":{"resume_section":"h","evidence":"e"}}}]}'])
    svc=ResumeAiService(llm)
    out=await svc.harmonize_data_to_template_style({},"",[],MANIFEST)
    assert len(out["filled_template_manifest"]["fields"])==3
    assert len(out["template_fill_result"].keys())==3
    assert out["template_fill_result"]["email"]["status"]=="not_found"

@pytest.mark.asyncio
async def test_harmonize_accepts_filled_template_manifest_wrapper():
    llm=DummyLLM(['{"filled_template_manifest":{"fields":[{"fieldname":"candidate_name","field_extraction_manifest":{"value_type":"scalar","value":"A","status":"extracted","confidence":0.9,"reason":"x","source":{"resume_section":"h","evidence":"e"}}}]}}'])
    svc=ResumeAiService(llm)
    out=await svc.harmonize_data_to_template_style({},"",[],MANIFEST)
    assert out["template_fill_result"]["candidate_name"]["value"]=="A"

@pytest.mark.asyncio
async def test_harmonize_accepts_template_fill_result_wrapper():
    llm=DummyLLM(['{"template_fill_result":{"candidate_name":{"value":"Divyang Panchasara","status":"extracted","confidence":0.95}}}'])
    svc=ResumeAiService(llm)
    out=await svc.harmonize_data_to_template_style({},"",[],MANIFEST)
    assert out["template_fill_result"]["candidate_name"]["status"]=="extracted"

def test_build_template_fill_result_complete():
    filled=[
      {"fieldname":"candidate_name","field_type":"scalar","marker_text":"","field_extraction_manifest":{"value":"A","confidence":0.8,"status":"extracted"}},
      {"fieldname":"notice_period","field_type":"scalar","marker_text":"","field_extraction_manifest":{"value":None,"confidence":0.0,"status":"not_found"}},
    ]
    out=_build_template_fill_result(filled)
    assert set(out.keys())=={"candidate_name","notice_period"}
    assert out["notice_period"]["status"]=="not_found"

@pytest.mark.asyncio
async def test_harmonize_injects_candidate_own_cv_passthrough():
    llm=DummyLLM(['{"nodes":[{"node_id":"skills","fieldname":"skills","field_extraction_manifest":{"value_type":"array_simple","value":["AWS"],"status":"extracted","confidence":0.9,"reason":"x","source":{"resume_section":"Skills","evidence":"AWS"}}}]}'])
    svc=ResumeAiService(llm)
    manifest=[
        {"fieldname":"skills","field_type":"array_simple","source_kind":"resume_fact"},
        {"fieldname":"candidate_own_cv","field_type":"paste_zone","source_kind":"raw_resume_passthrough"},
    ]
    out=await svc.harmonize_data_to_template_style({"text":"Skills:\nAWS\nPython"},"",[],manifest)
    assert out["template_fill_result"]["skills"]["value"]==["AWS"]
    assert out["template_fill_result"]["candidate_own_cv"]["status"]=="passthrough"
    assert "Skills:\nAWS\nPython" in out["template_fill_result"]["candidate_own_cv"]["value"]
