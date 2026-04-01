"""Tests for PrivacyAgent."""

from __future__ import annotations

import pytest

from resume_formatter.agents.privacy_agent import PrivacyAgent, _mask_email, _mask_phone
from resume_formatter.models import ContactInfo, Resume, WorkExperience


def _make_resume(**kwargs) -> Resume:
    contact_data = {
        "name": "Alice Smith",
        "email": "alice@example.com",
        "phone": "+1 (555) 987-6543",
        "linkedin": "https://linkedin.com/in/alice",
        "github": "https://github.com/alice",
    }
    contact_data.update(kwargs.pop("contact", {}))
    return Resume(
        contact=ContactInfo(**contact_data),
        summary=kwargs.pop("summary", "Experienced developer."),
        **kwargs,
    )


class TestMaskHelpers:
    def test_mask_email_standard(self):
        assert _mask_email("alice@example.com") == "a***@example.com"

    def test_mask_email_short_local(self):
        assert _mask_email("a@b.com") == "***@b.com"

    def test_mask_phone_keeps_last_four(self):
        result = _mask_phone("+1 (555) 987-6543")
        assert result.endswith("6543")
        assert "***" in result

    def test_mask_phone_short(self):
        result = _mask_phone("1234567")
        assert result.endswith("4567")


class TestPrivacyAgentScan:
    def setup_method(self):
        self.agent = PrivacyAgent()

    def test_scan_finds_email(self):
        resume = _make_resume()
        report = self.agent.scan(resume)
        email_findings = [v for t, v in report.findings if t == "email"]
        assert "alice@example.com" in email_findings

    def test_scan_finds_phone(self):
        resume = _make_resume()
        report = self.agent.scan(resume)
        assert report.has_pii

    def test_scan_no_pii(self):
        resume = Resume(contact=ContactInfo(name="No PII Person"))
        report = self.agent.scan(resume)
        assert not report.has_pii

    def test_scan_does_not_modify_resume(self):
        resume = _make_resume()
        _ = self.agent.scan(resume)
        assert resume.contact.email == "alice@example.com"


class TestPrivacyAgentMask:
    def setup_method(self):
        self.agent = PrivacyAgent()

    def test_mask_returns_new_resume(self):
        original = _make_resume()
        masked, _ = self.agent.mask(original)
        assert masked is not original

    def test_email_is_masked(self):
        original = _make_resume()
        masked, report = self.agent.mask(original)
        assert masked.contact.email != original.contact.email
        assert "***" in masked.contact.email

    def test_phone_is_masked(self):
        original = _make_resume()
        masked, report = self.agent.mask(original)
        assert "***" in masked.contact.phone

    def test_linkedin_is_masked(self):
        original = _make_resume()
        masked, _ = self.agent.mask(original)
        assert masked.contact.linkedin != original.contact.linkedin

    def test_github_is_masked(self):
        original = _make_resume()
        masked, _ = self.agent.mask(original)
        assert masked.contact.github != original.contact.github

    def test_original_not_modified(self):
        original = _make_resume()
        _, _ = self.agent.mask(original)
        assert original.contact.email == "alice@example.com"

    def test_report_lists_masked_fields(self):
        original = _make_resume()
        _, report = self.agent.mask(original)
        assert "contact.email" in report.masked_fields
        assert "contact.phone" in report.masked_fields

    def test_pii_in_summary_masked(self):
        original = _make_resume(summary="Contact me at hidden@secret.org for details.")
        masked, report = self.agent.mask(original)
        assert "hidden@secret.org" not in masked.summary
        email_findings = [v for t, v in report.findings if t == "email" and "hidden" in v]
        assert len(email_findings) >= 1

    def test_masked_fields_stored_on_resume(self):
        original = _make_resume()
        masked, _ = self.agent.mask(original)
        assert "contact.email" in masked.pii_fields_masked

    def test_resume_with_no_contact_details(self):
        resume = Resume(contact=ContactInfo(name="Ghost User"))
        masked, report = self.agent.mask(resume)
        assert not report.has_pii
        assert masked.contact.name == "Ghost User"
