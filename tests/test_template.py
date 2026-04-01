"""Tests for TemplateAgent."""

from __future__ import annotations

import json

import pytest

from resume_formatter.agents.template_agent import TemplateAgent
from resume_formatter.models import (
    Certification,
    ContactInfo,
    Education,
    Resume,
    Skill,
    WorkExperience,
)


def _sample_resume() -> Resume:
    return Resume(
        contact=ContactInfo(
            name="Carol Dev",
            email="carol@dev.io",
            phone="+1 555 000 1111",
            linkedin="https://linkedin.com/in/caroldev",
            github="https://github.com/caroldev",
        ),
        summary="Full-stack developer with a passion for clean code.",
        experience=[
            WorkExperience(
                title="Lead Developer",
                company="Tech Corp",
                start_date="Jan 2019",
                end_date="Present",
                description="Led development of core platform.",
            )
        ],
        education=[
            Education(
                institution="MIT",
                degree="BS Computer Science",
                graduation_date="2018",
            )
        ],
        skills=[Skill(name="Python"), Skill(name="React"), Skill(name="Go")],
        certifications=[
            Certification(name="AWS SAA", issuer="Amazon", date="2020")
        ],
        languages=["English", "French"],
    )


class TestTemplateAgent:
    def setup_method(self):
        self.agent = TemplateAgent()
        self.resume = _sample_resume()

    def test_supported_templates(self):
        templates = TemplateAgent.supported_templates()
        assert "modern" in templates
        assert "classic" in templates
        assert "minimal" in templates
        assert "json" in templates

    def test_render_modern_contains_name(self):
        output = self.agent.render(self.resume, template="modern")
        assert "Carol Dev" in output

    def test_render_modern_is_html(self):
        output = self.agent.render(self.resume, template="modern")
        assert "<!DOCTYPE html>" in output or "<html" in output

    def test_render_classic_contains_name(self):
        output = self.agent.render(self.resume, template="classic")
        assert "Carol Dev" in output

    def test_render_classic_is_html(self):
        output = self.agent.render(self.resume, template="classic")
        assert "<html" in output

    def test_render_minimal_contains_name(self):
        output = self.agent.render(self.resume, template="minimal")
        assert "Carol Dev" in output

    def test_render_minimal_is_markdown(self):
        output = self.agent.render(self.resume, template="minimal")
        # Markdown headings
        assert "#" in output

    def test_render_json_is_valid_json(self):
        output = self.agent.render(self.resume, template="json")
        data = json.loads(output)
        assert data["contact"]["name"] == "Carol Dev"

    def test_render_json_contains_all_sections(self):
        output = self.agent.render(self.resume, template="json")
        data = json.loads(output)
        assert "experience" in data
        assert "education" in data
        assert "skills" in data

    def test_render_unknown_template_raises(self):
        with pytest.raises(ValueError, match="Unknown template"):
            self.agent.render(self.resume, template="nonexistent")  # type: ignore[arg-type]

    def test_render_skills_appear(self):
        output = self.agent.render(self.resume, template="modern")
        assert "Python" in output

    def test_render_experience_dates_appear(self):
        output = self.agent.render(self.resume, template="modern")
        assert "Jan 2019" in output

    def test_render_minimal_skills(self):
        output = self.agent.render(self.resume, template="minimal")
        assert "Python" in output

    def test_render_certifications_appear(self):
        output = self.agent.render(self.resume, template="classic")
        assert "AWS SAA" in output

    def test_render_languages_appear(self):
        output = self.agent.render(self.resume, template="minimal")
        assert "English" in output or "French" in output
