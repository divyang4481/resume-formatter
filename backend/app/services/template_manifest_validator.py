"""
TemplateManifestValidator
--------------------------
Post-LLM quality gate for template manifests.

Validates:
- Every marker_text exists in detected_markers
- Every blank-marker field has a render_locator
- Every visual_blank_slot has a label in render_locator
- No duplicate marker_text across unrelated fields
- Required Hays fields present
- Snake_case fieldnames
- Confidence scores present
- Coverage statistics

Returns a ValidationResult with status PASS / WARN / FAIL.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Required fields that every Hays template should have (at minimum)
REQUIRED_HAYS_FIELDS = {
    "candidate_name",
    "candidate_id",
    "notice_period",
    "employee_email",
}

# At least one of these CV-body fields must be present
CV_BODY_FIELDS = {"candidate_cv_body", "candidate_own_cv", "cv_body", "full_cv"}

# Source kinds that MUST have a render_locator.strategy
LOCATOR_REQUIRED_KINDS = {"visual_blank_slot", "bullet_slots", "paste_zone", "section_body"}

SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass
class ValidationResult:
    status: str = "PASS"    # PASS | WARN | FAIL
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    coverage: Dict[str, int] = field(default_factory=dict)

    def fail(self, msg: str):
        self.status = "FAIL"
        self.errors.append(msg)

    def warn(self, msg: str):
        if self.status == "PASS":
            self.status = "WARN"
        self.warnings.append(msg)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "errors": self.errors,
            "warnings": self.warnings,
            "coverage": self.coverage,
        }


class TemplateManifestValidator:
    """
    Validates a template analysis manifest against the deterministically
    detected structure to catch LLM hallucinations and missing locators.
    """

    def validate(
        self,
        manifest: List[Dict[str, Any]],
        structure: Any,  # TemplateStructure
    ) -> ValidationResult:
        result = ValidationResult()

        if not manifest:
            result.fail("Manifest is empty — no fields extracted.")
            return result

        detected_markers = structure.detected_markers
        detected_set = set(m.strip() for m in detected_markers)
        detected_inner = {m.strip("«»[]<> ").lower() for m in detected_markers}
        known_headings = set(structure.all_headings or [])
        known_labels = set(structure.all_table_labels or [])
        paste_zones = set(structure.paste_zones or [])
        repeated_markers = set(structure.repeated_markers or [])

        # Build coverage counters
        mapped_count = 0
        visual_slot_count = 0
        used_markers: Dict[str, List[str]] = {}  # marker → [fieldnames]
        fieldnames_seen: set = set()

        for entry in manifest:
            fn = entry.get("fieldname", "")
            ft = entry.get("field_type", "scalar")
            sk = entry.get("source_kind", "")
            mt = (entry.get("marker_text") or "").strip()
            locator = entry.get("render_locator") or {}
            confidence = entry.get("confidence")

            # Skip instruction blocks — they don't need markers
            if ft == "instruction_block" or sk == "instruction_block":
                continue

            # ---- Fieldname checks ----
            if not fn:
                result.fail("Found manifest entry with no fieldname.")
                continue

            if not SNAKE_CASE_RE.match(fn) and not fn.startswith("_"):
                result.warn(f"Fieldname '{fn}' is not snake_case.")

            if fn in fieldnames_seen:
                result.warn(f"Duplicate fieldname '{fn}' in manifest.")
            fieldnames_seen.add(fn)

            # ---- Confidence ----
            if confidence is None:
                result.warn(f"Field '{fn}' has no confidence score.")

            # ---- marker_text validation ----
            if mt:
                # marker_text must exist in detected markers
                if mt not in detected_set:
                    mt_inner = mt.strip("«»[]<> ").lower()
                    if mt_inner not in detected_inner:
                        result.fail(
                            f"Field '{fn}' has marker_text='{mt}' which is NOT in detected_markers. "
                            f"Possible hallucination."
                        )
                    else:
                        result.warn(
                            f"Field '{fn}' marker_text='{mt}' found in detected markers by inner name "
                            f"(encoding mismatch — normalise)."
                        )
                else:
                    mapped_count += 1

                # Duplicate marker check (warn unless it's a shared marker like [Type text])
                if mt in repeated_markers:
                    strategy = locator.get("strategy", "")
                    if strategy == "replace_marker":
                        result.warn(
                            f"Field '{fn}' uses repeated marker '{mt}' without context strategy "
                            "(use label or heading based locator instead)."
                        )
                
                # Global duplicate check (different fields using same marker)
                used_markers.setdefault(mt, []).append(fn)

            else:
                # No marker_text — must have render_locator
                if sk in LOCATOR_REQUIRED_KINDS:
                    visual_slot_count += 1
                    strategy = locator.get("strategy", "")
                    if not strategy:
                        result.fail(
                            f"Field '{fn}' has source_kind='{sk}' but no render_locator.strategy."
                        )
                    if sk == "visual_blank_slot" and not locator.get("label"):
                        result.fail(
                            f"Field '{fn}' is visual_blank_slot but render_locator.label is missing."
                        )
                    if sk == "paste_zone":
                        heading = locator.get("heading")
                        if not heading:
                            result.fail(f"Field '{fn}' is paste_zone but render_locator.heading is missing.")
                        elif heading not in paste_zones:
                            result.fail(f"Field '{fn}' has hallucinated paste_zone heading '{heading}'.")
                    
                    if sk == "section_body" or sk == "bullet_slots":
                        heading = locator.get("heading")
                        if heading and heading not in known_headings:
                            result.fail(f"Field '{fn}' has hallucinated heading '{heading}'.")

                    if sk == "visual_blank_slot":
                        label = locator.get("label")
                        if not label:
                            result.fail(f"Field '{fn}' is visual_blank_slot but render_locator.label is missing.")
                        elif label not in known_labels:
                            result.fail(f"Field '{fn}' has hallucinated table label '{label}'.")
                else:
                    # merge_marker field with no marker_text
                    if sk == "merge_marker":
                        result.fail(
                            f"Field '{fn}' has source_kind='merge_marker' but empty marker_text. "
                            f"Reconciliation failed for this field."
                        )

        # ---- Duplicate markers (non-generic) ----
        for marker, fns in used_markers.items():
            if len(fns) > 1:
                result.warn(f"Marker '{marker}' mapped to multiple fields: {fns}")

        # ---- Required Hays fields ----
        for req_fn in REQUIRED_HAYS_FIELDS:
            if req_fn not in fieldnames_seen:
                result.warn(f"Required Hays field '{req_fn}' is missing from manifest.")

        if not fieldnames_seen.intersection(CV_BODY_FIELDS):
            result.warn(
                f"No CV body field found (expected one of: {CV_BODY_FIELDS}). "
                f"Template may not have a paste zone or free-form CV section."
            )

        # ---- Coverage stats ----
        result.coverage = {
            "detected_marker_count": len(detected_markers),
            "mapped_marker_count": mapped_count,
            "visual_slot_count": visual_slot_count,
            "unmapped_marker_count": len(detected_markers) - mapped_count,
            "total_fields": len(fieldnames_seen),
        }

        logger.info(
            f"ManifestValidation: status={result.status}, "
            f"errors={len(result.errors)}, warnings={len(result.warnings)}, "
            f"coverage={result.coverage}"
        )

        return result
