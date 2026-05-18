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

        logger.info(
            "\n" + "=" * 60 + "\n--- GENERATE SUMMARY RESPONSE ---\n" + "=" * 60
        )
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
            "word/header1.xml",
            "word/header2.xml",
            "word/header3.xml",
            "word/footer1.xml",
            "word/footer2.xml",
            "word/footer3.xml",
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
                                placeholders.append(
                                    parts[parts.index("MERGEFIELD") + 1]
                                )

                    # 2. MERGEFIELD complex fields (w:instrText)
                    for instr_text in root.xpath("//w:instrText", namespaces=ns):
                        text = instr_text.text
                        if text and "MERGEFIELD" in text:
                            parts = text.split()
                            if len(parts) >= 2:
                                placeholders.append(
                                    parts[parts.index("MERGEFIELD") + 1]
                                )

                    # 3. Reconstruct paragraph text across split <w:r> runs to find «...» markers
                    #    Word often splits a single cell value across many runs, breaking naive regex.
                    for para in root.xpath("//w:p", namespaces=ns):
                        # Concatenate all w:t text within this paragraph
                        run_texts = [
                            t.text or "" for t in para.xpath(".//w:t", namespaces=ns)
                        ]
                        para_text = "".join(run_texts)
                        # Now scan the reconstructed text for guillemet markers
                        for m in re.finditer(r"«\s*(.*?)\s*»", para_text):
                            placeholders.append(f"«{m.group(1).strip()}»")
                        # Also scan for bracketed forms
                        for m in re.finditer(r"\[\s*([^\]\s][^\]]*?)\s*\]", para_text):
                            inner = m.group(1).strip()
                            if (
                                inner and len(inner) < 80
                            ):  # Avoid matching long sentences
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

        PASTE_ZONE_KEYWORDS = [
            "own cv",
            "paste",
            "insert cv",
            "candidate cv",
            "candidate's cv",
        ]
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
                    hints["layout_style"] = (
                        "mixed" if para_count > table_count * 3 else "table_based"
                    )
                elif table_count > 0:
                    hints["layout_style"] = "table_based"

                # 2. Detect instruction blocks (colored / italic paragraphs)
                for para in root.xpath("//w:p", namespaces=ns):
                    run_texts = [
                        t.text or "" for t in para.xpath(".//w:t", namespaces=ns)
                    ]
                    para_text = "".join(run_texts).strip()
                    if not para_text or len(para_text) < 10:
                        continue

                    is_instruction = False

                    # Check for red/colored runs
                    for color_el in para.xpath(".//w:color", namespaces=ns):
                        color_val = (color_el.get(f"{W}val") or "").lower()
                        if color_val in INSTRUCTION_COLOR_RED or (
                            color_val not in ("auto", "000000", "")
                            and color_val != "auto"
                        ):
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
                    if (
                        not is_instruction
                        and para_text.startswith('"')
                        and para_text.endswith('"')
                        and len(para_text) > 20
                    ):
                        is_instruction = True

                    if (
                        is_instruction
                        and para_text not in hints["instruction_paragraphs"]
                    ):
                        hints["instruction_paragraphs"].append(
                            para_text[:300]
                        )  # Truncate long ones

                # 3. Detect paste-zone headings (bold headings containing paste-zone keywords)
                for para in root.xpath("//w:p", namespaces=ns):
                    # Check heading style
                    style_el = para.xpath(".//w:pStyle", namespaces=ns)
                    is_heading = any(
                        (s.get(f"{W}val") or "").lower().startswith("heading")
                        for s in style_el
                    )
                    run_texts = [
                        t.text or "" for t in para.xpath(".//w:t", namespaces=ns)
                    ]
                    para_text = "".join(run_texts).strip().lower()

                    # Check bold runs as proxy for headings
                    bold_els = para.xpath(".//w:b", namespaces=ns)
                    if (is_heading or bold_els) and any(
                        kw in para_text for kw in PASTE_ZONE_KEYWORDS
                    ):
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
                                loop_name = name[len("TableStart:") :]
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
                                loop_name = name[len("TableStart:") :]
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
            TemplateStructureExtractor,
            FIELD_ALIAS_MAP,
            canonical_marker,
            normalize_marker_name,
        )
        from app.services.template_manifest_validator import TemplateManifestValidator

        if not self.extraction_service:
            return {}

        # ── Phase 1: Deterministic structure extraction ──────────────────────
        extractor = TemplateStructureExtractor()
        structure = extractor.extract(content, filename)

        detected_markers = structure.detected_markers
        logger.info(
            f"[TemplateAnalysis] Detected {len(detected_markers)} markers: {detected_markers}"
        )
        logger.info(
            f"[TemplateAnalysis] Blank label slots: {structure.blank_label_slots}"
        )
        logger.info(
            f"[TemplateAnalysis] Table loops: {[l.loop_name for l in structure.table_loops]}"
        )
        logger.info(f"[TemplateAnalysis] Layout: {structure.layout_style}")

        # ── Phase 1b: Docling text extraction for semantic context ────────────
        extracted_doc = await self.extraction_service.extract(
            content,
            filename,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        logger.info(
            "\n" + "=" * 60 + "\n--- DOCLING EXTRACTION RESULT ---\n" + "=" * 60
        )
        logger.info(extracted_doc.extracted_text or "No text extracted")
        logger.info("=" * 60 + "\n")

        text_content = extracted_doc.extracted_text or ""

        # ── Phase 1c: Build rich context block for the LLM ───────────────────
        context_blocks: List[str] = []

        # Structural hints block
        hints_block = "[STRUCTURAL HINTS FROM DOCX ANALYSIS]\n"
        hints_block += f"Layout Style: {structure.layout_style}\n"
        hints_block += f"Paste Zone Headings: {structure.paste_zones}\n"
        hints_block += (
            f"Table Loops Detected: {[l.to_dict() for l in structure.table_loops]}\n"
        )
        hints_block += f"ALL_HEADINGS: {structure.all_headings}\n"
        hints_block += f"ALL_TABLE_LABELS: {structure.all_table_labels}\n"
        hints_block += f"REPEATED_MARKERS: {structure.repeated_markers}\n"

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
            hints_block += (
                "Bullet Slot Sections (source_kind=bullet_slots, array_simple):\n"
            )
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
                pairs_block += f"{slot.label} | {slot.marker_text or '[blank]'} | {slot.is_blank}\n"
            pairs_block += "[END TABLE PAIRS]\n"
            context_blocks.append(pairs_block)

        # Hidden markers not visible in extracted text
        hidden = [
            m
            for m in detected_markers
            if m not in text_content and m.strip("«»[] ") not in text_content
        ]
        if hidden:
            hidden_block = (
                "[HIDDEN MARKERS IN DOCUMENT XML — must be assigned to fields]\n"
            )
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
        from app.services.template_structure_extractor import (
            FIELD_ALIAS_MAP as _alias_map_for_prompt,
        )

        _alias_inverted_prompt = {
            alias.lower(): fn
            for fn, info in _alias_map_for_prompt.items()
            for alias in info["aliases"]
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
            example_merge_markers.append(
                {
                    "marker": m,
                    "fieldname": _marker_to_fieldname(m),
                }
            )
            if len(example_merge_markers) >= 3:
                break

        # Blank slot examples — pick first 2
        example_blank_slots = []
        for slot in structure.table_label_value_pairs[:5]:
            if slot.is_blank and not slot.marker_text:
                fn_derived = re.sub(r"[^a-z0-9]+", "_", slot.label.lower()).strip("_")
                example_blank_slots.append(
                    {"label": slot.label, "fieldname": fn_derived}
                )
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

        logger.info(
            "\n" + "=" * 60 + "\n--- TEMPLATE ANALYSIS RESPONSE ---\n" + "=" * 60
        )
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
        for fn, info in FIELD_ALIAS_MAP.items():
            if not isinstance(info, dict):
                continue
            for alias in info.get("aliases", []):
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
                        logger.info(
                            f"[Reconcile] Fixed wrapping: '{mt}' → '{canonical}' for '{fn}'"
                        )
                        entry["marker_text"] = canonical
                        mt = canonical
                    else:
                        # Try to heal by normalization match
                        mt_norm = normalize_marker_name(mt)
                        if mt_norm in norm_to_marker:
                            actual = norm_to_marker[mt_norm]
                            logger.info(
                                f"[Reconcile] Fixed AI marker typo: '{mt}' -> '{actual}' for '{fn}'"
                            )
                            entry["marker_text"] = actual
                            mt = actual
                        else:
                            logger.warning(
                                f"[Reconcile] Hallucinated marker '{mt}' for '{fn}' — clearing."
                            )
                            entry["marker_text"] = ""
                            mt = ""
                continue  # marker is valid, move on

            # marker_text is empty — run alias-based reconciliation
            if sk in (
                "bullet_slots",
                "paste_zone",
                "instruction_block",
                "section_body",
            ):
                continue  # these legitimately have no marker

            # Note: visual_blank_slot IS allowed to proceed here so we can "upgrade" it
            # if we find a detected marker that matches its fieldname/alias.

            # Try alias map first (high confidence)
            if fn in FIELD_ALIAS_MAP:
                info = FIELD_ALIAS_MAP[fn]
                if isinstance(info, dict):
                    for alias in info.get("aliases", []):
                        # Try all common wrappings to find the actual marker in the document
                        potential_matches = [
                            f"«{alias}»",
                            f"[{alias}]",
                            f"[[{alias}]]",
                            f"<<{alias}>>",
                            f"{{{alias}}}",
                            alias,
                        ]

                    found_marker = next(
                        (
                            m
                            for m in potential_matches
                            if m in detected_markers and m not in used_markers
                        ),
                        None,
                    )

                    if found_marker:
                        entry["marker_text"] = found_marker
                        entry["source_kind"] = "merge_marker"
                        entry["field_type"] = info.get("type", "scalar")
                        entry.setdefault("render_locator", {})[
                            "strategy"
                        ] = "replace_marker"
                        entry.setdefault("render_locator", {})["marker"] = found_marker
                        used_markers.add(found_marker)
                        logger.info(
                            f"[Reconcile] Alias matched: '{fn}' → '{found_marker}' (Upgraded from {sk}, type={entry['field_type']})"
                        )
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
                        logger.info(
                            f"[Reconcile] Norm matched: '{fn}' → '{m_candidate}'"
                        )

        # ── Phase 3c: Harden against hallucinations ───────────────────────────
        actual_paste_zone_headings = set(structure.paste_zones or [])
        known_headings = set(structure.all_headings or [])
        known_labels = set(structure.all_table_labels or [])

        reconciled_manifest = []
        for entry in manifest:
            fieldname = entry.get("fieldname", "")
            ft = entry.get("field_type", "")
            locator = entry.get("render_locator") or {}
            strategy = locator.get("strategy", "")
            heading = locator.get("heading", "")
            label = locator.get("label", "")
            mt = entry.get("marker_text", "")

            drop_reason = None

            # 1. Paste Zone Guard
            if ft == "paste_zone":
                if heading not in actual_paste_zone_headings:
                    drop_reason = f"hallucinated paste_zone heading '{heading}'"

            # 2. Heading Guard
            if strategy in ("replace_section_body", "replace_bullets_under_heading"):
                if heading and heading not in known_headings:
                    drop_reason = f"hallucinated heading '{heading}'"

            # 3. Label Guard
            if strategy == "fill_blank_cell_after_label":
                if label and label not in known_labels:
                    drop_reason = f"hallucinated table label '{label}'"

            # 4. Repeated Marker Context Enforcement & Healing
            if mt in structure.repeated_markers and strategy == "replace_marker":
                # Try to heal by finding a label that maps to this field
                found_label = next(
                    (
                        s.label
                        for s in structure.table_label_value_pairs
                        if s.marker_text == mt
                    ),
                    None,
                )
                if found_label:
                    logger.info(
                        f"[Reconcile] Healing repeated marker '{mt}' for '{fieldname}' using label context '{found_label}'."
                    )
                    entry["source_kind"] = "visual_blank_slot"
                    entry["render_locator"] = {
                        "strategy": "fill_blank_cell_after_label",
                        "label": found_label,
                    }
                    # We keep mt in marker_text for visibility
                else:
                    logger.warning(
                        f"[Reconcile] Field '{fieldname}' uses repeated marker '{mt}' without context strategy and no label found."
                    )

            # 5. Populate missing marker_text from structure for visibility
            if not mt:
                if (
                    strategy == "replace_section_body"
                    and heading in structure.heading_to_placeholder
                ):
                    entry["marker_text"] = structure.heading_to_placeholder[heading]
                    logger.info(
                        f"[Reconcile] Populated marker_text for section '{heading}': {entry['marker_text'][:40]}..."
                    )
                elif strategy == "fill_blank_cell_after_label":
                    # Find the marker that belongs to this label
                    slot = next(
                        (
                            s
                            for s in structure.table_label_value_pairs
                            if s.label == label
                        ),
                        None,
                    )
                    if slot and slot.marker_text:
                        entry["marker_text"] = slot.marker_text
                        logger.info(
                            f"[Reconcile] Populated marker_text for label '{label}': {slot.marker_text}"
                        )

            if drop_reason:
                logger.warning(
                    f"[Reconcile] Dropping field '{fieldname}': {drop_reason}"
                )
                continue

            reconciled_manifest.append(entry)

        manifest = reconciled_manifest

        # ── Phase 3d: Add any completely missed detected markers ──────────────
        for m in detected_markers:
            if m in used_markers:
                continue
            # Skip loop boundary markers
            inner = m.strip("«»[] ")
            if inner.startswith("TableStart:") or inner.startswith("TableEnd:"):
                continue

            # Try to find a known fieldname via alias using normalized comparison
            fn_for_marker = None
            f_type = "scalar"
            m_norm = normalize_marker_name(m)
            # STRIP LOOP PREFIXES for alias matching (e.g. "table start certifications" -> "certifications")
            m_norm_clean = m_norm.replace("table start ", "").replace("table end ", "").replace("tablestart", "").replace("tableend", "").strip()
            
            for fn_alias, info in FIELD_ALIAS_MAP.items():
                if not isinstance(info, dict):
                    continue
                alias_list = [normalize_marker_name(a) for a in info.get("aliases", [])]
                if m_norm_clean in alias_list or normalize_marker_name(fn_alias) == m_norm_clean:
                    fn_for_marker = fn_alias
                    f_type = info.get("type", "scalar")
                    break

            if not fn_for_marker:
                # Derive from the inner name
                fn_for_marker = normalize_marker_name(m).replace(" ", "_")

            manifest.append(
                {
                    "fieldname": fn_for_marker,
                    "field_type": f_type,
                    "source_kind": "merge_marker",
                    "marker_text": m,
                    "render_locator": {"strategy": "replace_marker", "marker_text": m},
                    "meaning": f"Auto-recovered marker: {m}",
                    "confidence": 0.8,
                }
            )
            used_markers.add(m)
            logger.info(
                f"[Reconcile] Auto-added missed marker: {m} → '{fn_for_marker}'"
            )

        # ── Phase 3c: Ensure visual_blank_slots from structure are in manifest ─
        manifest_labels = {
            (e.get("render_locator") or {}).get("label", "").lower() for e in manifest
        }
        for slot in structure.table_label_value_pairs:
            if (
                slot.is_blank
                and not slot.marker_text
                and slot.label.lower() not in manifest_labels
            ):
                fn_derived = re.sub(r"[^a-z0-9]+", "_", slot.label.lower()).strip("_")
                manifest.append(
                    {
                        "fieldname": fn_derived,
                        "field_type": "scalar",
                        "source_kind": "visual_blank_slot",
                        "marker_text": slot.marker_text,
                        "render_locator": {
                            "strategy": "fill_blank_cell_after_label",
                            "marker_text": slot.marker_text,
                            "label": slot.label,
                            "heading": "",
                        },
                        "meaning": f"Value for '{slot.label}' label in template table",
                        "source_hints": f"Table row labelled '{slot.label}' (contains {slot.marker_text if slot.marker_text else 'blank'})",
                        "required": False,
                        "confidence": 0.7,
                    }
                )
                logger.info(
                    f"[Reconcile] Added visual_blank_slot for label '{slot.label}' with marker '{slot.marker_text}'"
                )

        # ── Phase 4: Manifest validation ─────────────────────────────────────
        validator = TemplateManifestValidator()
        validation_result = validator.validate(manifest, structure)
        logger.info(f"[TemplateAnalysis] Validation: {validation_result.to_dict()}")
        if validation_result.status == "FAIL":
            logger.error(
                f"[TemplateAnalysis] Manifest FAILED validation: {validation_result.errors}"
            )

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
            "layout_analysis": data.get(
                "layout_analysis", {"layout_style": structure.layout_style}
            ),
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
        if isinstance(field_manifest, str):
            try:
                field_manifest = json.loads(field_manifest)
            except Exception:
                field_manifest = []

        if isinstance(field_manifest, dict):
            if "fields" in field_manifest:
                field_manifest = field_manifest["fields"]
            else:
                field_manifest = list(field_manifest.values())

        logger.info(f"Harmonize Request: Manifest has {len(field_manifest) if field_manifest else 'None'} fields.")
        
        prompt = prompt_manager.get_prompt(
            "data_linearization.jinja2",
            structured_data_json=json.dumps(structured_data, indent=2),
            field_extraction_manifest=field_manifest,
            field_extraction_manifest_json=json.dumps(field_manifest, indent=2),
            detected_placeholders_list=detected_placeholders,
            formatting_guidance=formatting_guidance,
            template_text=template_text[:4000],
            job_id=job_id,
        )

        system_prompt = prompt_manager.get_prompt("data_mapping_system.jinja2")

        response = self.llm.generate(
            prompt,
            system_prompt=system_prompt,
            task_name="data_mapping",
            temperature=0.0,  # Deterministic mapping
            max_tokens=4096,
        )

        try:
            cleaned_json = LlmSanitizer.clean_json(response)
            logger.info("\n" + "=" * 60 + "\n--- CLEANED JSON ---\n" + "=" * 60)
            logger.info(cleaned_json)
            data = json.loads(cleaned_json)

            # --- MANIFEST-FIRST RECONSTRUCTION ---
            data = self._enforce_manifest_compliance(
                ai_output=data,
                field_manifest=field_manifest,
                detected_placeholders=detected_placeholders,
            )

            logger.info(
                "\n"
                + "=" * 60
                + "\n--- FINAL HARMONIZED DATA (HEALED) ---\n"
                + "=" * 60
            )
            logger.info(json.dumps(data, indent=2))
            logger.info("=" * 60 + "\n")

            return data
        except Exception as e:
            logger.error(f"Failed to parse harmonized data JSON: {e}")
            # Fallback: Return a skeleton dictionary based on the manifest instead of raw data
            # This ensures downstream nodes don't crash or process raw text as if it were mapped.
            fallback = {}
            if field_manifest:
                for f in field_manifest:
                    fn = f.get("fieldname")
                    if fn:
                        fallback[fn] = (
                            "" if f.get("field_type") != "array_complex" else []
                        )
            return fallback if fallback else structured_data

    def _enforce_manifest_compliance(
        self, 
        ai_output: Dict[str, Any], 
        field_manifest: List[Dict[str, Any]], 
        detected_placeholders: List[str] = None
    ) -> Dict[str, Any]:
        """
        Enforces strict schema validation, type checking, and mapping compliance on the AI output.
        Fills the structured `field_extraction_manifest` property for every field in the template manifest,
        generates the final `filled_template_manifest` candidate-specific resolved contract,
        and populates the detailed `template_fill_result` mapping for down-stream document generation.
        """
        logger.info("\n" + "=" * 80 + "\n[ManifestCompliance] STARTING HIGH-FIDELITY COMPLIANCE PROTOCOL\n" + "=" * 80)
        
        if isinstance(field_manifest, str):
            try:
                field_manifest = json.loads(field_manifest)
            except Exception:
                field_manifest = []

        if isinstance(field_manifest, dict):
            if "fields" in field_manifest:
                field_manifest = field_manifest["fields"]
            else:
                field_manifest = list(field_manifest.values())

        # 1. Gather all potential source data (flatten root and nested result)
        raw_nested = ai_output.get("template_fill_result", {})
        if not isinstance(raw_nested, dict): raw_nested = {}
        
        # Combined pool of candidate answers from the AI
        pool = {**ai_output, **raw_nested}
        
        # Remove metadata/control keys from the pool so they aren't treated as "data"
        control_keys = {
            "template_fill_result", "additional_resume_facts_available", 
            "missing_fields_requiring_recruiter_or_ats_input", "summary", 
            "job_id", "status", "_manifest", "filled_template_manifest"
        }
        for ck in control_keys:
            pool.pop(ck, None)

        final_fill_result = {}
        missing_fields = []
        filled_fields_list = []
        from app.services.template_structure_extractor import FIELD_ALIAS_MAP

        # 2. Determine ground truth manifest
        effective_manifest = field_manifest
        if effective_manifest is None and detected_placeholders:
            logger.info("[ManifestCompliance] No manifest provided. Using detected placeholders.")
            effective_manifest = [
                {
                    "fieldname": p.strip("«»[] ").replace(" ", "_"),
                    "marker_text": p,
                    "field_type": "scalar",
                    "meaning": f"Auto-detected placeholder: {p}",
                    "source_hints": "",
                    "render_locator": {
                        "strategy": "replace_marker",
                        "marker_text": p,
                        "label": "",
                        "heading": ""
                    }
                }
                for p in detected_placeholders
            ]

        # 3. Iterate Manifest and pull from Pool
        if effective_manifest:
            for field in effective_manifest:
                # Make a deep-ish copy of the field definition to avoid mutating the master template record
                field_def = dict(field)
                fieldname = field_def.get("fieldname")
                if not fieldname or field_def.get("field_type") == "instruction_block":
                    continue
                
                ftype = field_def.get("field_type", "scalar")
                marker = field_def.get("marker_text", f"«{fieldname}»")
                meaning = field_def.get("meaning", "")
                source_hints = field_def.get("source_hints", "")
                render_locator = field_def.get("render_locator") or {
                    "strategy": "replace_marker",
                    "marker_text": marker,
                    "label": "",
                    "heading": ""
                }
                required = field_def.get("required", False)

                logger.info(f"[ManifestCompliance] Processing field: '{fieldname}' | Type: {ftype} | Required: {required}")

                # Attempt to find the value in the pool
                ai_entry = None
                found_key = None
                
                # Try Exact Match
                if fieldname in pool:
                    ai_entry = pool.pop(fieldname)
                    found_key = fieldname
                else:
                    # Try Alias Match
                    fname_norm = fieldname.lower().replace("_", "")
                    aliases = [a.lower().replace("_", "") for a in FIELD_ALIAS_MAP.get(fieldname, {}).get("aliases", [])]
                    
                    for pool_key in list(pool.keys()):
                        pool_key_norm = pool_key.lower().replace("_", "").replace("tablestart", "").replace("tableend", "")
                        if pool_key_norm == fname_norm or pool_key_norm in aliases:
                            logger.info(f"[ManifestCompliance] Mapping pool key '{pool_key}' to manifest field '{fieldname}' via alias")
                            ai_entry = pool.pop(pool_key)
                            found_key = pool_key
                            break

                # Extract raw value, confidence, and source information from the AI entry
                raw_val = None
                confidence = 1.0
                source_sec = None
                evidence = None
                ai_status = None

                if ai_entry is not None:
                    if isinstance(ai_entry, dict):
                        # AI returned a structured object
                        # Check nested structure
                        if "field_extraction_manifest" in ai_entry:
                            fem = ai_entry["field_extraction_manifest"]
                            if isinstance(fem, dict):
                                raw_val = fem.get("value")
                                confidence = fem.get("confidence", 1.0)
                                ai_status = fem.get("status")
                                src = fem.get("source") or {}
                                if isinstance(src, dict):
                                    source_sec = src.get("resume_section")
                                    evidence = src.get("evidence")
                        
                        if raw_val is None:
                            raw_val = ai_entry.get("value")
                        if "confidence" in ai_entry and confidence == 1.0:
                            try:
                                confidence = float(ai_entry["confidence"])
                            except Exception:
                                pass
                        if "source" in ai_entry and source_sec is None:
                            src_val = ai_entry["source"]
                            if isinstance(src_val, dict):
                                source_sec = src_val.get("resume_section")
                                evidence = src_val.get("evidence")
                            else:
                                source_sec = str(src_val)
                        if "note" in ai_entry and evidence is None:
                            evidence = str(ai_entry["note"])
                        if "status" in ai_entry and ai_status is None:
                            ai_status = ai_entry["status"]
                    else:
                        # AI returned raw scalar value
                        raw_val = ai_entry

                # Validate and coerce values based on expected type
                validated_val = None
                val_type = "scalar"
                validation_warning = None

                if ftype == "scalar":
                    val_type = "scalar"
                    if raw_val is None or raw_val == "":
                        validated_val = None
                    elif isinstance(raw_val, (list, dict)):
                        validation_warning = f"Type mismatch: expected scalar, got {type(raw_val).__name__}."
                        # Coerce to string representation
                        validated_val = json.dumps(raw_val)
                    else:
                        validated_val = raw_val
                
                elif ftype == "rich_text":
                    val_type = "rich_text"
                    if raw_val is None or raw_val == "":
                        validated_val = None
                    elif isinstance(raw_val, (list, dict)):
                        validation_warning = f"Type mismatch: expected rich_text, got {type(raw_val).__name__}."
                        validated_val = json.dumps(raw_val)
                    else:
                        validated_val = str(raw_val)

                elif ftype == "array_simple":
                    val_type = "array"
                    if raw_val is None or raw_val == "" or raw_val == []:
                        validated_val = []
                    elif isinstance(raw_val, str):
                        # Coerce string to list of strings
                        validation_warning = "Coerced simple string to array."
                        # Split by comma or newline if present
                        if "\n" in raw_val:
                            validated_val = [line.strip().strip("•-* ").strip() for line in raw_val.split("\n") if line.strip()]
                        elif "," in raw_val:
                            validated_val = [item.strip() for item in raw_val.split(",") if item.strip()]
                        else:
                            validated_val = [raw_val.strip()]
                    elif isinstance(raw_val, list):
                        validated_val = [str(x) for x in raw_val if x is not None]
                    else:
                        validation_warning = f"Type mismatch: expected array_simple, got {type(raw_val).__name__}."
                        validated_val = [str(raw_val)]

                elif ftype == "complex_object":
                    val_type = "complex_object"
                    if raw_val is None or raw_val == "" or raw_val == {}:
                        validated_val = {}
                    elif isinstance(raw_val, dict):
                        validated_val = raw_val
                    else:
                        validation_warning = f"Type mismatch: expected complex_object (dict), got {type(raw_val).__name__}."
                        try:
                            # Try to parse string as json
                            validated_val = json.loads(str(raw_val))
                            if not isinstance(validated_val, dict):
                                validated_val = {"raw_value": str(raw_val)}
                        except Exception:
                            validated_val = {"raw_value": str(raw_val)}

                elif ftype == "array_complex":
                    val_type = "array_complex"
                    if raw_val is None or raw_val == "" or raw_val == []:
                        validated_val = []
                    elif isinstance(raw_val, list):
                        validated_val = []
                        for idx, x in enumerate(raw_val):
                            if isinstance(x, dict):
                                validated_val.append(x)
                            else:
                                validation_warning = f"Item at index {idx} in array_complex is not an object."
                                validated_val.append({"raw_value": str(x)})
                    else:
                        validation_warning = f"Type mismatch: expected array_complex, got {type(raw_val).__name__}."
                        validated_val = []

                elif ftype == "paste_zone":
                    # paste_zone is flexible, it can be rich_text or complex_object
                    if isinstance(raw_val, dict):
                        val_type = "complex_object"
                        validated_val = raw_val
                    else:
                        val_type = "rich_text"
                        validated_val = str(raw_val) if raw_val is not None else None

                # Detailed logging of validation warnings
                if validation_warning:
                    logger.warning(f"[ManifestCompliance] [VALIDATION WARNING] Field '{fieldname}': {validation_warning}")

                # Determine Extraction Status
                status = "not_found"
                reason = None

                is_empty = (
                    validated_val is None or 
                    validated_val == "" or 
                    validated_val == [] or 
                    validated_val == {}
                )

                if is_empty:
                    confidence = 0.0
                    if required:
                        status = "needs_user_input"
                        reason = f"Required field '{fieldname}' was not found in candidate's resume."
                    else:
                        status = "not_found"
                        reason = f"Field '{fieldname}' could not be located in candidate's resume."
                    
                    missing_fields.append(fieldname)
                    logger.info(f"[ManifestCompliance] Field '{fieldname}' is EMPTY. Status set to: {status}")
                else:
                    # Value is present, determine status
                    if ai_status in ["extracted", "inferred", "generated_from_resume", "needs_user_input"]:
                        status = ai_status
                    else:
                        # Automatically categorize based on field and confidence
                        if fieldname == "cv_comments":
                            status = "generated_from_resume"
                        elif confidence >= 0.85:
                            status = "extracted"
                        else:
                            status = "inferred"
                            reason = f"Value was mapped from section with lower confidence ({confidence})."

                    logger.info(f"[ManifestCompliance] Field '{fieldname}' is RESOLVED. Status: {status} | Confidence: {confidence}")

                # Build the structured field_extraction_manifest object
                source_obj = {
                    "resume_section": source_sec if source_sec else ("Full Resume" if not is_empty else None),
                    "evidence": evidence if evidence else (f"Extracted content for {fieldname}" if not is_empty else None)
                }

                field_extraction_manifest = {
                    "value_type": val_type,
                    "value": validated_val,
                    "confidence": confidence,
                    "status": status,
                    "source": source_obj
                }

                if reason:
                    field_extraction_manifest["reason"] = reason

                # 4. Save the candidate-specific resolved contract fields
                field_def["field_extraction_manifest"] = field_extraction_manifest
                filled_fields_list.append(field_def)

                # 5. Populate final_fill_result in strict schema format for document generator compatibility
                mapping_category = "simple scalar replacement"
                if ftype in ("array_complex", "table_loop"):
                    mapping_category = "complex smart object"
                elif ftype == "array_simple":
                    mapping_category = "array"

                final_fill_result[fieldname] = {
                    "value": validated_val,
                    "marker_text": marker,
                    "field_type": ftype,
                    "mapping_category": mapping_category,
                    "source": source_sec if source_sec else "extracted",
                    "confidence": confidence,
                    "status": status,
                    "note": evidence if evidence else f"Resolved field {fieldname}",
                    "field_extraction_manifest": field_extraction_manifest
                }

        # 6. Cleanup remaining pool elements (Move them to additional facts)
        if pool:
            if "additional_resume_facts_available" not in ai_output:
                ai_output["additional_resume_facts_available"] = {}
            ai_output["additional_resume_facts_available"].update(pool)
            
            # Remove keys from root if they were moved
            for pk in pool.keys():
                ai_output.pop(pk, None)

        # 7. Assemble the final candidate-specific filled_template_manifest contract!
        filled_template_manifest = {
            "fields": filled_fields_list
        }

        ai_output["template_fill_result"] = final_fill_result
        ai_output["missing_fields_requiring_recruiter_or_ats_input"] = list(set(missing_fields))
        ai_output["filled_template_manifest"] = filled_template_manifest

        if field_manifest:
            ai_output["template_fill_result"]["_manifest"] = field_manifest

        # Print detailed logger report at the end
        logger.info("\n" + "=" * 80)
        logger.info("[ManifestCompliance] COMPLIANCE REPORT SUMMARY:")
        logger.info(f"  - Total Manifest Fields: {len(filled_fields_list)}")
        logger.info(f"  - Successfully Extracted: {sum(1 for f in filled_fields_list if f['field_extraction_manifest']['status'] == 'extracted')}")
        logger.info(f"  - Inferred / Generated: {sum(1 for f in filled_fields_list if f['field_extraction_manifest']['status'] in ['inferred', 'generated_from_resume'])}")
        logger.info(f"  - Missing / Not Found: {sum(1 for f in filled_fields_list if f['field_extraction_manifest']['status'] in ['not_found', 'needs_user_input'])}")
        logger.info("=" * 80 + "\n")

        return ai_output

    async def apply_composition_logic(
        self,
        harmonized_data: Dict[str, Any],
        template_text: str,
        manifest: List[Dict[str, Any]] = None,
        formatting_guidance: str = "",
    ) -> Dict[str, Any]:
        """Performs a secondary formatting and professional phrasing pass."""

        prompt = prompt_manager.get_prompt(
            "composition_logic.jinja2",
            harmonized_json=json.dumps(harmonized_data, indent=2),
            manifest_json=json.dumps(manifest, indent=2) if manifest else "None",
            formatting_guidance=formatting_guidance,
            template_text=template_text[:3000],
        )

        logger.info("\n" + "=" * 60 + "\n--- COMPOSITION LOGIC PROMPT ---\n" + "=" * 60)
        logger.info(prompt)
        logger.info("=" * 60 + "\n")

        response = self.llm.generate(prompt)

        logger.info(
            "\n" + "=" * 60 + "\n--- COMPOSITION LOGIC LLM RESPONSE ---\n" + "=" * 60
        )
        logger.info(response)
        logger.info("=" * 60 + "\n")

        try:
            cleaned_json = LlmSanitizer.clean_json(response)
            data = json.loads(cleaned_json)

            logger.info(
                "\n" + "=" * 60 + "\n--- FINAL COMPOSITION DATA ---\n" + "=" * 60
            )
            logger.info(data)
            logger.info("=" * 60 + "\n")
        except Exception as e:
            logger.error(f"Failed to parse composition logic JSON: {e}")
            data = harmonized_data

        if manifest:
            try:
                logger.info("[CompositionLogic] Enforcing programmatic manifest compliance and schema shape post-composition...")
                data = self._enforce_manifest_compliance(data, manifest)
            except Exception as ce:
                logger.error(f"Failed to enforce manifest compliance after composition logic: {ce}")

        return data

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
