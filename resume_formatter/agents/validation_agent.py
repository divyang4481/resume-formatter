"""ValidationAgent – validates a structured Resume object."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ValidationError:
    field: str
    message: str


@dataclass
class ValidationReport:
    """Result of a :class:`ValidationAgent` run."""

    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return *True* when there are no errors (warnings are allowed)."""
        return not self.errors

    def add_error(self, f: str, msg: str) -> None:
        self.errors.append(ValidationError(field=f, message=msg))

    def add_warning(self, f: str, msg: str) -> None:
        self.warnings.append(ValidationError(field=f, message=msg))

    def __str__(self) -> str:
        lines: list[str] = []
        for e in self.errors:
            lines.append(f"  ERROR   [{e.field}] {e.message}")
        for w in self.warnings:
            lines.append(f"  WARNING [{w.field}] {w.message}")
        return "\n".join(lines) if lines else "  OK – no issues found."


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"[\d\s\-\+\(\)\.]{7,20}")
_URL_RE = re.compile(r"^https?://")


class ValidationAgent:
    """Validate a :class:`~resume_formatter.models.Resume` against business rules.

    Rules
    -----
    Errors (block processing):
    * Contact name must be non-empty.
    * Email, when present, must match a basic format.
    * Phone, when present, must contain at least 7 digits.

    Warnings (informational):
    * No work experience entries found.
    * No education entries found.
    * No skills listed.
    * LinkedIn/GitHub URL should start with ``https://``.
    """

    def validate(self, resume: "Resume") -> ValidationReport:  # noqa: F821
        report = ValidationReport()
        self._validate_contact(resume.contact, report)
        self._validate_experience(resume.experience, report)
        self._validate_education(resume.education, report)
        self._validate_skills(resume.skills, report)
        return report

    # ------------------------------------------------------------------
    # Individual section validators
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_contact(contact: "ContactInfo", report: ValidationReport) -> None:  # noqa: F821
        if not contact.name or not contact.name.strip():
            report.add_error("contact.name", "Candidate name is missing.")

        if contact.email:
            if not _EMAIL_RE.match(contact.email):
                report.add_error("contact.email", f"Invalid e-mail format: {contact.email!r}")

        if contact.phone:
            # Skip digit-count check for already-masked values (contain '*')
            if "*" not in contact.phone:
                digits = re.sub(r"\D", "", contact.phone)
                if len(digits) < 7:
                    report.add_error(
                        "contact.phone",
                        f"Phone number has fewer than 7 digits: {contact.phone!r}",
                    )

        for url_field in ("linkedin", "github"):
            url = getattr(contact, url_field)
            if url and not _URL_RE.match(url):
                report.add_warning(
                    f"contact.{url_field}",
                    f"URL should start with 'https://': {url!r}",
                )

    @staticmethod
    def _validate_experience(experience: list, report: ValidationReport) -> None:
        if not experience:
            report.add_warning("experience", "No work experience entries found.")
            return
        for i, exp in enumerate(experience):
            if not exp.title:
                report.add_warning(f"experience[{i}].title", "Job title is missing.")
            if not exp.company:
                report.add_warning(f"experience[{i}].company", "Company name is missing.")

    @staticmethod
    def _validate_education(education: list, report: ValidationReport) -> None:
        if not education:
            report.add_warning("education", "No education entries found.")

    @staticmethod
    def _validate_skills(skills: list, report: ValidationReport) -> None:
        if not skills:
            report.add_warning("skills", "No skills listed.")
