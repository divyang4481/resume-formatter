from app.template_analysis.manifest_enricher import enrich_manifest_from_evidence
from app.template_analysis.models import (
    PlaceholderCandidate,
    TableCandidate,
    TemplateEvidence,
    TemplateField,
    TemplateManifest,
)
from app.template_analysis.manifest_validator import validate_manifest_against_evidence


def test_enricher_adds_missing_fields_and_detailed_contracts():
    evidence = TemplateEvidence(
        placeholder_candidates=[
            PlaceholderCandidate(marker="«CandidateFullName»", candidate_kind="merge_marker", location="document_body"),
            PlaceholderCandidate(marker="«EmployeeEmail»", candidate_kind="merge_marker", location="header_footer"),
            PlaceholderCandidate(marker="[Type text]", candidate_kind="context_placeholder", location="document_body"),
        ],
        tables=[
            TableCandidate(label="Candidate name", marker="«CandidateFullName»", is_blank=False, row_index=0),
            TableCandidate(label="Notice period", marker="", is_blank=True, row_index=1),
        ],
        paste_zones=["Work experience"],
        header_footer_markers=["«EmployeeEmail»"],
        layout_style="mixed",
    )
    manifest = TemplateManifest(
        template_id="sample",
        purpose="Resume formatting",
        fields=[
            TemplateField(
                fieldname="candidate_full_name",
                marker_text="CandidateFullName",
                field_type="scalar",
                meaning="Candidate name",
                confidence=0.9,
            )
        ],
    )

    enriched = enrich_manifest_from_evidence(manifest, evidence)
    fieldnames = {field.fieldname for field in enriched.fields}

    assert "candidate_full_name" in fieldnames
    assert "employee_email" in fieldnames
    assert "notice_period" in fieldnames
    assert "work_experience" in fieldnames
    assert enriched.field_count == len(enriched.fields)
    assert enriched.evidence_summary["marker_count"] == 3
    assert enriched.extraction_contract["resume_fields"]
    assert enriched.injection_contract["targets"]

    candidate_name = next(field for field in enriched.fields if field.fieldname == "candidate_full_name")
    assert candidate_name.marker_text == "«CandidateFullName»"
    assert candidate_name.injection_hints["strategy"] == "replace_marker"
    assert candidate_name.extraction_hints["canonical_fieldname"] == "candidate_full_name"

    employee_email = next(field for field in enriched.fields if field.fieldname == "employee_email")
    assert employee_email.source_kind == "recruiter_input"
    assert employee_email.resume_fillable is False
    assert employee_email.context["appears_in_header_footer"] is True

    errors, _warnings = validate_manifest_against_evidence(enriched, evidence)
    assert errors == []
