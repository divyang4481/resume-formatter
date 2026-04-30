import asyncio
from unittest.mock import patch

from app.services.resume_ai_service import ResumeAiService


class StubLlm:
    def __init__(self):
        self.calls = []

    def generate(self, prompt, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        return '{"document_kind": "candidate_document", "confidence": 0.91, "reason": "ok"}'


def test_classify_document_uses_compact_excerpt_for_prompt():
    captured_kwargs = {}
    extracted_text = "START-" + ("A" * 5000) + "-MIDDLE-" + ("B" * 5000) + "-END"
    llm = StubLlm()
    service = ResumeAiService(llm=llm)

    def fake_get_chat_prompt(feature_name, **kwargs):
        captured_kwargs.update(kwargs)
        return "system", "prompt"

    with patch("app.services.resume_ai_service.prompt_manager.get_chat_prompt", side_effect=fake_get_chat_prompt):
        with patch("app.services.audit_service.AuditService.log_event"):
            result = asyncio.run(
                service.classify_document(
                    extracted_text=extracted_text,
                    raw_parsed_data={},
                    filename="resume.pdf",
                    content_type="application/pdf",
                )
            )

    excerpt = captured_kwargs["extracted_text"]
    assert len(excerpt) < 4000
    assert "START-" in excerpt
    assert "-END" in excerpt
    assert "[content omitted for classification]" in excerpt
    assert llm.calls[0]["max_tokens"] == 256
    assert result["document_kind"] == "candidate_document"