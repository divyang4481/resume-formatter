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
        summary = self.llm.generate(prompt)
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

    async def analyze_template(self, content: bytes, filename: str) -> Dict[str, str]:
        """Analyzes a .docx template to suggest metadata... (Uses Context Injection)"""
        if not self.extraction_service:
            return {}

        extracted_doc = await self.extraction_service.extract(
            content,
            filename,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        text_content = extracted_doc.extracted_text

        # 1. Gather all placeholders
        xml_placeholders = []
        if filename.lower().endswith(".docx"):
            xml_placeholders = self._get_docx_placeholders_from_xml(content)
            logger.info(f"Deep XML Scan found: {xml_placeholders}")

        regex_patterns = [
            r"<<\s*.*?\s*>>",
            r"\{\{\s*.*?\s*\}\}",
            r"\[\[\s*.*?\s*\]\]",
            r"«\s*.*?\s*»",
            r"\[\s*[^\]\s].*?\s*\]",
        ]

        detected_raw = []
        for pattern in regex_patterns:
            matches = re.findall(pattern, text_content)
            detected_raw.extend(matches)
        
        # XML scan results should already have markers if we fix the helper
        detected_raw.extend(xml_placeholders)

        seen = set()
        detected_placeholders = [
            p.strip()
            for p in detected_raw
            if p.strip() and not (p.strip() in seen or seen.add(p.strip()))
        ]

        # 2. CONTEXT INJECTION: inject hidden markers not found in extracted text
        missing_from_text = [
            p
            for p in xml_placeholders
            if p not in text_content and p.strip("«»") not in text_content
        ]
        if missing_from_text:
            injection_header = (
                "\n[SYSTEM: HIDDEN METADATA MARKERS DETECTED IN DOCUMENT XML]\n"
            )
            for p in missing_from_text:
                inner = p.strip("«»[]")
                injection_header += f"Marker: «{inner}» → must be assigned to logical field '{inner}'\n"
            injection_header += "[END HIDDEN METADATA]\n\n"
            text_content = injection_header + text_content

        # 2b. Structural hints: layout style, instruction blocks, paste zones, table loops
        if filename.lower().endswith(".docx"):
            struct_hints = self._detect_structural_hints(content)
            logger.info(f"Structural hints detected: {struct_hints}")

            struct_block = "\n[STRUCTURAL HINTS FROM DOCX ANALYSIS]\n"
            struct_block += f"Layout Style: {struct_hints.get('layout_style', 'unknown')}\n"

            loops = struct_hints.get("table_loops", [])
            if loops:
                struct_block += "Table Loops Detected (field_type=table_loop):\n"
                for loop in loops:
                    struct_block += f"  - Loop: '{loop['loop_name']}' with item fields: {loop['item_fields']}\n"

            paste_zones = struct_hints.get("paste_zone_headings", [])
            if paste_zones:
                struct_block += "Paste Zone Headings Detected (field_type=paste_zone):\n"
                for pz in paste_zones:
                    struct_block += f"  - '{pz}'\n"

            instructions = struct_hints.get("instruction_paragraphs", [])
            if instructions:
                struct_block += "Instruction Block Paragraphs Detected (field_type=instruction_block):\n"
                for inst in instructions:
                    struct_block += f"  - '{inst}'\n"

            struct_block += "[END STRUCTURAL HINTS]\n"
            text_content = struct_block + text_content

        # 2b. Append structured table label→value context so AI can map labels to markers
        table_context = self._build_table_label_context(extracted_doc)
        if table_context:
            text_content += table_context

        # 2c. Legacy structured table rows (kept for backward compat)
        if extracted_doc.structured_data and "items" in extracted_doc.structured_data:
            tables = [item for item in extracted_doc.structured_data["items"] if item.get("role") == "table"]
            if tables:
                text_content += "\n\n[STRUCTURED TABLE DATA]\n"
                for table in tables:
                    if "cells" in table:
                        rows: Dict[int, Dict[int, str]] = {}
                        for cell in table["cells"]:
                            r, c = cell.get("row_index", 0), cell.get("column_index", 0)
                            txt = cell.get("text", "").strip()
                            rows.setdefault(r, {})[c] = txt
                        for r_idx in sorted(rows.keys()):
                            row_vals = [rows[r_idx].get(c_idx, "") for c_idx in sorted(rows[r_idx].keys())]
                            text_content += "| " + " | ".join(row_vals) + " |\n"
                text_content += "[END TABLE DATA]\n"

        # 3. LLM Analysis - Single "Smart" Text Source
        prompt = prompt_manager.get_prompt(
            "template_analysis.jinja2",
            template_text=text_content[:12000],
            detected_placeholders=detected_placeholders,
        )

        logger.info("\n" + "="*60 + "\n--- TEMPLATE ANALYSIS PROMPT ---\n" + "="*60)
        logger.info(prompt)
        logger.info("="*60 + "\n")

        response = self.llm.generate(prompt)

        logger.info("\n" + "="*60 + "\n--- TEMPLATE ANALYSIS LLM RESPONSE ---\n" + "="*60)
        logger.info(response)
        logger.info("="*60 + "\n")

        try:
            cleaned_json = LlmSanitizer.clean_json(response)
            data = json.loads(cleaned_json)
        except Exception as e:
            logger.error(f"Failed to parse template analysis JSON: {e}")
            data = {}

        manifest = data.get("field_extraction_manifest", [])
        if not isinstance(manifest, list):
            manifest = []

        # ---------------------------------------------------------------
        # AI HEALING PASS: Fill in empty marker_text fields.
        # Strategy: for each manifest entry that has no marker_text, try to
        # find a detected placeholder whose inner name fuzzy-matches the
        # fieldname or source_hints label.
        # ---------------------------------------------------------------
        def _fuzzy_match_placeholder(fieldname: str, source_hints: str, candidates: List[str]) -> str:
            """Return the best matching placeholder from candidates, or empty string."""
            # Build a set of keywords from fieldname and source_hints
            keywords = set(re.sub(r"[^a-z0-9]", " ", fieldname.lower()).split())
            label_words = set(re.sub(r"[^a-z0-9]", " ", (source_hints or "").lower()).split())
            keywords |= label_words
            # Strip common stop-words
            keywords -= {"in", "the", "of", "to", "a", "an", "is", "and", "or", "for", "at", "by", "located", "next", "label", "table", "under", "header", "section", "candidate", "profile"}

            best_match = ""
            best_score = 0
            for cand in candidates:
                inner = re.sub(r"[^a-z0-9]", " ", cand.strip("«»[]").lower())
                cand_words = set(inner.split())
                score = len(keywords & cand_words)
                if score > best_score:
                    best_score = score
                    best_match = cand
            return best_match if best_score > 0 else ""

        for entry in manifest:
            if not entry.get("marker_text"):
                fieldname = entry.get("fieldname", "")
                source_hints = entry.get("source_hints", "")
                healed = _fuzzy_match_placeholder(fieldname, source_hints, detected_placeholders)
                if healed:
                    entry["marker_text"] = healed
                    logger.info(f"HEALED (fuzzy): '{fieldname}' → '{healed}'")

        # 4. Final Reconciliation & Hallucination Guard
        manifest_markers = [str(m.get("marker_text", "")) for m in manifest if m.get("marker_text")]
        
        # --- HALLUCINATION GUARD: Check for repetitive markers ---
        if len(manifest_markers) > 3:
            from collections import Counter
            counts = Counter(manifest_markers)
            most_common, count = counts.most_common(1)[0]
            if count / len(manifest_markers) > 0.6:
                logger.error(f"HALLUCINATION DETECTED: Marker '{most_common}' repeated {count} times. Rejecting manifest.")
                # Force a partial cleanup: remove the hallucinated markers from fields that clearly don't match
                for m in manifest:
                    if m.get("marker_text") == most_common and most_common.lower().strip("«»") not in m.get("fieldname", "").lower():
                        if "email" not in m.get("fieldname", "").lower():
                            m["marker_text"] = "" 
                            logger.info(f"Cleaned hallucinated marker from {m.get('fieldname')}")

        for p in detected_placeholders:
            found = False
            for m in manifest_markers:
                if p in m:
                    found = True
                    break

            if not found:
                logger.warning(f"AI STILL missed placeholder '{p}'. Using fallback.")
                clean_name = re.sub(r"[^a-z0-9]", "_", p.lower()).strip("_")
                if not clean_name:
                    clean_name = f"field_{p}"
                manifest.insert(
                    0,
                    {
                        "fieldname": clean_name,
                        "marker_text": f"«{p}»",
                        "visual_context": "Automatically identified at document level",
                        "meaning": f"Metadata placeholder for {p}",
                        "source_hints": clean_name.replace("_", " "),
                    },
                )

        fields = [m.get("fieldname") for m in manifest if m.get("fieldname")]
        expected_fields = ", ".join(fields)

        return {
            "purpose": data.get("purpose") or "General Template",
            "expected_sections": data.get("expected_sections") or "Summary, Experience",
            "expected_fields": expected_fields,
            "summary_guidance": data.get("summary_guidance", ""),
            "formatting_guidance": data.get("formatting_guidance", ""),
            "validation_guidance": data.get("validation_guidance", ""),
            "field_extraction_manifest": manifest,
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
