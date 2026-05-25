import pytest
import json
from app.services.resume_ai_service import ResumeAiService

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

# Raw data from log evidence
raw_llm_response = {
  "fields": [
    {
      "field_name": "candidate_id",
      "marker_text": "«CandidateID»",
      "field_type": "scalar",
      "source_kind": "resume_fact",
      "render_locator": {
        "strategy": "fill_blank_cell_after_label",
        "marker_text": "«CandidateID»",
        "label": "Candidate",
        "heading": ""
      },
      "meaning": "Unique identifier assigned to the candidate in the Hays system",
      "source_hints": "Table row with label 'Candidate', Appears multiple times in document",
      "required": True,
      "confidence": 1.0,
      "occurrence_index": 1,
      "canonical_fieldname": "candidate_id",
      "original_label": "Candidate",
      "context": {
        "location": "document_body",
        "candidate_kind": "merge_marker",
        "context_snippet": "Table label: Candidate; blank value cell: False",
        "table_label": "Candidate",
        "is_blank_table_slot": False,
        "related_headings": [],
        "appears_in_header_footer": False
      },
      "extraction_hints": {
        "resume_sections": [],
        "labels": [
          "Candidate"
        ],
        "format": "alphanumeric code",
        "canonical_fieldname": "candidate_id",
        "source_kind": "resume_fact"
      },
      "injection_hints": {
        "strategy": "fill_blank_cell_after_label",
        "label": "Candidate",
        "marker_text": "«CandidateID»"
      },
      "provenance": {
        "source": "raw_evidence",
        "evidence_type": "merge_marker",
        "exact_marker_found": True
      },
      "sub_fields": [],
      "field_extraction_manifest": {
        "value_type": "scalar",
        "value": None,
        "confidence": 0.0,
        "status": "not_found",
        "reason": "Candidate ID is not present in the resume and must be provided by the Hays system or user",
        "source": {
          "resume_section": "",
          "evidence": ""
        }
      }
    },
    {
      "field_name": "expected_salary",
      "marker_text": "«ExpectedSalary»",
      "field_type": "scalar",
      "source_kind": "resume_fact",
      "field_extraction_manifest": {
        "value_type": "scalar",
        "value": None,
        "confidence": 0.0,
        "status": "not_found",
        "reason": "Expected salary is not mentioned in the resume",
        "source": {
          "resume_section": "",
          "evidence": ""
        }
      }
    }
  ]
}

@pytest.mark.asyncio
async def test_harmonize_preserves_log_evidence():
    manifest_fields = [
        {"field_name": "candidate_id", "field_type": "scalar"},
        {"field_name": "expected_salary", "field_type": "scalar"},
        {"field_name": "cv_comments", "field_type": "rich_text"} # Add an unmapped one to test failsafe empty fem
    ]

    responses = [json.dumps(raw_llm_response)]
    llm = DummyLLM(responses)
    svc = ResumeAiService(llm)

    out = await svc.harmonize_data_to_template_style({}, "", [], manifest_fields)

    # 3 total fields processed
    assert len(out["filled_template_manifest"]["fields"]) == 3
    assert len(out["template_fill_result"]) == 3

    # Candidate ID correctly parsed and mapped despite field_name and raw properties in extraction_manifest
    cand_id_field = next((f for f in out["filled_template_manifest"]["fields"] if f["fieldname"] == "candidate_id"), None)
    assert cand_id_field is not None
    assert cand_id_field["field_extraction_manifest"]["status"] == "not_found"

    salary_field = next((f for f in out["filled_template_manifest"]["fields"] if f["fieldname"] == "expected_salary"), None)
    assert salary_field is not None
    assert salary_field["field_extraction_manifest"]["status"] == "not_found"

    # Check cv comments generated the empty fallback
    cv_field = next((f for f in out["filled_template_manifest"]["fields"] if f["fieldname"] == "cv_comments"), None)
    assert cv_field is not None
    assert cv_field["field_extraction_manifest"]["status"] == "not_found"
