from typing import Any, Dict, List


# Common field aliases: canonical name → common variants found in extraction output
_FIELD_ALIASES: Dict[str, List[str]] = {
    "professional_summary": ["summary", "profile", "overview", "professional_profile"],
    "technical_skills":     ["skills", "technical_skills", "skill_set", "core_skills", "competencies"],
    "professional_experience": ["experience", "work_experience", "employment", "work_history"],
    "key_projects":         ["projects", "key_projects", "notable_projects", "project_highlights"],
    "education":            ["education", "academic_background", "qualifications"],
    "certifications":       ["certifications", "certificates", "credentials", "licenses"],
    "achievements":         ["achievements", "awards", "accomplishments"],
    "languages":            ["languages", "language_skills"],
    "references":           ["references"],
}


class TemplateRenderPlanner:
    """
    Reads the field manifest and produces per-section render instructions.
    Also resolves extracted data keys to manifest fieldnames via source_hints.
    """

    def resolve_data(
        self,
        field_manifest: List[Dict[str, Any]],
        resume_data: Dict[str, Any],
        summary_text: str = "",
    ) -> Dict[str, Any]:
        """
        Returns a new dict keyed by manifest fieldnames, with values sourced
        from resume_data using:
          1. Exact key match
          2. Snake_case normalization
          3. Global alias table (_FIELD_ALIASES)
          4. source_hints keyword scan against resume_data keys
          5. Empty string if nothing found (field absent from cv)

        This resolves the mismatch between extraction output keys (e.g. 'summary',
        'experience') and manifest fieldnames (e.g. 'professional_summary',
        'professional_experience').
        """
        # Flat normalised lookup of ALL extracted keys for fast access
        normalised_data: Dict[str, Any] = {}
        for k, v in resume_data.items():
            normalised_data[k.lower().strip().replace(" ", "_").replace(":", "")] = v

        resolved: Dict[str, Any] = {}

        for item in (field_manifest or []):
            if not isinstance(item, dict):
                continue
            fieldname = item.get("fieldname", "").strip()
            if not fieldname:
                continue

            value = None

            # 1. Exact match
            value = normalised_data.get(fieldname)

            # 2. Global alias table
            if value is None:
                for alias in _FIELD_ALIASES.get(fieldname, []):
                    value = normalised_data.get(alias)
                    if value is not None:
                        break

            # 3. source_hints keyword scan
            if value is None:
                hints_raw = item.get("source_hints", "")
                hints = [h.strip().lower().replace(" ", "_") for h in hints_raw.split(",") if h.strip()]
                for hint in hints:
                    for data_key in normalised_data:
                        if hint in data_key or data_key in hint:
                            value = normalised_data[data_key]
                            break
                    if value is not None:
                        break

            # 4. Substring match on fieldname parts (e.g. 'experience' ⊂ 'professional_experience')
            if value is None:
                parts = fieldname.split("_")
                for part in parts:
                    if len(part) > 4:  # Skip short words like 'key', 'the'
                        for data_key, data_val in normalised_data.items():
                            if part in data_key:
                                value = data_val
                                break
                    if value is not None:
                        break

            resolved[fieldname] = value if value is not None else ""

        # Always ensure summary fallback
        if "professional_summary" not in resolved or not resolved["professional_summary"]:
            resolved["professional_summary"] = summary_text
        if "summary" not in resolved or not resolved["summary"]:
            resolved["summary"] = summary_text

        # Pass-through any extracted keys that weren't in the manifest
        for k, v in normalised_data.items():
            if k not in resolved:
                resolved[k] = v

        return resolved


    def build_plan(
        self,
        expected_fields: List[str],
        field_manifest: List[Dict[str, Any]],
        resume_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Returns an ordered list of render instructions, one per expected field.
        """
        manifest_map: Dict[str, Dict] = {}
        for item in (field_manifest or []):
            if not isinstance(item, dict):
                continue
            key = (item.get("fieldname") or item.get("meaning") or "").strip()
            if key:
                manifest_map[key] = item

        plan = []
        for field in expected_fields:
            item = manifest_map.get(field, {})
            value = resume_data.get(field)

            # Honour an explicit render_mode already in the manifest
            render_mode = item.get("render_mode") or self._infer_render_mode(value)

            plan.append({
                "fieldname": field,
                "render_mode": render_mode,
                "schema_hint": item.get("schema_hint") or {},
                "tag": item.get("tag"),
                "label": item.get("label") or field,
                "field_type": item.get("field_type"),
            })

        # Also include keys present in resume_data but not in expected_fields
        existing_fieldnames = {p["fieldname"] for p in plan}
        for key, value in resume_data.items():
            safe_key = key.lower().strip().replace(" ", "_").replace(":", "")
            if safe_key not in existing_fieldnames:
                item = manifest_map.get(safe_key, {})
                plan.append({
                    "fieldname": safe_key,
                    "render_mode": item.get("render_mode") or self._infer_render_mode(value),
                    "schema_hint": item.get("schema_hint") or {},
                    "tag": item.get("tag"),
                    "label": item.get("label") or safe_key,
                    "field_type": item.get("field_type"),
                })

        return plan

    def _infer_render_mode(self, value: Any) -> str:
        """Infer render strategy purely from value shape — no field-name logic."""
        if value is None or isinstance(value, str):
            return "scalar_richtext"
        if isinstance(value, list):
            if value and all(isinstance(x, dict) for x in value):
                return "object_list_block"
            return "list_scalar_block"
        if isinstance(value, dict):
            return "object_block"
        return "scalar_richtext"
