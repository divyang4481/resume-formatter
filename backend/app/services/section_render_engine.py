import json
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

from docxtpl import RichText
from app.services.schema_inference_engine import SchemaInferenceEngine

logger = logging.getLogger(__name__)


class SectionRenderEngine:
    """
    Converts a single field value into a DOCX-safe object AND a CVML-tagged string.

    Strategies
    ----------
    scalar_richtext    : AI-polished with manifest guidance → RichText (or str)
    list_scalar_block  : list[str|primitive] → bulleted RichText
    object_list_block  : list[dict] → schema-inferred RichText blocks
    object_block       : dict → schema-inferred RichText block
    """

    def __init__(self, llm=None) -> None:
        self._schema = SchemaInferenceEngine()
        self._llm = llm  # Optional: injected LlmRuntimeAdapter

    # ── public entry point ───────────────────────────────────────────────────

    def render_field(
        self,
        field_name: str,
        value: Any,
        render_plan: Dict[str, Any],
        manifest_item: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
    ) -> Tuple[Any, str]:
        """
        Returns: (docx_render_object, cvml_string)
        """
        mode        = render_plan.get("render_mode", "scalar_richtext")
        schema_hint = render_plan.get("schema_hint") or {}

        if mode == "scalar_richtext":
            return self._render_scalar_with_ai(
                field_name=field_name,
                value=value,
                manifest_item=manifest_item or {},
                job_id=job_id,
            )

        if mode == "list_scalar_block":
            return self._render_list_of_scalars(value)

        if mode == "object_list_block":
            return self._render_object_list(value, schema_hint)

        if mode == "object_block":
            return self._render_object(value, schema_hint)

        logger.warning(f"Unknown render_mode '{mode}' for '{field_name}', using scalar.")
        return self._render_scalar_with_ai(
            field_name=field_name,
            value=value,
            manifest_item=manifest_item or {},
            job_id=job_id,
        )

    # ── scalar: AI-polished (manifest-guided, small prompt) ─────────────────

    def _render_scalar_with_ai(
        self,
        field_name: str,
        value: Any,
        manifest_item: Dict[str, Any],
        job_id: Optional[str] = None,
    ) -> Tuple[Any, str]:
        if not isinstance(value, str):
            value = json.dumps(value, indent=2) if isinstance(value, (dict, list)) else str(value or "")

        if not value.strip():
            return "", ""

        if self._llm and manifest_item:
            try:
                from app.agent.prompt_manager import prompt_manager
                system_prompt, user_prompt = prompt_manager.get_chat_prompt(
                    "field_polish",
                    fieldname=manifest_item.get("fieldname", field_name),
                    meaning=manifest_item.get("meaning", ""),
                    content_expectation=manifest_item.get("content_expectation", ""),
                    structure_expectation=manifest_item.get("structure_expectation", ""),
                    constraints=manifest_item.get("constraints", ""),
                    field_intent=manifest_item.get("field_intent", ""),
                    source_value=value[:3000],
                )

                response = self._llm.generate(user_prompt, system_prompt=system_prompt)

                if response and len(response.strip()) > 5:
                    cvml_str = response.strip()
                    logger.debug(f"AI-polished scalar field '{field_name}'")
                    from app.services.audit_service import AuditService
                    AuditService.log_event(
                        job_id=job_id,
                        event_type="FIELD_POLISH_AI",
                        payload={"field": field_name, "chars_in": len(value), "chars_out": len(cvml_str)},
                    )
                    return self._apply_cvml_formatting(cvml_str), cvml_str

            except Exception as e:
                logger.warning(f"AI polish failed for '{field_name}': {e}. Using CVML fallback.")

        # Fallback: direct CVML formatting
        cvml_str = value.strip()
        return self._apply_cvml_formatting(cvml_str), cvml_str

    # ── helper: strip existing bullet/dash prefix ───────────────────────────

    @staticmethod
    def _clean_bullet_text(text: str) -> str:
        """Remove leading punctuation that the source data already has (-, •, *, .)."""
        return re.sub(r'^[\s\-\.\*•]+', '', text).strip()

    # ── list of scalars ──────────────────────────────────────────────────────

    def _render_list_of_scalars(self, items: List[Any]) -> Tuple[Any, str]:
        cvml_parts = []
        for item in (items or []):
            text = self._clean_bullet_text(str(item).strip())
            if text:
                cvml_parts.append(f"[:L1:] {text}")
        
        cvml_str = "[:BR:]".join(cvml_parts)
        return self._apply_cvml_formatting(cvml_str), cvml_str

    # ── list of objects (experience, education, etc.) ────────────────────────

    def _render_object_list(
        self,
        items: List[Dict[str, Any]],
        schema_hint: Dict[str, Any],
    ) -> Tuple[Any, str]:
        cvml_blocks = []
        valid = [x for x in (items or []) if isinstance(x, dict)]
        for item in valid:
            roles = self._schema.infer_object_roles(item, schema_hint)
            cvml_blocks.append(self._build_object_cvml(roles))
        
        cvml_str = "[:BR:][:BR:]".join(cvml_blocks)
        return self._apply_cvml_formatting(cvml_str), cvml_str

    def _render_object(
        self,
        item: Dict[str, Any],
        schema_hint: Dict[str, Any],
    ) -> Tuple[Any, str]:
        roles = self._schema.infer_object_roles(item or {}, schema_hint)
        cvml_str = self._build_object_cvml(roles)
        return self._apply_cvml_formatting(cvml_str), cvml_str

    # ── object block builder (CVML version) ──────────────────────────────────

    def _build_object_cvml(self, roles: Dict[str, Any]) -> str:
        lines = []
        # Line 1: Title | Dates (Bold)
        t_line = [roles["title"]] if roles["title"] else []
        
        date_keywords = ["present", "-", "20", "19", "jan", "feb", "mar", "apr",
                         "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        date_parts = [m for m in roles["meta_parts"] if any(k in m.lower() for k in date_keywords)]
        other_meta = [m for m in roles["meta_parts"] if m not in date_parts]

        if date_parts:
            t_line.append(" | ".join(date_parts))
        
        if t_line:
            lines.append("[:B:]" + " | ".join(t_line) + "[:/B:]")

        # Line 2: Company | Location (Bold)
        if other_meta:
            lines.append("[:B:]" + " | ".join(other_meta) + "[:/B:]")

        # Bullets
        for bullet in roles["bullets"]:
            clean = self._clean_bullet_text(bullet)
            if clean:
                lines.append(f"[:L1:] {clean}")

        # Remainder
        for line in roles["remainder"]:
            clean = self._clean_bullet_text(line)
            if clean:
                lines.append(clean)
        
        return "[:BR:]".join(lines)

    # ── CVML formatter ───────────────────────────────────────────────────────

    def _apply_cvml_formatting(self, content: str) -> Any:
        content = re.sub(r'(?m)^[ \t]*[•\-\*][ \t]*', '[:L1:] ', content)
        content = content.replace("\u2022", "[:L1:]")
        content = content.replace("\r\n", "\n")

        TAG_SPLIT = r'(?i)(\[:B:\]|\[:/B:\]|\[:PIPE:\]|\[:TAB:\]|\[:BR:\]|\[:L\d+:\])'

        if not re.search(TAG_SPLIT, content):
            if "\n" not in content:
                return content
            content = content.replace("\n", "[:BR:]")

        rt = RichText()
        parts = re.split(TAG_SPLIT, content)
        is_bold = False
        for part in parts:
            if not part:
                continue
            lower = part.lower()
            if lower == "[:b:]":
                is_bold = True
            elif lower == "[:/b:]":
                is_bold = False
            elif lower == "[:pipe:]":
                rt.add(" | ", bold=is_bold)
            elif lower == "[:tab:]":
                rt.add("    ", bold=is_bold)
            elif lower == "[:br:]":
                rt.add("\n")
            elif lower.startswith("[:l"):
                rt.add("\n\u2022 ", bold=is_bold)
            else:
                rt.add(re.sub(r" +", " ", part), bold=is_bold)
        return rt
