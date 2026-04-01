"""Pydantic models for structured resume data."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, field_validator
import re


class ContactInfo(BaseModel):
    """Personal contact information extracted from a resume."""

    name: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(pattern, v):
            raise ValueError(f"Invalid email address: {v!r}")
        return v.lower()

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Already-masked values (e.g. "***-***-1234") pass through unchanged
        if "*" in v:
            return v
        digits = re.sub(r"\D", "", v)
        if len(digits) < 7 or len(digits) > 15:
            raise ValueError(f"Phone number has an unexpected digit count: {v!r}")
        return v


class WorkExperience(BaseModel):
    """A single work experience entry."""

    company: str = ""
    title: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class Education(BaseModel):
    """A single education entry."""

    institution: str = ""
    degree: str = ""
    field: Optional[str] = None
    graduation_date: Optional[str] = None


class Certification(BaseModel):
    """A professional certification or license."""

    name: str = ""
    issuer: Optional[str] = None
    date: Optional[str] = None


class Skill(BaseModel):
    """A skill with an optional proficiency level."""

    name: str = ""
    level: Optional[str] = None  # beginner | intermediate | advanced | expert


class Resume(BaseModel):
    """Top-level structured resume document."""

    contact: ContactInfo = ContactInfo()
    summary: Optional[str] = None
    experience: List[WorkExperience] = []
    education: List[Education] = []
    skills: List[Skill] = []
    certifications: List[Certification] = []
    languages: List[str] = []

    # Metadata set during pipeline processing
    source_file: Optional[str] = None
    pii_fields_masked: List[str] = []
