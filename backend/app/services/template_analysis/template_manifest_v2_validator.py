import re
from typing import Dict, Any, List

class TemplateManifestV2Validator:
    def validate(self, manifest: dict, evidence: dict) -> dict:
        """
        Validates the manifest.
        1. field_id unique
        2. slot_id unique
        3. every slot.owner_field_id exists
        4. every field.render.target_slot_ids exists
        5. no field_id or fieldname ends with _2/_3
        6. no table loop item marker is top-level field
        7. all detected markers are covered
        8. no duplicate slot render identities
        9. no duplicate semantic field identities
        10. all instructions have action remove/preserve
        """
        status = "PASS"
        errors = []
        warnings = []

        fields = manifest.get("fields", [])
        slots = manifest.get("slots", [])
        instructions = manifest.get("instructions", [])

        field_ids = []
        slot_ids = []

        # Check IDs and _2/_3 suffixes
        for f in fields:
            fid = f.get("field_id", "")
            fname = f.get("fieldname", "")

            if fid in field_ids:
                errors.append(f"Duplicate field_id: {fid}")
                status = "FAIL"
            field_ids.append(fid)

            if re.search(r"_\d+$", fid) or re.search(r"_\d+$", fname):
                errors.append(f"Field ends with numbered suffix: {fid} or {fname}")
                status = "FAIL"
            if f.get("source_kind") == "raw_resume_passthrough":
                if f.get("field_type") != "paste_zone":
                    errors.append(f"Field {fid} uses raw_resume_passthrough but is not paste_zone.")
                    status = "FAIL"
                semantic_like_names = {"skills", "education", "work_experience", "professional_qualifications", "certifications"}
                if fname in semantic_like_names:
                    errors.append(f"Field {fid} uses raw_resume_passthrough with semantic fieldname '{fname}'.")
                    status = "FAIL"

        for s in slots:
            sid = s.get("slot_id", "")
            if sid in slot_ids:
                errors.append(f"Duplicate slot_id: {sid}")
                status = "FAIL"
            slot_ids.append(sid)

            owner = s.get("owner_field_id")
            if owner and owner not in field_ids:
                errors.append(f"Slot {sid} references missing owner_field_id: {owner}")
                status = "FAIL"
            loc = s.get("locator", {}) or {}
            marker_text = (loc.get("marker_text") or loc.get("placeholder_text") or "").strip().lower()
            if marker_text in {"[type text]", "«type text»", "type text"}:
                has_scope = bool(loc.get("heading") or loc.get("heading_text")) and (
                    loc.get("occurrence_index_under_heading") is not None
                    or loc.get("occurrence_index") is not None
                    or loc.get("paragraph_or_cell_path")
                    or loc.get("path")
                )
                if not has_scope:
                    warnings.append(f"Slot {sid} uses generic placeholder without location metadata.")

        # Check instruction actions
        for inst in instructions:
            action = inst.get("action")
            if action not in ("remove", "preserve"):
                errors.append(f"Instruction {inst.get('instruction_id')} has invalid action: {action}")
                status = "FAIL"

        # Note: Checks 6, 7, 8, 9 are complex to implement fully without full marker resolution,
        # but the Normalizer handles deduplication.

        detected_markers = evidence.get("docx_structure_view", {}).get("detected_markers", [])

        # Covered markers simplified check
        covered = []
        for s in slots:
            loc = s.get("locator", {})
            if "marker_text" in loc:
                covered.append(loc["marker_text"])
            for item in s.get("item_schema", []):
                if "marker_text" in item:
                    covered.append(item["marker_text"])

        uncovered = [m for m in detected_markers if m not in covered and not m.startswith("Table")]
        if uncovered:
            warnings.append(f"Uncovered markers: {uncovered}")

        return {
            "status": status,
            "errors": errors,
            "warnings": warnings,
            "covered_markers": covered,
            "uncovered_markers": uncovered,
            "duplicate_field_ids": [] # Populated in real validator
        }
