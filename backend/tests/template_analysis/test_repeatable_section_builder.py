from app.template_analysis.models import TemplateEvidence, TemplateField, TemplateManifest, PlaceholderCandidate, SectionCandidate
from app.template_analysis.repeatable_section_builder import build_repeatable_sections_from_evidence


def _manifest(fields):
    return TemplateManifest(template_id="t1", purpose="test", fields=fields, field_count=len(fields))


def test_generic_project_experience_repeatable_section():
    txt = """PROJECT EXPERIENCE
[Project Name]
[Client]
[Duration]
• \"[Bullet point achievements]\"

[Project Name]
[Client]
[Duration]
• \"[Bullet point achievements]\""" 
    evidence = TemplateEvidence(raw_text_summary=txt, section_candidates=[SectionCandidate(heading="PROJECT EXPERIENCE", level=1)])
    out = build_repeatable_sections_from_evidence(_manifest([]), evidence)
    parent = next(f for f in out.fields if f.fieldname == "project_experience")
    assert parent.field_type == "array_complex"
    assert {s.fieldname for s in parent.sub_fields} >= {"project_name", "client", "duration", "achievements"}


def test_normalization_repeat_block():
    f = TemplateField(fieldname="work_experience", marker_text="[Role]", field_type="repeat_block", meaning="x", render_locator={"strategy": "repeat_block"})
    assert f.field_type == "array_complex"
    assert f.render_locator["strategy"] == "replace_complex_block"


def test_table_loop_not_converted():
    evidence = TemplateEvidence(raw_text_summary="EXPERIENCE\n«TableStart:Experience»\n«Role»\n«Company»\n«TableEnd:Experience»", section_candidates=[SectionCandidate(heading="EXPERIENCE", level=1)], placeholder_candidates=[PlaceholderCandidate(marker="«TableStart:Experience»", candidate_kind="repeat_start", location="body")])
    out = build_repeatable_sections_from_evidence(_manifest([TemplateField(fieldname="experience", marker_text="«TableStart:Experience»", field_type="table_loop", meaning="loop")]), evidence)
    assert out.fields[0].field_type == "table_loop"
