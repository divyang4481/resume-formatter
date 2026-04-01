"""Tests for NormalizationAgent."""

from __future__ import annotations

import textwrap

import pytest

from resume_formatter.agents.normalization_agent import NormalizationAgent
from resume_formatter.models import Resume


SAMPLE_RESUME_TEXT = textwrap.dedent("""\
    Jane Doe
    jane.doe@example.com
    +1 (555) 123-4567
    linkedin.com/in/janedoe
    github.com/janedoe

    Summary
    Experienced software engineer with 8+ years building scalable systems.

    Experience
    Senior Software Engineer at Acme Corp
    January 2020 – Present
    Led a team of 6 engineers delivering microservices on AWS.

    Software Engineer at StartupXYZ
    March 2016 – December 2019
    Built full-stack web applications using React and Node.js.

    Education
    Bachelor of Science in Computer Science
    State University
    2016

    Skills
    Python, JavaScript, TypeScript, AWS, Docker, Kubernetes

    Certifications
    AWS Certified Solutions Architect – Amazon Web Services
    Certified Kubernetes Administrator – CNCF

    Languages
    English, Spanish
""")


class TestNormalizationAgent:
    def setup_method(self):
        self.agent = NormalizationAgent()

    def test_returns_resume_instance(self):
        result = self.agent.normalize(SAMPLE_RESUME_TEXT)
        assert isinstance(result, Resume)

    def test_contact_name(self):
        result = self.agent.normalize(SAMPLE_RESUME_TEXT)
        assert result.contact.name == "Jane Doe"

    def test_contact_email(self):
        result = self.agent.normalize(SAMPLE_RESUME_TEXT)
        assert result.contact.email == "jane.doe@example.com"

    def test_contact_phone(self):
        result = self.agent.normalize(SAMPLE_RESUME_TEXT)
        assert result.contact.phone is not None
        assert "555" in result.contact.phone

    def test_contact_linkedin(self):
        import re
        result = self.agent.normalize(SAMPLE_RESUME_TEXT)
        assert result.contact.linkedin is not None
        assert re.match(r"(?:https?://)?(?:www\.)?linkedin\.com/", result.contact.linkedin)

    def test_contact_github(self):
        import re
        result = self.agent.normalize(SAMPLE_RESUME_TEXT)
        assert result.contact.github is not None
        assert re.match(r"(?:https?://)?(?:www\.)?github\.com/", result.contact.github)

    def test_summary_extracted(self):
        result = self.agent.normalize(SAMPLE_RESUME_TEXT)
        assert result.summary is not None
        assert "software engineer" in result.summary.lower()

    def test_experience_extracted(self):
        result = self.agent.normalize(SAMPLE_RESUME_TEXT)
        assert len(result.experience) >= 1

    def test_experience_has_dates(self):
        result = self.agent.normalize(SAMPLE_RESUME_TEXT)
        exp_with_dates = [e for e in result.experience if e.start_date]
        assert len(exp_with_dates) >= 1

    def test_education_extracted(self):
        result = self.agent.normalize(SAMPLE_RESUME_TEXT)
        assert len(result.education) >= 1

    def test_skills_extracted(self):
        result = self.agent.normalize(SAMPLE_RESUME_TEXT)
        skill_names = [s.name for s in result.skills]
        assert any("Python" in name for name in skill_names)

    def test_certifications_extracted(self):
        result = self.agent.normalize(SAMPLE_RESUME_TEXT)
        assert len(result.certifications) >= 1
        cert_names = [c.name for c in result.certifications]
        assert any("AWS" in name for name in cert_names)

    def test_certification_issuer_parsed(self):
        result = self.agent.normalize(SAMPLE_RESUME_TEXT)
        certs_with_issuer = [c for c in result.certifications if c.issuer]
        assert len(certs_with_issuer) >= 1

    def test_languages_extracted(self):
        result = self.agent.normalize(SAMPLE_RESUME_TEXT)
        assert "English" in result.languages or any("English" in lang for lang in result.languages)

    def test_source_file_stored(self):
        result = self.agent.normalize(SAMPLE_RESUME_TEXT, source_file="resume.pdf")
        assert result.source_file == "resume.pdf"

    def test_empty_text_returns_empty_resume(self):
        result = self.agent.normalize("")
        assert isinstance(result, Resume)
        assert result.contact.name == ""
        assert result.experience == []
        assert result.skills == []

    def test_section_without_header(self):
        text = textwrap.dedent("""\
            Skills
            Java, Scala, Spark
        """)
        result = self.agent.normalize(text)
        skill_names = [s.name for s in result.skills]
        assert any("Java" in n for n in skill_names)
