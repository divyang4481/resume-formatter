"""Tests for ValidationAgent."""

from __future__ import annotations

import pytest

from resume_formatter.agents.validation_agent import ValidationAgent
from resume_formatter.models import ContactInfo, Education, Resume, Skill, WorkExperience


def _full_resume() -> Resume:
    return Resume(
        contact=ContactInfo(
            name="Bob Builder",
            email="bob@example.com",
            phone="+44 20 7946 0958",
        ),
        summary="Skilled professional.",
        experience=[
            WorkExperience(title="Engineer", company="Widgets Ltd", start_date="2020", end_date="Present")
        ],
        education=[Education(institution="Uni", degree="BSc Computer Science")],
        skills=[Skill(name="Python"), Skill(name="SQL")],
    )


class TestValidationAgent:
    def setup_method(self):
        self.agent = ValidationAgent()

    def test_valid_resume_passes(self):
        report = self.agent.validate(_full_resume())
        assert report.is_valid
        assert not report.errors

    def test_missing_name_is_error(self):
        resume = _full_resume()
        resume.contact.name = ""
        report = self.agent.validate(resume)
        assert not report.is_valid
        error_fields = [e.field for e in report.errors]
        assert "contact.name" in error_fields

    def test_invalid_email_is_error(self):
        resume = _full_resume()
        resume.contact.email = "not-an-email"
        report = self.agent.validate(resume)
        assert not report.is_valid
        error_fields = [e.field for e in report.errors]
        assert "contact.email" in error_fields

    def test_short_phone_is_error(self):
        resume = _full_resume()
        resume.contact.phone = "123"
        report = self.agent.validate(resume)
        assert not report.is_valid

    def test_no_experience_is_warning(self):
        resume = _full_resume()
        resume.experience = []
        report = self.agent.validate(resume)
        assert report.is_valid  # warnings don't fail validation
        warning_fields = [w.field for w in report.warnings]
        assert "experience" in warning_fields

    def test_no_education_is_warning(self):
        resume = _full_resume()
        resume.education = []
        report = self.agent.validate(resume)
        assert report.is_valid
        warning_fields = [w.field for w in report.warnings]
        assert "education" in warning_fields

    def test_no_skills_is_warning(self):
        resume = _full_resume()
        resume.skills = []
        report = self.agent.validate(resume)
        assert report.is_valid
        warning_fields = [w.field for w in report.warnings]
        assert "skills" in warning_fields

    def test_linkedin_without_https_is_warning(self):
        resume = _full_resume()
        resume.contact.linkedin = "linkedin.com/in/bob"
        report = self.agent.validate(resume)
        assert report.is_valid  # warning only
        warning_fields = [w.field for w in report.warnings]
        assert "contact.linkedin" in warning_fields

    def test_report_str_ok(self):
        report = self.agent.validate(_full_resume())
        assert "OK" in str(report)

    def test_report_str_with_errors(self):
        resume = _full_resume()
        resume.contact.name = ""
        report = self.agent.validate(resume)
        assert "ERROR" in str(report)
