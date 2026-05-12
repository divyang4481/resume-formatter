import json
import logging
import os
import re
import zipfile
import lxml.etree as ET
from typing import Dict, List, Any

from app.config import settings
from app.agent.prompt_manager import prompt_manager
from app.agent.utils.llm_sanitizer import LlmSanitizer

logger = logging.getLogger(__name__)


class ResumeAiService:
    def __init__(self, llm_adapter, extraction_service=None):
        self.llm = llm_adapter
        self.extraction_service = extraction_service

    async def generate_summary(
        self,
        extracted_text: str,
        guidance: str = "",
        industry: str = None,
        language: str = "en",
    ) -> str:
        """Restored method for worker nodes to generate professional summaries."""
        prompt = f"Summarize the following professional experience into 3 punchy bullet points. Language: {language}. Industry: {industry}.\nGuidance: {guidance}\n\n{extracted_text[:10000]}"
        
        logger.info("\n" + "=" * 60 + "\n--- GENERATE SUMMARY PROMPT ---\n" + "=" * 60)
        logger.info(prompt)
        logger.info("=" * 60 + "\n")
        
        summary = self.llm.generate(prompt)
        
        logger.info("\n" + "=" * 60 + "\n--- GENERATE SUMMARY RESPONSE ---\n" + "=" * 60)
        logger.info(summary)
        logger.info("=" * 60 + "\n")
        
        return summary.strip()

    async def summarize_experience(self, experience_text: str) -> str:
        """Alias for short-form summarization."""
        return await self.generate_summary(experience_text)

    def _get_docx_placeholders_from_xml(self, content: bytes) -> List[str]:
        """
        Deep-scans ALL DOCX XML parts for placeholder markers.
        Handles:
          - MERGEFIELD simple/complex fields
          - «guillemet» markers (including those split across <w:r> runs)
          - Bracketed [Type text] placeholders
          - Header/footer XML files (not just word/document.xml)
        """
        placeholders = []
        W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        W = f"{{{W_NS}}}"

        # XML parts to scan (document body + all headers/footers)
        XML_PARTS_TO_SCAN = [
            "word/document.xml",
            "word/header1.xml", "word/header2.xml", "word/header3.xml",
            "word/footer1.xml", "word/footer2.xml", "word/footer3.xml",
        ]

        try:
            import io

            with zipfile.ZipFile(io.BytesIO(content)) as z:
                available_parts = set(z.namelist())

                for part_name in XML_PARTS_TO_SCAN:
                    if part_name not in available_parts:
                        continue

                    xml_content = z.read(part_name)
                    root = ET.fromstring(xml_content)
                    ns = {"w": W_NS}

                    # 1. MERGEFIELD simple fields (w:fldSimple)
                    for fld in root.xpath("//w:fldSimple", namespaces=ns):
                        instr = fld.get(f"{W}instr")
                        if instr and "MERGEFIELD" in instr:
                            parts = instr.split()
                            if len(parts) >= 2:
                                placeholders.append(parts[parts.index("MERGEFIELD") + 1])

                    # 2. MERGEFIELD complex fields (w:instrText)
                    for instr_text in root.xpath("//w:instrText", namespaces=ns):
                        text = instr_text.text
                        if text and "MERGEFIELD" in text:
                            parts = text.split()
                            if len(parts) >= 2:
                                placeholders.append(parts[parts.index("MERGEFIELD") + 1])

                    # 3. Reconstruct paragraph text across split <w:r> runs to find «...» markers
                    #    Word often splits a single cell value across many runs, breaking naive regex.
                    for para in root.xpath("//w:p", namespaces=ns):
                        # Concatenate all w:t text within this paragraph
                        run_texts = [
                            t.text or ""
                            for t in para.xpath(".//w:t", namespaces=ns)
                        ]
                        para_text = "".join(run_texts)
                        # Now scan the reconstructed text for guillemet markers
                        for m in re.finditer(r"«\s*(.*?)\s*»", para_text):
                            placeholders.append(f"«{m.group(1).strip()}»")
                        # Also scan for bracketed forms
                        for m in re.finditer(r"\[\s*([^\]\s][^\]]*?)\s*\]", para_text):
                            inner = m.group(1).strip()
                            if inner and len(inner) < 80:  # Avoid matching long sentences
                                placeholders.append(f"[{inner}]")

                    # 4. Raw XML string scan for entities (fallback for encoding edge cases)
                    raw_xml = xml_content.decode("utf-8", errors="ignore")
                    for pat, prefix, suffix in [
                        (r"&#171;(.*?)&#187;", "«", "»"),
                        (r"&laquo;(.*?)&raquo;", "«", "»"),
                    ]:
                        for m in re.finditer(pat, raw_xml):
                            inner = m.group(1).strip()
                            if inner:
                                placeholders.append(f"{prefix}{inner}{suffix}")

        except Exception as e:
            logger.error(f"Error deep-scanning docx XML: {e}")

        # Deduplicate while preserving order
        seen: set = set()
        unique = []
        for p in placeholders:
            ps = p.strip()
            if ps and ps not in seen:
                seen.add(ps)
                unique.append(ps)
        return unique

    def _detect_structural_hints(self, content: bytes) -> Dict[str, Any]:
        """
        Scans DOCX XML to detect structural and visual presentation hints:
        - Layout style: table_based, freeflow, or mixed
        - Instruction blocks: paragraphs with red/colored text (w:color) or italic style
        - Paste zones: headings that contain 'own cv', 'paste', 'insert cv'
        - Table loops: «TableStart:NAME» markers signaling mail-merge loops
        """
        hints: Dict[str, Any] = {
            "layout_style": "freeflow",
            "instruction_paragraphs": [],
            "paste_zone_headings": [],
            "table_loops": [],  # List of {loop_name, item_fields}
        }
        W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        ns = {"w": W_NS}
        W = f"{{{W_NS}}}"

        PASTE_ZONE_KEYWORDS = ["own cv", "paste", "insert cv", "candidate cv", "candidate's cv"]
        INSTRUCTION_COLOR_RED = {"ff0000", "ff0000", "c00000", "dc143c"}

        try:
            import io

            with zipfile.ZipFile(io.BytesIO(content)) as z:
                if "word/document.xml" not in z.namelist():
                    return hints

                xml_content = z.read("word/document.xml")
                root = ET.fromstring(xml_content)

                # 1. Layout style: count tables vs non-table paragraphs
                table_count = len(root.xpath("//w:tbl", namespaces=ns))
                para_count = len(root.xpath("//w:p", namespaces=ns))
                if table_count > 0 and para_count > 0:
                    hints["layout_style"] = "mixed" if para_count > table_count * 3 else "table_based"
                elif table_count > 0:
                    hints["layout_style"] = "table_based"

                # 2. Detect instruction blocks (colored / italic paragraphs)
                for para in root.xpath("//w:p", namespaces=ns):
                    run_texts = [t.text or "" for t in para.xpath(".//w:t", namespaces=ns)]
                    para_text = "".join(run_texts).strip()
                    if not para_text or len(para_text) < 10:
                        continue

                    is_instruction = False

                    # Check for red/colored runs
                    for color_el in para.xpath(".//w:color", namespaces=ns):
                        color_val = (color_el.get(f"{W}val") or "").lower()
                        if color_val in INSTRUCTION_COLOR_RED or (color_val not in ("auto", "000000", "") and color_val != "auto"):
                            is_instruction = True
                            break

                    # Check for italic-only runs (common for instruction text)
                    italic_runs = para.xpath(".//w:i", namespaces=ns)
                    if italic_runs and not is_instruction:
                        # Only flag if ALL content is italic (instruction style)
                        total_runs = para.xpath(".//w:r", namespaces=ns)
                        if total_runs and len(italic_runs) >= len(total_runs):
                            is_instruction = True

                    # Check for quoted instruction text
                    if not is_instruction and para_text.startswith('"') and para_text.endswith('"') and len(para_text) > 20:
                        is_instruction = True

                    if is_instruction and para_text not in hints["instruction_paragraphs"]:
                        hints["instruction_paragraphs"].append(para_text[:300])  # Truncate long ones

                # 3. Detect paste-zone headings (bold headings containing paste-zone keywords)
                for para in root.xpath("//w:p", namespaces=ns):
                    # Check heading style
                    style_el = para.xpath(".//w:pStyle", namespaces=ns)
                    is_heading = any(
                        (s.get(f"{W}val") or "").lower().startswith("heading")
                        for s in style_el
                    )
                    run_texts = [t.text or "" for t in para.xpath(".//w:t", namespaces=ns)]
                    para_text = "".join(run_texts).strip().lower()

                    # Check bold runs as proxy for headings
                    bold_els = para.xpath(".//w:b", namespaces=ns)
                    if (is_heading or bold_els) and any(kw in para_text for kw in PASTE_ZONE_KEYWORDS):
                        hints["paste_zone_headings"].append("".join(run_texts).strip())

                # 4. Detect table loops from MERGEFIELD instructions
                loop_names: Dict[str, list] = {}
                # Simple fields
                for fld in root.xpath("//w:fldSimple", namespaces=ns):
                    instr = fld.get(f"{W}instr") or ""
                    if "MERGEFIELD" in instr:
                        parts = instr.split()
                        if len(parts) >= 2:
                            name = parts[parts.index("MERGEFIELD") + 1]
                            if name.startswith("TableStart:"):
                                loop_name = name[len("TableStart:"):]
                                loop_names.setdefault(loop_name, [])
                            elif name.startswith("TableEnd:"):
                                pass  # already tracked
                            else:
                                # Could be a loop body field — associate with most recent loop
                                for ln in loop_names:
                                    if name not in loop_names[ln]:
                                        loop_names[ln].append(name)
                # Complex fields
                for instr_text in root.xpath("//w:instrText", namespaces=ns):
                    text = instr_text.text or ""
                    if "MERGEFIELD" in text:
                        parts = text.split()
                        if len(parts) >= 2:
                            name = parts[parts.index("MERGEFIELD") + 1]
                            if name.startswith("TableStart:"):
                                loop_name = name[len("TableStart:"):]
                                loop_names.setdefault(loop_name, [])
                            elif not name.startswith("TableEnd:"):
                                for ln in loop_names:
                                    if name not in loop_names[ln]:
                                        loop_names[ln].append(name)

                hints["table_loops"] = [
                    {"loop_name": k, "item_fields": v} for k, v in loop_names.items()
                ]

        except Exception as e:
            logger.error(f"Error detecting structural hints: {e}")

        return hints

    def _build_table_label_context(self, extracted_doc) -> str:
        """
        Builds a structured text block describing table label→value pairs from
        the document's structured_data. This gives the AI richer context to
        map labels (e.g. 'Current salary & benefits') to the correct markers.
        """
        if not extracted_doc or not extracted_doc.structured_data:
            return ""
        items = extracted_doc.structured_data.get("items", [])
        tables = [item for item in items if item.get("role") == "table"]
        if not tables:
            return ""

        lines = ["\n[STRUCTURED TABLE LABEL→VALUE PAIRS]"]
        for table in tables:
            cells = table.get("cells", [])
            # Build row-column grid
            rows: Dict[int, Dict[int, str]] = {}
            for cell in cells:
                r, c = cell.get("row_index", 0), cell.get("column_index", 0)
                txt = cell.get("text", "").strip()
                rows.setdefault(r, {})[c] = txt
            # Emit as label: value pairs (col 0 = label, col 1 = value/marker)
            for r_idx in sorted(rows.keys()):
                row = rows[r_idx]
                cols = sorted(row.keys())
                if len(cols) >= 2:
                    label = row.get(cols[0], "").rstrip(":")
                    value = row.get(cols[1], "")
                    if label:
                        lines.append(f"  LABEL: '{label}'  →  VALUE/MARKER: '{value}'")
        lines.append("[END TABLE PAIRS]")
        return "\n".join(lines)

    async def analyze_template(self, content: bytes, filename: str) -> Dict[str, Any]:
        """
        Analyzes a .docx template using a 3-phase pipeline:
        1. Deterministic extraction (TemplateStructureExtractor)
        2. LLM semantic interpretation (Claude Sonnet, temp=0)
        3. Deterministic reconciliation + validation
        """
        from app.services.template_structure_extractor import (
            TemplateStructureExtractor, FIELD_ALIAS_MAP, canonical_marker, normalize_marker_name
        )
        from app.services.template_manifest_validator import TemplateManifestValidator

        if not self.extraction_service:
            return {}

        # ── Phase 1: Deterministic structure extraction ──────────────────────
        extractor = TemplateStructureExtractor()
        structure = extractor.extract(content, filename)

        detected_markers = structure.detected_markers
        logger.info(f"[TemplateAnalysis] Detected {len(detected_markers)} markers: {detected_markers}")
        logger.info(f"[TemplateAnalysis] Blank label slots: {structure.blank_label_slots}")
        logger.info(f"[TemplateAnalysis] Table loops: {[l.loop_name for l in structure.table_loops]}")
        logger.info(f"[TemplateAnalysis] Layout: {structure.layout_style}")

        # ── Phase 1b: Docling text extraction for semantic context ────────────
        extracted_doc = await self.extraction_service.extract(
            content,
            filename,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        text_content = extracted_doc.extracted_text or ""

        # ── Phase 1c: Build rich context block for the LLM ───────────────────
        context_blocks: List[str] = []

        # Structural hints block
        hints_block = "[STRUCTURAL HINTS FROM DOCX ANALYSIS]\n"
        hints_block += f"Layout Style: {structure.layout_style}\n"

        if structure.table_loops:
            hints_block += "Table Loops Detected (field_type=table_loop):\n"
            for loop in structure.table_loops:
                hints_block += f"  - Loop '{loop.loop_name}' with item fields: {loop.item_fields}\n"

        if structure.paste_zones:
            hints_block += "Paste Zone Headings (field_type=paste_zone):\n"
            for pz in structure.paste_zones:
                hints_block += f"  - '{pz}'\n"

        if structure.instruction_blocks:
            hints_block += "Instruction Block Paragraphs (field_type=instruction_block, clear at render):\n"
            for inst in structure.instruction_blocks:
                hints_block += f"  - '{inst[:200]}'\n"

        if structure.bullet_slots:
            hints_block += "Bullet Slot Sections (source_kind=bullet_slots, array_simple):\n"
            for bs in structure.bullet_slots:
                hints_block += f"  - Heading: '{bs}'\n"

        hints_block += "[END STRUCTURAL HINTS]\n"
        context_blocks.append(hints_block)

        # Table label→value pairs block
        if structure.table_label_value_pairs:
            pairs_block = "[STRUCTURED TABLE LABEL→VALUE PAIRS]\n"
            pairs_block += "LABEL | VALUE/MARKER | BLANK?\n"
            pairs_block += "-" * 60 + "\n"
            for slot in structure.table_label_value_pairs:
                pairs_block += f"{slot.label} | {slot.marker or '[blank]'} | {slot.is_blank}\n"
            pairs_block += "[END TABLE PAIRS]\n"
            context_blocks.append(pairs_block)

        # Hidden markers not visible in extracted text
        hidden = [
            m for m in detected_markers
            if m not in text_content and m.strip("«»[] ") not in text_content
        ]
        if hidden:
            hidden_block = "[HIDDEN MARKERS IN DOCUMENT XML — must be assigned to fields]\n"
            for m in hidden:
                inner = m.strip("«»[] ")
                hidden_block += f"  Marker: {m} → field alias: '{inner}'\n"
            hidden_block += "[END HIDDEN MARKERS]\n"
            context_blocks.append(hidden_block)

        full_context = "\n".join(context_blocks) + "\n\n" + text_content

        # ── Phase 2: LLM semantic analysis (Claude Sonnet, temp=0) ───────────
        SYSTEM_PROMPT = (
            "You are a document structure analyst. Your output MUST be a single valid JSON object. "
            "No markdown, no code fences, no prose. Start with { and end with }. "
            "Never invent marker_text values — they must exactly match the DETECTED MARKERS list. "
            "Never use label text like 'Candidate name' as a marker_text value. "
            "For blank table cells, use source_kind=visual_blank_slot and provide render_locator.label."
        )

        # ── Build dynamic examples from actual detected structure ─────────────
        # These replace hardcoded examples in the prompt — every example shown
        # to the LLM is derived from THIS template's structure.
        from app.services.template_structure_extractor import FIELD_ALIAS_MAP as _alias_map_for_prompt

        _alias_inverted_prompt = {
            alias.lower(): fn
            for fn, aliases in _alias_map_for_prompt.items()
            for alias in aliases
        }

        def _marker_to_fieldname(marker: str) -> str:
            inner = marker.strip("«»[] ")
            from_alias = _alias_inverted_prompt.get(inner.lower())
            if from_alias:
                return from_alias
            return normalize_marker_name(marker).replace(" ", "_") or inner.lower()

        # Merge marker examples — pick first 3 non-loop markers
        example_merge_markers = []
        for m in detected_markers[:8]:
            inner = m.strip("«»[] ")
            if inner.startswith("TableStart:") or inner.startswith("TableEnd:"):
                continue
            example_merge_markers.append({
                "marker": m,
                "fieldname": _marker_to_fieldname(m),
            })
            if len(example_merge_markers) >= 3:
                break

        # Blank slot examples — pick first 2
        example_blank_slots = []
        for slot in structure.table_label_value_pairs[:5]:
            if slot.is_blank and not slot.marker:
                fn_derived = re.sub(r"[^a-z0-9]+", "_", slot.label.lower()).strip("_")
                example_blank_slots.append({"label": slot.label, "fieldname": fn_derived})
                if len(example_blank_slots) >= 2:
                    break

        # Table loop examples
        example_table_loops = [
            {"loop_name": l.loop_name, "item_fields": l.item_fields}
            for l in structure.table_loops[:2]
        ]

        # Paste zone examples
        example_paste_zones = structure.paste_zones[:2]

        # Instruction block examples
        example_instructions = structure.instruction_blocks[:2]

        prompt = prompt_manager.get_prompt(
            "template_analysis.jinja2",
            template_text=full_context[:14000],
            detected_placeholders=detected_markers,
            example_merge_markers=example_merge_markers,
            example_blank_slots=example_blank_slots,
            example_table_loops=example_table_loops,
            example_paste_zones=example_paste_zones,
            example_instructions=example_instructions,
        )

        logger.info("\n" + "=" * 60 + "\n--- TEMPLATE ANALYSIS PROMPT ---\n" + "=" * 60)
        logger.info(prompt)
        logger.info("=" * 60 + "\n")

        response = self.llm.generate(
            prompt,
            system_prompt=SYSTEM_PROMPT,
            task_name="template_analysis",
            temperature=settings.bedrock_temperature_template_analysis,
            max_tokens=settings.bedrock_max_output_tokens_template_analysis,
        )
        
        logger.info("\n" + "=" * 60 + "\n--- TEMPLATE ANALYSIS RESPONSE ---\n" + "=" * 60)
        logger.info(response)
        logger.info("=" * 60 + "\n")

        try:
            cleaned_json = LlmSanitizer.clean_json(response)
            data = json.loads(cleaned_json)
        except Exception as e:
            logger.error(f"[TemplateAnalysis] Failed to parse LLM JSON response: {e}")
            data = {}

        manifest: List[Dict[str, Any]] = data.get("field_extraction_manifest", [])
        if not isinstance(manifest, list):
            manifest = []

        # ── Phase 3: Deterministic reconciliation ─────────────────────────────
        # Build a fast lookup: normalised_marker_name → canonical marker string
        norm_to_marker: Dict[str, str] = {}
        for m in detected_markers:
            norm_to_marker[normalize_marker_name(m)] = m
            # Also index by inner name directly
            inner = m.strip("«»[] ")
            norm_to_marker[inner.lower()] = m

        # Build inverted alias: CamelCase alias → fieldname
        alias_inverted: Dict[str, str] = {}
        for fn, aliases in FIELD_ALIAS_MAP.items():
            for alias in aliases:
                alias_inverted[alias.lower()] = fn

        # Track which detected markers are already used
        used_markers: set = {
            e.get("marker_text", "").strip()
            for e in manifest
            if e.get("marker_text", "").strip()
        }

        for entry in manifest:
            fn = entry.get("fieldname", "")
            mt = (entry.get("marker_text") or "").strip()
            sk = entry.get("source_kind", "")

            # Skip instruction blocks
            if entry.get("field_type") == "instruction_block":
                continue

            # Validate existing marker_text
            if mt:
                if mt not in detected_markers:
                    # Try canonical wrap
                    canonical = canonical_marker(mt.strip("«»[] "))
                    if canonical in detected_markers:
                        logger.info(f"[Reconcile] Fixed wrapping: '{mt}' → '{canonical}' for '{fn}'")
                        entry["marker_text"] = canonical
                        mt = canonical
                    else:
                        logger.warning(f"[Reconcile] Hallucinated marker '{mt}' for '{fn}' — clearing.")
                        entry["marker_text"] = ""
                        mt = ""
                continue  # marker is valid, move on

            # marker_text is empty — run alias-based reconciliation
            if sk in ("visual_blank_slot", "bullet_slots", "paste_zone", "instruction_block", "section_body"):
                continue  # these legitimately have no marker

            # Try alias map first (high confidence)
            if fn in FIELD_ALIAS_MAP:
                for alias in FIELD_ALIAS_MAP[fn]:
                    canonical = f"«{alias}»"
                    if canonical in detected_markers and canonical not in used_markers:
                        entry["marker_text"] = canonical
                        entry["source_kind"] = "merge_marker"
                        entry.setdefault("render_locator", {})["strategy"] = "replace_marker"
                        entry.setdefault("render_locator", {})["marker"] = canonical
                        used_markers.add(canonical)
                        logger.info(f"[Reconcile] Alias matched: '{fn}' → '{canonical}'")
                        break

            # If still empty, try normalized name matching
            if not entry.get("marker_text"):
                fn_norm = normalize_marker_name(fn)
                if fn_norm in norm_to_marker:
                    m_candidate = norm_to_marker[fn_norm]
                    if m_candidate not in used_markers:
                        entry["marker_text"] = m_candidate
                        entry["source_kind"] = "merge_marker"
                        used_markers.add(m_candidate)
                        logger.info(f"[Reconcile] Norm matched: '{fn}' → '{m_candidate}'")

        # ── Phase 3b: Add any completely missed detected markers ──────────────
        for m in detected_markers:
            if m in used_markers:
                continue
            # Skip loop boundary markers
            inner = m.strip("«»[] ")
            if inner.startswith("TableStart:") or inner.startswith("TableEnd:"):
                continue

            # Try to find a known fieldname via alias
            fn_for_marker = None
            for fn_alias, aliases in FIELD_ALIAS_MAP.items():
                if inner in aliases:
                    fn_for_marker = fn_alias
                    break

            if not fn_for_marker:
                # Derive from the inner name
                fn_for_marker = normalize_marker_name(m).replace(" ", "_")

            manifest.append({
                "fieldname": fn_for_marker,
                "field_type": "scalar",
                "source_kind": "merge_marker",
                "marker_text": m,
                "render_locator": {"strategy": "replace_marker", "marker": m, "label": "", "heading": ""},
                "meaning": f"Auto-recovered: {inner}",
                "source_hints": f"Detected in DOCX XML as {m}",
                "required": False,
                "confidence": 0.6,
            })
            used_markers.add(m)
            logger.info(f"[Reconcile] Auto-added missed marker: {m} → '{fn_for_marker}'")

        # ── Phase 3c: Ensure visual_blank_slots from structure are in manifest ─
        manifest_labels = {
            (e.get("render_locator") or {}).get("label", "").lower()
            for e in manifest
        }
        for slot in structure.table_label_value_pairs:
            if slot.is_blank and not slot.marker and slot.label.lower() not in manifest_labels:
                fn_derived = re.sub(r"[^a-z0-9]+", "_", slot.label.lower()).strip("_")
                manifest.append({
                    "fieldname": fn_derived,
                    "field_type": "scalar",
                    "source_kind": "visual_blank_slot",
                    "marker_text": "",
                    "render_locator": {
                        "strategy": "fill_blank_cell_after_label",
                        "marker": "",
                        "label": slot.label,
                        "heading": "",
                    },
                    "meaning": f"Value for '{slot.label}' label in template table",
                    "source_hints": f"Table row labelled '{slot.label}'",
                    "required": False,
                    "confidence": 0.7,
                })
                logger.info(f"[Reconcile] Added visual_blank_slot for label '{slot.label}'")

        # ── Phase 4: Manifest validation ─────────────────────────────────────
        validator = TemplateManifestValidator()
        validation_result = validator.validate(manifest, detected_markers)
        logger.info(f"[TemplateAnalysis] Validation: {validation_result.to_dict()}")
        if validation_result.status == "FAIL":
            logger.error(f"[TemplateAnalysis] Manifest FAILED validation: {validation_result.errors}")

        # ── Assemble final result ─────────────────────────────────────────────
        expected_sections = data.get("expected_sections") or []
        if isinstance(expected_sections, list):
            expected_sections_str = ", ".join(expected_sections)
        else:
            expected_sections_str = str(expected_sections)

        fields = [m.get("fieldname") for m in manifest if m.get("fieldname")]
        expected_fields_str = ", ".join(fields)

        return {
            "purpose": data.get("purpose") or "General Template",
            "expected_sections": expected_sections_str,
            "expected_fields": expected_fields_str,
            "summary_guidance": data.get("summary_guidance", ""),
            "formatting_guidance": data.get("formatting_guidance", ""),
            "validation_guidance": data.get("validation_guidance", ""),
            "pii_guidance": data.get("pii_guidance", ""),
            "layout_analysis": data.get("layout_analysis", {"layout_style": structure.layout_style}),
            "field_extraction_manifest": manifest,
            "_validation": validation_result.to_dict(),
        }



    async def harmonize_data_to_template_style(
        self,
        structured_data: Dict[str, Any],
        template_text: str,
        detected_placeholders: List[str],
        field_manifest: List[Dict[str, Any]],
        formatting_guidance: str = "",
        job_id: str = "N/A",
    ) -> Dict[str, Any]:
        """Restored method to map resume data to the template contract."""

        prompt = prompt_manager.get_prompt(
            "data_linearization.jinja2",
            structured_data_json=json.dumps(structured_data, indent=2),
            field_extraction_manifest=field_manifest,
            detected_placeholders_list=detected_placeholders,
            formatting_guidance=formatting_guidance,
            template_text=template_text[:4000],
            job_id=job_id,
        )

        logger.info(
            "\n" + "=" * 60 + "\n--- DATA LINEARIZATION PROMPT ---\n" + "=" * 60
        )
        logger.info(prompt)
        logger.info("=" * 60 + "\n")

        response = self.llm.generate(prompt)

        logger.info(
            "\n" + "=" * 60 + "\n--- DATA LINEARIZATION LLM RESPONSE ---\n" + "=" * 60
        )
        logger.info(response)
        logger.info("=" * 60 + "\n")

        try:
            cleaned_json = LlmSanitizer.clean_json(response)
            logger.info("\n" + "=" * 60 + "\n--- CLEANED JSON ---\n" + "=" * 60)
            logger.info(cleaned_json)
            logger.info("=" * 60 + "\n")
            data = json.loads(cleaned_json)

            logger.info(
                "\n" + "=" * 60 + "\n--- FINAL HARMONIZED DATA ---\n" + "=" * 60
            )
            logger.info(data)
            logger.info("=" * 60 + "\n")

            return data
        except Exception as e:
            logger.error(f"Failed to parse harmonized data JSON: {e}")
            # Fallback: Return raw data if AI fails
            return structured_data

    async def apply_composition_logic(self, harmonized_data: Dict[str, Any], template_text: str, manifest: List[Dict[str, Any]] = None, formatting_guidance: str = "") -> Dict[str, Any]:
        """Performs a secondary formatting and professional phrasing pass."""
        
        prompt = prompt_manager.get_prompt(
            "composition_logic.jinja2",
            harmonized_json=json.dumps(harmonized_data, indent=2),
            manifest_json=json.dumps(manifest, indent=2) if manifest else "None",
            formatting_guidance=formatting_guidance,
            template_text=template_text[:3000]
        )
        
        logger.info("\n" + "="*60 + "\n--- COMPOSITION LOGIC PROMPT ---\n" + "="*60)
        logger.info(prompt)
        logger.info("="*60 + "\n")
        
        response = self.llm.generate(prompt)
        
        logger.info("\n" + "="*60 + "\n--- COMPOSITION LOGIC LLM RESPONSE ---\n" + "="*60)
        logger.info(response)
        logger.info("="*60 + "\n")
        
        try:
            cleaned_json = LlmSanitizer.clean_json(response)
            data = json.loads(cleaned_json)
            
            logger.info("\n" + "=" * 60 + "\n--- FINAL COMPOSITION DATA ---\n" + "=" * 60)
            logger.info(data)
            logger.info("=" * 60 + "\n")
            
            return data
        except Exception as e:
            logger.error(f"Failed to parse composition logic JSON: {e}")
            return harmonized_data

    async def linearize_data(
        self, structured_data: Dict[str, Any], template_metadata: Dict[str, Any]
    ) -> str:
        """Linearizes structured resume data into a narrative format (Legacy support)."""
        result = await self.harmonize_data_to_template_style(
            structured_data=structured_data,
            template_text="",
            detected_placeholders=template_metadata.get("expected_fields", "").split(
                ", "
            ),
            field_manifest=template_metadata.get("field_extraction_manifest", []),
        )
        return json.dumps(result)
