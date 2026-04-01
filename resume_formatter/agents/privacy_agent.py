"""PrivacyAgent – detects and masks personally-identifiable information (PII)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from resume_formatter.models import Resume, ContactInfo


# ---------------------------------------------------------------------------
# PII detection patterns
# ---------------------------------------------------------------------------

_PII_PATTERNS: Dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(
        r"(?:\+?\d{1,3}[\s\-.]?)?"           # optional country code
        r"(?:\(?\d{1,4}\)?[\s\-.]?)?"        # optional area code
        r"\d{2,4}[\s\-.]?"                   # first segment
        r"\d{2,4}[\s\-.]?"                   # second segment
        r"\d{0,4}"                           # optional trailing digits
    ),
    "ssn": re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[\s\-]?){3}\d{4}\b"),
    "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "date_of_birth": re.compile(
        r"\b(?:D\.?O\.?B\.?|date of birth|born)\s*[:\-]?\s*"
        r"\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}",
        re.IGNORECASE,
    ),
    "linkedin": re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+/?", re.IGNORECASE),
    "github": re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w\-]+/?", re.IGNORECASE),
}


# ---------------------------------------------------------------------------
# Masking helpers
# ---------------------------------------------------------------------------

def _mask_email(value: str) -> str:
    """Mask email to ``u***@domain.tld``."""
    at = value.find("@")
    if at <= 0:
        return "***"
    local = value[:at]
    domain = value[at:]
    masked_local = local[0] + "***" if len(local) > 1 else "***"
    return masked_local + domain


def _mask_phone(value: str) -> str:
    """Keep only the last 4 digits visible: ``***-***-1234``."""
    digits = re.sub(r"\D", "", value)
    visible = digits[-4:] if len(digits) >= 4 else digits
    return f"***-***-{visible}"


def _mask_generic(value: str) -> str:
    """Replace all characters with asterisks."""
    return "*" * min(len(value), 8)


_MASKERS: Dict[str, callable] = {
    "email": _mask_email,
    "phone": _mask_phone,
    "ssn": _mask_generic,
    "credit_card": _mask_generic,
    "ip_address": _mask_generic,
    "date_of_birth": _mask_generic,
    "linkedin": _mask_generic,
    "github": _mask_generic,
}


@dataclass
class PrivacyReport:
    """Report produced by :class:`PrivacyAgent`."""

    findings: List[Tuple[str, str]] = field(default_factory=list)
    """List of ``(pii_type, original_value)`` tuples that were found."""

    masked_fields: List[str] = field(default_factory=list)
    """Names of :class:`~resume_formatter.models.Resume` fields that were masked."""

    @property
    def has_pii(self) -> bool:
        return bool(self.findings)


class PrivacyAgent:
    """Detect and optionally mask PII in a :class:`Resume` object.

    Usage
    -----
    .. code-block:: python

        agent = PrivacyAgent()
        report = agent.scan(resume)            # detect only
        masked_resume, report = agent.mask(resume)  # detect + mask
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self, resume: Resume) -> PrivacyReport:
        """Scan *resume* for PII and return a report without modifying it."""
        report = PrivacyReport()
        flat_text = self._flatten(resume)
        for pii_type, pattern in _PII_PATTERNS.items():
            for match in pattern.finditer(flat_text):
                report.findings.append((pii_type, match.group(0)))
        return report

    def mask(self, resume: Resume) -> Tuple[Resume, PrivacyReport]:
        """Return a copy of *resume* with PII fields masked.

        The original object is **not** modified.
        """
        report = PrivacyReport()

        # Work on a mutable copy via model serialisation round-trip
        data = resume.model_dump()

        # --- contact block ---
        contact = data.get("contact", {})

        if contact.get("email"):
            report.findings.append(("email", contact["email"]))
            contact["email"] = _mask_email(contact["email"])
            report.masked_fields.append("contact.email")

        if contact.get("phone"):
            report.findings.append(("phone", contact["phone"]))
            contact["phone"] = _mask_phone(contact["phone"])
            report.masked_fields.append("contact.phone")

        if contact.get("linkedin"):
            report.findings.append(("linkedin", contact["linkedin"]))
            contact["linkedin"] = _mask_generic(contact["linkedin"])
            report.masked_fields.append("contact.linkedin")

        if contact.get("github"):
            report.findings.append(("github", contact["github"]))
            contact["github"] = _mask_generic(contact["github"])
            report.masked_fields.append("contact.github")

        data["contact"] = contact

        # --- free-text fields (summary, descriptions) ---
        if data.get("summary"):
            data["summary"], extra = self._mask_text(data["summary"])
            report.findings.extend(extra)

        for exp in data.get("experience", []):
            if exp.get("description"):
                exp["description"], extra = self._mask_text(exp["description"])
                report.findings.extend(extra)

        masked = Resume.model_validate(data)
        masked.pii_fields_masked = list(report.masked_fields)
        return masked, report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _flatten(resume: Resume) -> str:
        """Produce a single flat string for scanning."""
        parts: List[str] = []
        c = resume.contact
        for val in [c.name, c.email, c.phone, c.address, c.linkedin, c.github]:
            if val:
                parts.append(val)
        if resume.summary:
            parts.append(resume.summary)
        for exp in resume.experience:
            for val in [exp.title, exp.company, exp.description]:
                if val:
                    parts.append(val)
        return " ".join(parts)

    @staticmethod
    def _mask_text(text: str) -> Tuple[str, List[Tuple[str, str]]]:
        """Mask any PII tokens found inside free-form *text*."""
        findings: List[Tuple[str, str]] = []
        for pii_type, pattern in _PII_PATTERNS.items():
            masker = _MASKERS[pii_type]
            def _replace(m: re.Match, _type=pii_type, _masker=masker) -> str:
                findings.append((_type, m.group(0)))
                return _masker(m.group(0))
            text = pattern.sub(_replace, text)
        return text, findings
