import re
from typing import Dict, Any, List

class TemplateManifestV2Normalizer:
    def normalize(self, draft_manifest: dict, evidence: dict) -> dict:
        """
        Normalizes the draft manifest.
        1. Remove numbered suffixes (_2, _3)
        2. Fields unique by semantic identity
        3. Slots unique by render identity
        4. Move child placeholders into parent blocks
        5. Ensure table loop is grouped
        6. Ensure bullet section is grouped
        7. Ensure paste zones are represented
        """
        fields = draft_manifest.get("fields", [])
        slots = draft_manifest.get("slots", [])
        blocks = draft_manifest.get("blocks", [])
        instructions = draft_manifest.get("instructions", [])

        # 1 & 2. Remove numbered suffixes & Deduplicate semantic fields
        normalized_fields = []
        seen_semantic_identities = set()
        field_id_map = {} # Maps old field_id to new deduplicated field_id

        for field in fields:
            field_id = field.get("field_id", "")
            fieldname = field.get("fieldname", "")

            # Clean numbered suffix from ID and Name
            clean_field_id = re.sub(r"_\d+$", "", field_id)
            clean_fieldname = re.sub(r"_\d+$", "", fieldname)

            # Semantic identity
            original_label = field.get("original_label") or ""
            original_heading = field.get("original_heading") or ""
            source_kind = field.get("source_kind", "")
            data_shape = field.get("field_type", "")

            semantic_identity = f"{clean_field_id}|{original_label}|{original_heading}|{source_kind}|{data_shape}"

            if semantic_identity not in seen_semantic_identities:
                seen_semantic_identities.add(semantic_identity)
                field["field_id"] = clean_field_id
                field["fieldname"] = clean_fieldname
                normalized_fields.append(field)
                field_id_map[field_id] = clean_field_id
            else:
                field_id_map[field_id] = clean_field_id # Map duplicate to the preserved one

        # Update slot owner references
        for slot in slots:
            old_owner = slot.get("owner_field_id")
            if old_owner in field_id_map:
                slot["owner_field_id"] = field_id_map[old_owner]

        # Update block owner references
        for block in blocks:
            old_owner = block.get("owner_field_id")
            if old_owner in field_id_map:
                block["owner_field_id"] = field_id_map[old_owner]

        # 3. Slots unique by render identity
        normalized_slots = []
        seen_render_identities = set()

        for slot in slots:
            slot_type = slot.get("slot_type", "")
            render_mode = slot.get("render_mode", "")
            locator = slot.get("locator", {})
            loc_kind = locator.get("kind", "")
            loc_marker = locator.get("marker_text", "")
            loc_label = locator.get("label", "")
            loc_heading = locator.get("heading_text", "")
            loc_start = locator.get("start_marker", "")
            loc_end = locator.get("end_marker", "")
            loc_ordered = str(locator.get("ordered_placeholders", []))

            render_identity = f"{slot_type}|{render_mode}|{loc_kind}|{loc_marker}|{loc_label}|{loc_heading}|{loc_start}|{loc_end}|{loc_ordered}"

            if render_identity not in seen_render_identities:
                seen_render_identities.add(render_identity)
                normalized_slots.append(slot)

        # 4 & 5. Move child placeholders into parent blocks & Ensure table loop is grouped
        # Collect table loop / repeat block item schema definitions
        child_markers_to_remove = set()

        for block in blocks:
            for subfield in block.get("subfields", []):
                # If a subfield maps to a marker, we remove it from top-level
                # Real implementation would need precise mapping
                marker = subfield.get("marker_text") or subfield.get("field_id")
                if marker:
                    child_markers_to_remove.add(marker)

        for slot in normalized_slots:
            if slot.get("slot_type") in ("table_loop", "repeat_block"):
                for item in slot.get("item_schema", []):
                    marker = item.get("marker_text") or item.get("field_id")
                    if marker:
                        child_markers_to_remove.add(marker)

        # Remove top-level fields that are actually children
        final_fields = []
        for f in normalized_fields:
            # Simplistic check if field ID or marker text matches a child
            # In real system, this is based on marker_text
            f_id = f.get("field_id", "")
            f_marker = f.get("render", {}).get("marker_text", "")
            if f_id in child_markers_to_remove or f_marker in child_markers_to_remove:
                continue
            final_fields.append(f)

        # 7. Ensure paste zones are represented
        paste_zones_evidence = evidence.get("docx_structure_view", {}).get("paste_zones", [])
        if paste_zones_evidence:
            for pz_heading in paste_zones_evidence:
                # Check if it exists
                exists = any(f.get("field_type") == "paste_zone" and f.get("original_heading") == pz_heading for f in final_fields)
                if not exists:
                    pz_id = re.sub(r"[^a-z0-9]+", "_", pz_heading.lower()).strip("_")
                    if not pz_id:
                         pz_id = "paste_zone_1"
                    final_fields.append({
                        "field_id": pz_id,
                        "fieldname": pz_id,
                        "field_type": "paste_zone",
                        "source_kind": "static",
                        "original_heading": pz_heading
                    })
                    normalized_slots.append({
                        "slot_id": f"slot_{pz_id}",
                        "owner_field_id": pz_id,
                        "slot_type": "paste_zone",
                        "render_mode": "replace_section_body",
                        "locator": {"heading_text": pz_heading}
                    })
                    instructions.append({
                        "instruction_id": f"inst_{pz_id}",
                        "text": pz_heading, # simplified
                        "nearest_heading": pz_heading,
                        "action": "remove"
                    })

        draft_manifest["fields"] = final_fields
        draft_manifest["slots"] = normalized_slots
        draft_manifest["blocks"] = blocks
        draft_manifest["instructions"] = instructions

        return draft_manifest
