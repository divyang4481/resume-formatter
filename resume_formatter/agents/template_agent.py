"""TemplateAgent – renders a Resume into formatted output using Jinja2 templates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, select_autoescape

from resume_formatter.models import Resume

# Supported template names and their associated file + output MIME type
_TEMPLATES: dict[str, dict] = {
    "modern": {"file": "modern.html.j2", "mime": "text/html"},
    "classic": {"file": "classic.html.j2", "mime": "text/html"},
    "minimal": {"file": "minimal.md.j2", "mime": "text/markdown"},
}

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

OutputFormat = Literal["modern", "classic", "minimal", "json"]


class TemplateAgent:
    """Render a :class:`~resume_formatter.models.Resume` to a target format.

    Supported formats
    -----------------
    * ``"modern"``  – polished HTML with colour accents
    * ``"classic"`` – traditional serif HTML layout
    * ``"minimal"`` – clean Markdown output
    * ``"json"``    – pretty-printed JSON (no template file required)
    """

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
            keep_trailing_newline=True,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, resume: Resume, template: OutputFormat = "modern") -> str:
        """Render *resume* with the chosen *template*.

        Parameters
        ----------
        resume:
            The structured resume to render.
        template:
            One of ``"modern"``, ``"classic"``, ``"minimal"``, or ``"json"``.

        Returns
        -------
        str
            Rendered content as a string.
        """
        if template == "json":
            return self._render_json(resume)
        if template not in _TEMPLATES:
            raise ValueError(
                f"Unknown template {template!r}. "
                f"Choose from: {', '.join(list(_TEMPLATES) + ['json'])}"
            )
        return self._render_jinja(resume, template)

    @staticmethod
    def supported_templates() -> list[str]:
        """Return the list of supported template names."""
        return list(_TEMPLATES) + ["json"]

    # ------------------------------------------------------------------
    # Renderers
    # ------------------------------------------------------------------

    def _render_jinja(self, resume: Resume, template_name: str) -> str:
        tmpl_file = _TEMPLATES[template_name]["file"]
        tmpl = self._env.get_template(tmpl_file)
        return tmpl.render(resume=resume)

    @staticmethod
    def _render_json(resume: Resume) -> str:
        return resume.model_dump_json(indent=2)
