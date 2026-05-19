from app.services.render_context_builder import build_render_context_from_template_fill_result

def test_render_context_builder_fallback_to_filled_manifest():
    manifest=[{"fieldname":"candidate_name","field_type":"scalar","marker_text":"«Candidate»"},{"fieldname":"email","field_type":"scalar","marker_text":"«Email»"}]
    filled=[{"fieldname":"candidate_name","field_extraction_manifest":{"value":"Divyang"}},{"fieldname":"email","field_extraction_manifest":{"value":"a@b.com"}}]
    out=build_render_context_from_template_fill_result({},manifest,filled)
    assert out["candidate_name"]=="Divyang"
    assert out["email"]=="a@b.com"
