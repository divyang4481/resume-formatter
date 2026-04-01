"""NormalizationAgent – parses raw text into a structured Resume object."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from resume_formatter.models import (
    ContactInfo,
    WorkExperience,
    Education,
    Certification,
    Skill,
    Resume,
)


# ---------------------------------------------------------------------------
# Section heading keywords (case-insensitive)
# ---------------------------------------------------------------------------
_SECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "summary": re.compile(
        r"^\s*(summary|profile|objective|about me|professional summary)\s*$",
        re.IGNORECASE,
    ),
    "experience": re.compile(
        r"^\s*(experience|work experience|employment|work history|professional experience)\s*$",
        re.IGNORECASE,
    ),
    "education": re.compile(
        r"^\s*(education|academic background|qualifications|academic qualifications)\s*$",
        re.IGNORECASE,
    ),
    "skills": re.compile(
        r"^\s*(skills|technical skills|core competencies|competencies|expertise)\s*$",
        re.IGNORECASE,
    ),
    "certifications": re.compile(
        r"^\s*(certifications?|certificates?|licen[sc]es?)\s*$",
        re.IGNORECASE,
    ),
    "languages": re.compile(
        r"^\s*(languages?|spoken languages?)\s*$",
        re.IGNORECASE,
    ),
}

# ---------------------------------------------------------------------------
# Contact extraction helpers
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?"           # optional country code
    r"(?:\(?\d{1,4}\)?[\s\-.]?)?"        # optional area code
    r"\d{2,4}[\s\-.]?"                   # first segment
    r"\d{2,4}[\s\-.]?"                   # second segment
    r"\d{0,4}"                           # optional trailing digits
)
_LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+/?", re.IGNORECASE)
_GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w\-]+/?", re.IGNORECASE)

# Date range: "Jan 2020 – Present", "2019 - 2021", "03/2018 - 09/2020"
_DATE_RANGE_RE = re.compile(
    r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"[\s.,]*\d{4}|\d{1,2}[\/\-]\d{4}|\d{4})"
    r"\s*[-–—to]+\s*"
    r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"[\s.,]*\d{4}|\d{1,2}[\/\-]\d{4}|\d{4}|[Pp]resent|[Cc]urrent|[Nn]ow)",
    re.IGNORECASE,
)


class NormalizationAgent:
    """Parse raw text extracted from a resume document into a :class:`Resume`.

    The agent uses heuristic section-detection and regular expressions.  It
    is intentionally conservative: when a field cannot be reliably detected
    the field is left empty rather than filled with incorrect data.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def normalize(self, raw_text: str, source_file: Optional[str] = None) -> Resume:
        """Parse *raw_text* and return a populated :class:`Resume`.

        Parameters
        ----------
        raw_text:
            Plain text extracted from a document.
        source_file:
            Optional original file name stored as metadata.
        """
        lines = [ln.rstrip() for ln in raw_text.splitlines()]
        sections = self._split_sections(lines)

        contact = self._parse_contact(sections.get("header", []))
        summary = self._parse_summary(sections.get("summary", []))
        experience = self._parse_experience(sections.get("experience", []))
        education = self._parse_education(sections.get("education", []))
        skills = self._parse_skills(sections.get("skills", []))
        certifications = self._parse_certifications(sections.get("certifications", []))
        languages = self._parse_languages(sections.get("languages", []))

        return Resume(
            contact=contact,
            summary=summary,
            experience=experience,
            education=education,
            skills=skills,
            certifications=certifications,
            languages=languages,
            source_file=source_file,
        )

    # ------------------------------------------------------------------
    # Section splitting
    # ------------------------------------------------------------------

    def _split_sections(self, lines: List[str]) -> dict[str, List[str]]:
        """Split the document into named sections.

        Everything before the first recognised section heading is treated as
        the *header* (contact info + candidate name).
        """
        sections: dict[str, List[str]] = {"header": []}
        current: str = "header"

        for line in lines:
            matched_section = self._match_section(line)
            if matched_section:
                current = matched_section
                if current not in sections:
                    sections[current] = []
            else:
                sections.setdefault(current, []).append(line)

        return sections

    @staticmethod
    def _match_section(line: str) -> Optional[str]:
        stripped = line.strip()
        if not stripped:
            return None
        for name, pattern in _SECTION_PATTERNS.items():
            if pattern.match(stripped):
                return name
        return None

    # ------------------------------------------------------------------
    # Contact info
    # ------------------------------------------------------------------

    def _parse_contact(self, lines: List[str]) -> ContactInfo:
        text = "\n".join(lines)

        email_match = _EMAIL_RE.search(text)
        phone_match = _PHONE_RE.search(text)
        linkedin_match = _LINKEDIN_RE.search(text)
        github_match = _GITHUB_RE.search(text)

        # The name is assumed to be the first non-empty line in the header
        name = ""
        for line in lines:
            stripped = line.strip()
            if stripped:
                name = stripped
                break

        try:
            contact = ContactInfo(
                name=name,
                email=email_match.group(0) if email_match else None,
                phone=phone_match.group(0).strip() if phone_match else None,
                linkedin=linkedin_match.group(0) if linkedin_match else None,
                github=github_match.group(0) if github_match else None,
            )
        except Exception:
            # If pydantic validation fails (e.g. malformed email), fall back
            contact = ContactInfo(name=name)

        return contact

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_summary(lines: List[str]) -> Optional[str]:
        text = " ".join(ln.strip() for ln in lines if ln.strip())
        return text if text else None

    # ------------------------------------------------------------------
    # Work experience
    # ------------------------------------------------------------------

    def _parse_experience(self, lines: List[str]) -> List[WorkExperience]:
        entries: List[WorkExperience] = []
        current: dict = {}

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current:
                    entries.append(self._build_experience(current))
                    current = {}
                continue

            date_match = _DATE_RANGE_RE.search(stripped)
            if date_match:
                current["start_date"] = date_match.group(1).strip()
                current["end_date"] = date_match.group(2).strip()
                # Rest of the line (before the date) may contain title/company
                before = stripped[: date_match.start()].strip(" ,-|")
                if before and not current.get("title"):
                    self._assign_title_company(current, before)
            else:
                if not current.get("title"):
                    self._assign_title_company(current, stripped)
                else:
                    desc = current.get("description", "")
                    current["description"] = (desc + " " + stripped).strip() if desc else stripped

        if current:
            entries.append(self._build_experience(current))

        return entries

    @staticmethod
    def _assign_title_company(current: dict, text: str) -> None:
        """Heuristically split 'Title at Company' or 'Title | Company'."""
        sep_match = re.search(r"\s+(?:at|@|\||–|-)\s+", text, re.IGNORECASE)
        if sep_match:
            current["title"] = text[: sep_match.start()].strip()
            current["company"] = text[sep_match.end() :].strip()
        elif not current.get("company"):
            current["title"] = text
        else:
            current["company"] = text

    @staticmethod
    def _build_experience(d: dict) -> WorkExperience:
        return WorkExperience(
            title=d.get("title", ""),
            company=d.get("company", ""),
            start_date=d.get("start_date"),
            end_date=d.get("end_date"),
            description=d.get("description"),
        )

    # ------------------------------------------------------------------
    # Education
    # ------------------------------------------------------------------

    def _parse_education(self, lines: List[str]) -> List[Education]:
        entries: List[Education] = []
        current: dict = {}

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current:
                    entries.append(self._build_education(current))
                    current = {}
                continue

            date_match = _DATE_RANGE_RE.search(stripped)
            single_year = re.search(r"\b(19|20)\d{2}\b", stripped)

            if date_match:
                current["graduation_date"] = date_match.group(2).strip()
            elif single_year:
                current["graduation_date"] = single_year.group(0)

            degree_match = re.search(
                r"\b(Bachelor|Master|Ph\.?D|Associate|B\.?S\.?|M\.?S\.?|B\.?A\.?|M\.?B\.?A\.?|"
                r"B\.?Eng|M\.?Eng|Doctor)\b",
                stripped,
                re.IGNORECASE,
            )
            if degree_match and not current.get("degree"):
                current["degree"] = stripped
            elif not current.get("institution"):
                current["institution"] = stripped
            elif not current.get("field"):
                current["field"] = stripped

        if current:
            entries.append(self._build_education(current))

        return entries

    @staticmethod
    def _build_education(d: dict) -> Education:
        return Education(
            institution=d.get("institution", ""),
            degree=d.get("degree", ""),
            field=d.get("field"),
            graduation_date=d.get("graduation_date"),
        )

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_skills(lines: List[str]) -> List[Skill]:
        skills: List[Skill] = []
        for line in lines:
            # Lines may be comma-separated lists or bullet points
            for item in re.split(r"[,;•·\-–\u2022]", line):
                name = item.strip()
                if name:
                    skills.append(Skill(name=name))
        return skills

    # ------------------------------------------------------------------
    # Certifications
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_certifications(lines: List[str]) -> List[Certification]:
        certs: List[Certification] = []
        for line in lines:
            stripped = line.strip("•·- \t")
            if stripped:
                # Try to detect issuer: "AWS Certified Developer – Amazon Web Services"
                parts = re.split(r"\s*[-–—|]\s*", stripped, maxsplit=1)
                if len(parts) == 2:
                    certs.append(Certification(name=parts[0].strip(), issuer=parts[1].strip()))
                else:
                    certs.append(Certification(name=stripped))
        return certs

    # ------------------------------------------------------------------
    # Languages
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_languages(lines: List[str]) -> List[str]:
        languages: List[str] = []
        for line in lines:
            for item in re.split(r"[,;•·\-\u2022]", line):
                lang = item.strip()
                if lang:
                    languages.append(lang)
        return languages
