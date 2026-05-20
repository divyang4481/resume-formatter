import zipfile
import io
import lxml.etree as ET
import re
from typing import Dict, Any, List

class TemplateEvidenceExtractor:
    def __init__(self, docling_adapter=None):
        self.docling_adapter = docling_adapter

    async def extract(
        self,
        content: bytes,
        filename: str,
        template_context: dict,
    ) -> dict:
        """
        Extracts evidence package combining deterministic structure extraction,
        Docling text flow, placeholder inventory, and structural summary.
        """
        docx_structure_view = self._extract_docx_structure(content)
        placeholder_view = self._build_placeholder_view(docx_structure_view)

        docling_view = {"document_text_flow": []}
        if self.docling_adapter:
            docling_view = await self.docling_adapter.extract_text_flow(content, filename)

        # Discover repeated placeholder sequences by combining structure and text (simplistic heuristic here)
        placeholder_view["repeated_placeholder_sequences"] = self._detect_repeated_sequences(
            content, docx_structure_view, placeholder_view["all_placeholders"]
        )

        # Child placeholders
        placeholder_view["child_placeholders_not_top_level"] = self._detect_child_placeholders(
            docx_structure_view, placeholder_view["repeated_placeholder_sequences"]
        )

        return {
            "template_context": template_context,
            "docling_view": docling_view,
            "docx_structure_view": docx_structure_view,
            "placeholder_view": placeholder_view,
            "semantic_discovery_rules": template_context.get("semantic_discovery_rules", {})
        }

    def _extract_docx_structure(self, content: bytes) -> Dict[str, Any]:
        W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        ns = {"w": W_NS}
        W = f"{{{W_NS}}}"

        detected_markers = []
        table_loops = []
        instruction_blocks = []
        paste_zones = []
        heading_blocks = []
        bullet_sections = []

        PASTE_ZONE_KEYWORDS = ["own cv", "paste", "insert cv", "candidate cv", "candidate's cv"]
        INSTRUCTION_COLOR_RED = {"ff0000", "c00000", "dc143c"}

        XML_PARTS_TO_SCAN = [
            "word/document.xml", "word/header1.xml", "word/header2.xml",
            "word/header3.xml", "word/footer1.xml", "word/footer2.xml", "word/footer3.xml"
        ]

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                available_parts = set(z.namelist())

                for part_name in XML_PARTS_TO_SCAN:
                    if part_name not in available_parts:
                        continue

                    xml_content = z.read(part_name)
                    root = ET.fromstring(xml_content)

                    # 1. Markers (MERGEFIELD simple)
                    for fld in root.xpath("//w:fldSimple", namespaces=ns):
                        instr = fld.get(f"{W}instr")
                        if instr and "MERGEFIELD" in instr:
                            parts = instr.split()
                            if len(parts) >= 2:
                                detected_markers.append(parts[parts.index("MERGEFIELD") + 1])

                    # 2. Markers (MERGEFIELD complex)
                    for instr_text in root.xpath("//w:instrText", namespaces=ns):
                        text = instr_text.text
                        if text and "MERGEFIELD" in text:
                            parts = text.split()
                            if len(parts) >= 2:
                                detected_markers.append(parts[parts.index("MERGEFIELD") + 1])

                    # 3. Guillemet and Bracketed placeholders
                    for para in root.xpath("//w:p", namespaces=ns):
                        run_texts = [t.text or "" for t in para.xpath(".//w:t", namespaces=ns)]
                        para_text = "".join(run_texts)

                        # Guillemet
                        for m in re.finditer(r"«\s*(.*?)\s*»", para_text):
                            detected_markers.append(f"«{m.group(1).strip()}»")

                        # Bracketed
                        for m in re.finditer(r"\[\s*([^\]\s][^\]]*?)\s*\]", para_text):
                            inner = m.group(1).strip()
                            if inner and len(inner) < 80:
                                detected_markers.append(f"[{inner}]")

                        # Quoted Bracketed (e.g., "[Job description, Date]")
                        for m in re.finditer(r'"\[\s*([^\]\s][^\]]*?)\s*\]"', para_text):
                            inner = m.group(1).strip()
                            if inner and len(inner) < 80:
                                detected_markers.append(f'"[{inner}]"')

                    # 4. Table Loops
                    loop_names: Dict[str, list] = {}
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
                                    pass
                                else:
                                    for ln in loop_names:
                                        if name not in loop_names[ln]:
                                            loop_names[ln].append(name)

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

                    for k, v in loop_names.items():
                        table_loops.append({"loop_name": k, "item_fields": v})

                    # Guillemet table loops
                    raw_xml = xml_content.decode("utf-8", errors="ignore")
                    g_loops = {}
                    current_loop = None
                    # Very naive pass to find TableStart/TableEnd sequences
                    for m in re.finditer(r"«(TableStart:([^»]+))»", raw_xml):
                        loop_name = m.group(2)
                        g_loops[loop_name] = []

                    # This requires more complex parsing for guillemets if needed...
                    for ln in g_loops.keys():
                        table_loops.append({"loop_name": ln, "item_fields": []}) # We might populate item_fields later if needed

                    # 5. Instructions and Paste Zones
                    for para in root.xpath("//w:p", namespaces=ns):
                        run_texts = [t.text or "" for t in para.xpath(".//w:t", namespaces=ns)]
                        para_text = "".join(run_texts).strip()
                        if not para_text:
                            continue

                        # Headings
                        style_el = para.xpath(".//w:pStyle", namespaces=ns)
                        is_heading = any((s.get(f"{W}val") or "").lower().startswith("heading") for s in style_el)
                        bold_els = para.xpath(".//w:b", namespaces=ns)

                        if is_heading or bold_els:
                            heading_blocks.append(para_text)

                        if (is_heading or bold_els) and any(kw in para_text.lower() for kw in PASTE_ZONE_KEYWORDS):
                            if para_text not in paste_zones:
                                paste_zones.append(para_text)

                        # Instructions
                        is_instruction = False
                        if len(para_text) >= 10:
                            for color_el in para.xpath(".//w:color", namespaces=ns):
                                color_val = (color_el.get(f"{W}val") or "").lower()
                                if color_val in INSTRUCTION_COLOR_RED or (color_val not in ("auto", "000000", "") and color_val != "auto"):
                                    is_instruction = True
                                    break

                            italic_runs = para.xpath(".//w:i", namespaces=ns)
                            total_runs = para.xpath(".//w:r", namespaces=ns)
                            if italic_runs and not is_instruction and total_runs and len(italic_runs) >= len(total_runs):
                                is_instruction = True

                            if not is_instruction and para_text.startswith('"') and para_text.endswith('"') and len(para_text) > 20:
                                is_instruction = True

                        if is_instruction and para_text not in instruction_blocks:
                            instruction_blocks.append(para_text)

                        # 6. Bullet sections
                        ilvl_el = para.xpath(".//w:ilvl", namespaces=ns)
                        numId_el = para.xpath(".//w:numId", namespaces=ns)
                        if (ilvl_el or numId_el) and len(para_text) < 5 and para_text.strip() == "·":
                           # Extremely naive bullet section detection for placeholders
                           # Usually we'd track headings and collect bullets under them
                           pass

                # Collect bullet sections more globally by analyzing document flow
                xml_content = z.read("word/document.xml")
                root = ET.fromstring(xml_content)
                current_heading = None
                bullet_count = 0
                for para in root.xpath("//w:p", namespaces=ns):
                    run_texts = [t.text or "" for t in para.xpath(".//w:t", namespaces=ns)]
                    para_text = "".join(run_texts).strip()

                    style_el = para.xpath(".//w:pStyle", namespaces=ns)
                    is_heading = any((s.get(f"{W}val") or "").lower().startswith("heading") for s in style_el)
                    bold_els = para.xpath(".//w:b", namespaces=ns)

                    if (is_heading or bold_els) and para_text:
                        if current_heading and bullet_count > 0:
                            bullet_sections.append({
                                "heading": current_heading,
                                "sample_bullet_count": bullet_count
                            })
                        current_heading = para_text
                        bullet_count = 0
                    else:
                        num_props = para.xpath(".//w:numPr", namespaces=ns)
                        # Identify bullet points: either actual text is a bullet character, or it has numbering props
                        if para_text == "·" or num_props:
                            bullet_count += 1

                if current_heading and bullet_count > 0:
                    bullet_sections.append({
                        "heading": current_heading,
                        "sample_bullet_count": bullet_count
                    })

        except Exception as e:
            pass # Handle gracefully in a real impl

        # Deduplicate markers
        unique_markers = []
        seen = set()
        for m in detected_markers:
            m = m.strip()
            if m and m not in seen:
                seen.add(m)
                unique_markers.append(m)

        return {
            "detected_markers": unique_markers,
            "label_value_pairs": [], # Requires more complex extraction
            "heading_blocks": heading_blocks,
            "table_loops": table_loops,
            "bullet_sections": bullet_sections,
            "repeat_blocks": [], # Filled via sequence detection
            "paste_zones": paste_zones,
            "instruction_blocks": instruction_blocks
        }

    def _build_placeholder_view(self, docx_structure: dict) -> dict:
        all_placeholders = docx_structure.get("detected_markers", [])
        return {
            "all_placeholders": all_placeholders,
            "placeholder_occurrences": [], # Can be fleshed out
            "repeated_placeholder_sequences": [],
            "child_placeholders_not_top_level": []
        }

    def _detect_repeated_sequences(self, content: bytes, docx_structure: dict, placeholders: list) -> list:
        """
        Dynamically detects blocks of repeated placeholders under headings.
        Groups them by evaluating structural XML.
        """
        sequences = []
        W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        ns = {"w": W_NS}
        W = f"{{{W_NS}}}"

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                if "word/document.xml" not in z.namelist():
                    return sequences

                xml_content = z.read("word/document.xml")
                root = ET.fromstring(xml_content)

                current_heading = None
                current_sequence = []
                heading_sequences = {}

                for para in root.xpath("//w:p", namespaces=ns):
                    run_texts = [t.text or "" for t in para.xpath(".//w:t", namespaces=ns)]
                    para_text = "".join(run_texts).strip()

                    style_el = para.xpath(".//w:pStyle", namespaces=ns)
                    is_heading = any((s.get(f"{W}val") or "").lower().startswith("heading") for s in style_el)
                    bold_els = para.xpath(".//w:b", namespaces=ns)

                    if (is_heading or bold_els) and para_text:
                        if current_heading and len(current_sequence) > 1:
                            # Save the previous sequence before moving to new heading
                            seq_tuple = tuple(current_sequence)
                            if current_heading not in heading_sequences:
                                heading_sequences[current_heading] = {}
                            heading_sequences[current_heading][seq_tuple] = heading_sequences[current_heading].get(seq_tuple, 0) + 1

                        current_heading = para_text
                        current_sequence = []
                    else:
                        # Detect placeholders in the paragraph
                        for m in re.finditer(r"\[\s*([^\]\s][^\]]*?)\s*\]", para_text):
                            current_sequence.append(f"[{m.group(1).strip()}]")
                        for m in re.finditer(r'"\[\s*([^\]\s][^\]]*?)\s*\]"', para_text):
                            current_sequence.append(f'"[{m.group(1).strip()}]"')
                        for m in re.finditer(r"«\s*(.*?)\s*»", para_text):
                            current_sequence.append(f"«{m.group(1).strip()}»")

                # Handle the final sequence
                if current_heading and len(current_sequence) > 1:
                    seq_tuple = tuple(current_sequence)
                    if current_heading not in heading_sequences:
                        heading_sequences[current_heading] = {}
                    heading_sequences[current_heading][seq_tuple] = heading_sequences[current_heading].get(seq_tuple, 0) + 1

                for heading, seq_counts in heading_sequences.items():
                    for seq, count in seq_counts.items():
                        if count >= 1 and len(seq) > 1: # Consider any grouped block
                            sequences.append({
                                "heading": heading,
                                "ordered_placeholders": list(seq),
                                "sample_occurrence_count": count,
                                "has_bullets": True # Simplification, could detect w:numPr here
                            })

        except Exception as e:
            pass

        return sequences

    def _detect_child_placeholders(self, docx_structure: dict, repeated_sequences: list) -> list:
        child_placeholders = []
        # Add table loop items
        for tl in docx_structure.get("table_loops", []):
            child_placeholders.extend(tl.get("item_fields", []))

        # Add repeat block items
        for rs in repeated_sequences:
            child_placeholders.extend(rs.get("ordered_placeholders", []))

        return list(set(child_placeholders))
