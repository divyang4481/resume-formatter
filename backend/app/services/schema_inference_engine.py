from typing import Any, Dict, List


class SchemaInferenceEngine:
    """
    Infers structured roles (title, meta, bullets, remainder) from a dict item
    using schema hints from the manifest or generic DEFAULT candidate lists.

    Never hard-depends on specific business field names — the DEFAULT lists are
    used only as a last-resort fallback when the manifest provides no hint.
    """

    DEFAULT_PRIMARY = [
        "job_title", "title", "role", "position", "name",
        "degree", "qualification", "program", "course",
    ]
    DEFAULT_SECONDARY = [
        "company", "employer", "employer_name", "organization", "institution",
        "school", "college", "university", "location", "city",
    ]
    DEFAULT_DATES = [
        "dates", "date", "period", "duration",
        "start_date", "end_date", "year_range", "year",
    ]
    DEFAULT_LISTS = [
        "bullet_points", "responsibilities", "highlights",
        "achievements", "details", "summary_points", "tasks",
        "key_contributions", "duties",
    ]

    def infer_object_roles(
        self,
        item: Dict[str, Any],
        schema_hint: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Returns:
            {
                "title":      str,
                "meta_parts": [str, ...],   # secondary + date fields
                "bullets":    [str, ...],
                "remainder":  [str, ...],
            }
        """
        schema_hint = schema_hint or {}

        primary_fields  = schema_hint.get("primary_fields")  or self.DEFAULT_PRIMARY
        secondary_fields = schema_hint.get("secondary_fields") or self.DEFAULT_SECONDARY
        date_fields     = schema_hint.get("date_fields")     or self.DEFAULT_DATES
        list_fields     = schema_hint.get("list_fields")     or self.DEFAULT_LISTS

        title   = self._first_scalar(item, primary_fields)
        secondary = self._collect_scalars(item, secondary_fields)
        dates   = self._collect_scalars(item, date_fields)
        bullets = self._first_list(item, list_fields)

        used_keys = set(primary_fields + secondary_fields + date_fields + list_fields)

        remainder = []
        for k, v in item.items():
            if k in used_keys or not v:
                continue
            if isinstance(v, list):
                remainder.extend(str(x).strip() for x in v if str(x).strip())
            elif isinstance(v, dict):
                remainder.append(f"{k}: {v}")
            else:
                val_str = str(v).strip()
                if val_str:
                    remainder.append(val_str)

        return {
            "title":      title,
            "meta_parts": [*secondary, *dates],
            "bullets":    bullets,
            "remainder":  remainder,
        }

    # ── private helpers ──────────────────────────────────────────────────────

    def _first_scalar(self, item: Dict[str, Any], keys: List[str]) -> str:
        for k in keys:
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        # last-resort: pick first non-empty string value
        for v in item.values():
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    def _collect_scalars(self, item: Dict[str, Any], keys: List[str]) -> List[str]:
        out: List[str] = []
        for k in keys:
            v = item.get(k)
            if not v:
                continue
            if isinstance(v, list):
                out.extend(str(x).strip() for x in v if str(x).strip())
            elif isinstance(v, str) and v.strip():
                out.append(v.strip())
        return out

    def _first_list(self, item: Dict[str, Any], keys: List[str]) -> List[str]:
        for k in keys:
            v = item.get(k)
            if isinstance(v, list):
                return [str(x).strip() for x in v if str(x).strip()]
        return []
