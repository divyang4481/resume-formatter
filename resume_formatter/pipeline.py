"""Pipeline – orchestrates all agents into an end-to-end transformation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, Union

from resume_formatter.agents import (
    ExtractionAgent,
    NormalizationAgent,
    PrivacyAgent,
    ValidationAgent,
    TemplateAgent,
)
from resume_formatter.agents.privacy_agent import PrivacyReport
from resume_formatter.agents.template_agent import OutputFormat
from resume_formatter.agents.validation_agent import ValidationReport
from resume_formatter.models import Resume


@dataclass
class PipelineResult:
    """The complete output of a pipeline run."""

    resume: Resume
    raw_text: str = ""
    rendered: str = ""
    validation: Optional[ValidationReport] = None
    privacy: Optional[PrivacyReport] = None

    @property
    def ok(self) -> bool:
        """Return *True* when the resume passed validation (no errors)."""
        return self.validation is None or self.validation.is_valid


@dataclass
class PipelineConfig:
    """Configuration for a :class:`Pipeline` run."""

    template: OutputFormat = "modern"
    """Output template: ``"modern"``, ``"classic"``, ``"minimal"``, or ``"json"``."""

    apply_privacy: bool = True
    """When *True* PII fields are masked in the output and the privacy report is populated."""

    validate: bool = True
    """When *True* the resume is validated and the report is populated."""


class Pipeline:
    """End-to-end document transformation pipeline.

    Steps
    -----
    1. **Extract** – parse raw text from a PDF, DOCX, or image file.
    2. **Normalize** – convert the raw text into a structured :class:`Resume`.
    3. **Privacy**   – detect and optionally mask PII (configurable).
    4. **Validate**  – run business-rule validation (configurable).
    5. **Render**    – apply a Jinja2 / JSON template to produce the output.

    Usage
    -----
    .. code-block:: python

        pipeline = Pipeline()
        result = pipeline.run("resume.pdf")
        print(result.rendered)      # formatted HTML / Markdown / JSON
        print(result.validation)    # ValidationReport
        print(result.privacy)       # PrivacyReport
    """

    def __init__(self, config: Optional[PipelineConfig] = None) -> None:
        self.config = config or PipelineConfig()
        self._extractor = ExtractionAgent()
        self._normalizer = NormalizationAgent()
        self._privacy = PrivacyAgent()
        self._validator = ValidationAgent()
        self._renderer = TemplateAgent()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        source: Union[str, Path, bytes],
        extension: str = "",
    ) -> PipelineResult:
        """Transform *source* and return a :class:`PipelineResult`.

        Parameters
        ----------
        source:
            A file-system path **or** raw bytes.  When passing bytes, supply
            the *extension* parameter (e.g. ``".pdf"``).
        extension:
            File extension hint required when *source* is ``bytes``.
        """
        source_name: Optional[str] = None
        if isinstance(source, (str, Path)):
            source_name = Path(source).name

        # 1. Extract
        raw_text = self._extractor.extract(source, extension=extension)

        # 2. Normalize
        resume = self._normalizer.normalize(raw_text, source_file=source_name)

        # 3. Privacy
        privacy_report: Optional[PrivacyReport] = None
        if self.config.apply_privacy:
            resume, privacy_report = self._privacy.mask(resume)

        # 4. Validate
        validation_report: Optional[ValidationReport] = None
        if self.config.validate:
            validation_report = self._validator.validate(resume)

        # 5. Render
        rendered = self._renderer.render(resume, template=self.config.template)

        return PipelineResult(
            resume=resume,
            raw_text=raw_text,
            rendered=rendered,
            validation=validation_report,
            privacy=privacy_report,
        )

    def run_text(self, raw_text: str, source_file: Optional[str] = None) -> PipelineResult:
        """Run the pipeline starting from *already extracted* plain text.

        Useful when the caller has extracted text from an external tool and
        only wants normalization, privacy, validation, and rendering.
        """
        resume = self._normalizer.normalize(raw_text, source_file=source_file)

        privacy_report: Optional[PrivacyReport] = None
        if self.config.apply_privacy:
            resume, privacy_report = self._privacy.mask(resume)

        validation_report: Optional[ValidationReport] = None
        if self.config.validate:
            validation_report = self._validator.validate(resume)

        rendered = self._renderer.render(resume, template=self.config.template)

        return PipelineResult(
            resume=resume,
            raw_text=raw_text,
            rendered=rendered,
            validation=validation_report,
            privacy=privacy_report,
        )
