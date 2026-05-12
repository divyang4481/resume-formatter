"""
TemplateStructureExtractor
--------------------------
Deterministic DOCX XML scanner that produces a TemplateStructure object.

Design principle: ALL structural facts about the template come from here.
The LLM is only used for semantic interpretation AFTER this runs.
"""
import io
import logging
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import lxml.etree as ET

logger = logging.getLogger(__name__)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"
NS = {"w": W_NS}

# ---------------------------------------------------------------------------
# Known alias map: fieldname → list of expected marker CamelCase names
# Used in reconciliation to map LLM-produced fieldnames → detected markers
# ---------------------------------------------------------------------------
FIELD_ALIAS_MAP: Dict[str, List[str]] = {
    "candidate_name": ["CandidateFullName", "FullName", "CandidateName"],
    "candidate_id": ["CandidateID", "CandidateId"],
    "notice_period": ["NoticePeriod"],
    "salary_required": ["ExpectedSalary", "SalaryRequired", "ExpectedSalaryAmount"],
    "living_in": ["CandidateTown", "CandidateLocation", "Town"],
    "expert_opinion": ["CVcomments", "ExpertOpinion", "CVComments", "Cvcomments"],
    "employee_name": ["EmployeeName"],
    "employee_job_title": ["EmployeeJobTitle"],
    "employee_email": ["EmployeeEmail"],
    "employee_tel_no": ["EmployeeTelNo", "EmployeeTelNumber"],
    "employee_specialist_area": ["EmployeeSpecialistArea"],
    "candidate_name_full": ["CandidateFullName"],
    "cv_comments": ["CVcomments", "CVComments"],
    "position_required": ["PositionRequired"],
    "current_salary_benefits": ["CurrentSalary", "Salary", "CurrentSalaryBenefits"],
}

# Inverted alias map: CamelCase marker → canonical fieldname
_ALIAS_INVERTED: Dict[str, str] = {}
for _fn, _aliases in FIELD_ALIAS_MAP.items():
    for _alias in _aliases:
        _ALIAS_INVERTED[_alias.lower()] = _fn

PASTE_ZONE_KEYWORDS = ["own cv", "paste", "insert cv", "candidate cv", "candidate's cv"]
INSTRUCTION_COLORS_RED = {"ff0000", "c00000", "dc143c", "b22222"}
TABLE_LOOP_PREFIX = "TableStart:"
TABLE_LOOP_SUFFIX = "TableEnd:"

# XML parts to scan (document body + all headers/footers)
XML_PARTS = [
    "word/document.xml",
    "word/header1.xml", "word/header2.xml", "word/header3.xml",
    "word/footer1.xml", "word/footer2.xml", "word/footer3.xml",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TableLoop:
    loop_name: str
    item_fields: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"loop_name": self.loop_name, "item_fields": self.item_fields}


@dataclass
class TableLabelSlot:
    """A table row where a bold/label cell is followed by a blank or marker cell."""
    label: str
    marker: str = ""        # If marker found in value cell
    is_blank: bool = False  # True when value cell has no useful content

    def to_dict(self) -> Dict[str, Any]:
        return {"label": self.label, "marker": self.marker, "is_blank": self.is_blank}


@dataclass
class TemplateStructure:
    detected_markers: List[str] = field(default_factory=list)
    """Canonical form of all found markers: «Name», [Name], <<Name>>"""

    marker_normalized_map: Dict[str, str] = field(default_factory=dict)
    """marker → normalized lowercase name, for fuzzy matching"""

    table_label_value_pairs: List[TableLabelSlot] = field(default_factory=list)
    """Table rows: (label, marker or blank)"""

    blank_label_slots: List[str] = field(default_factory=list)
    """Labels whose adjacent cell is blank (no marker)"""

    bullet_slots: List[str] = field(default_factory=list)
    """Section headings that have bullet-list placeholder slots below them"""

    table_loops: List[TableLoop] = field(default_factory=list)
    """Word mail-merge table loops (TableStart/TableEnd)"""

    paste_zones: List[str] = field(default_factory=list)
    """Headings or sections identified as paste/CV body zones"""

    instruction_blocks: List[str] = field(default_factory=list)
    """Paragraphs identified as human instructions (red/italic/quoted)"""

    headers_footers_markers: List[str] = field(default_factory=list)
    """Markers found specifically in header/footer XML parts"""

    layout_style: str = "freeflow"
    """table_based | freeflow | mixed"""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected_markers": self.detected_markers,
            "marker_normalized_map": self.marker_normalized_map,
            "table_label_value_pairs": [s.to_dict() for s in self.table_label_value_pairs],
            "blank_label_slots": self.blank_label_slots,
            "bullet_slots": self.bullet_slots,
            "table_loops": [l.to_dict() for l in self.table_loops],
            "paste_zones": self.paste_zones,
            "instruction_blocks": self.instruction_blocks,
            "headers_footers_markers": self.headers_footers_markers,
            "layout_style": self.layout_style,
        }


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def normalize_marker_name(marker: str) -> str:
    """
    Converts a raw marker string to a lowercase-space-separated name for fuzzy matching.

    Examples:
        «CandidateFullName» → "candidate full name"
        [Type text]         → "type text"
        EmployeeEmail       → "employee email"
    """
    # Strip enclosing brackets
    inner = marker.strip()
    for pair in [("«", "»"), ("[", "]"), ("<<", ">>"), ("{{", "}}"), ("[[", "]]")]:
        if inner.startswith(pair[0]) and inner.endswith(pair[1]):
            inner = inner[len(pair[0]):-len(pair[1])].strip()
            break

    # Split CamelCase: CandidateFullName → Candidate Full Name
    inner = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", inner)
    inner = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", inner)

    # Replace non-alphanumeric with space, lowercase, collapse whitespace
    inner = re.sub(r"[^a-z0-9]+", " ", inner.lower()).strip()
    return inner


def canonical_marker(raw: str) -> str:
    """
    Returns a canonical guillemet-wrapped marker.
    If already wrapped (guillemets, brackets), returns as-is.
    Prevents double-wrapping bugs like ««Name»».
    """
    s = raw.strip()
    if (s.startswith("«") and s.endswith("»")) or \
       (s.startswith("[") and s.endswith("]")) or \
       (s.startswith("<<") and s.endswith(">>")):
        return s
    return f"«{s}»"


def _para_text(para: ET._Element) -> str:
    """Reconstruct full paragraph text from all <w:t> children."""
    return "".join(t.text or "" for t in para.xpath(".//w:t", namespaces=NS))


def _is_bold(para: ET._Element) -> bool:
    """True if any run in the paragraph is bold."""
    return bool(para.xpath(".//w:b", namespaces=NS))


def _is_red_or_colored(para: ET._Element) -> bool:
    """True if any run has a non-black, non-auto color (indicates instruction text)."""
    for color_el in para.xpath(".//w:color", namespaces=NS):
        val = (color_el.get(f"{W}val") or "").lower().strip()
        if val in INSTRUCTION_COLORS_RED or (val not in ("auto", "000000", "") and len(val) == 6):
            return True
    return False


def _is_all_italic(para: ET._Element) -> bool:
    runs = para.xpath(".//w:r", namespaces=NS)
    italic_runs = para.xpath(".//w:i", namespaces=NS)
    return bool(runs) and len(italic_runs) >= len(runs)


def _extract_mergefield_name(instr: str) -> Optional[str]:
    """Pull the field name from a MERGEFIELD instruction string."""
    parts = instr.split()
    try:
        idx = parts.index("MERGEFIELD")
        return parts[idx + 1].strip("\\*MERGEFORMAT").strip()
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# Main extractor
# ---------------------------------------------------------------------------

class TemplateStructureExtractor:
    """
    Deterministic DOCX XML structure extractor.
    Call extract() once per template — this is the ground truth used by the LLM prompt
    and the reconciliation pass.
    """

    def extract(self, content: bytes, filename: str) -> TemplateStructure:
        struct = TemplateStructure()

        if not filename.lower().endswith(".docx"):
            logger.info(f"TemplateStructureExtractor: skipping non-DOCX file '{filename}'")
            return struct

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                available = set(z.namelist())
                raw_markers: List[str] = []
                loop_tracker: Dict[str, TableLoop] = {}

                for part_name in XML_PARTS:
                    if part_name not in available:
                        continue
                    is_header_footer = part_name != "word/document.xml"
                    xml_bytes = z.read(part_name)
                    part_markers = self._scan_xml_part(
                        xml_bytes, part_name, struct, loop_tracker, is_header_footer
                    )
                    raw_markers.extend(part_markers)

                struct.table_loops = list(loop_tracker.values())

                # Deduplicate markers preserving order
                seen: set = set()
                for m in raw_markers:
                    m = m.strip()
                    if m and m not in seen:
                        seen.add(m)
                        struct.detected_markers.append(m)
                        struct.marker_normalized_map[m] = normalize_marker_name(m)

            logger.info(
                f"TemplateStructureExtractor: '{filename}' → "
                f"{len(struct.detected_markers)} markers, "
                f"{len(struct.table_label_value_pairs)} table pairs, "
                f"{len(struct.table_loops)} loops, "
                f"layout={struct.layout_style}"
            )

        except Exception as e:
            logger.error(f"TemplateStructureExtractor: error scanning '{filename}': {e}")

        return struct

    # ------------------------------------------------------------------
    # XML part scanner
    # ------------------------------------------------------------------

    def _scan_xml_part(
        self,
        xml_bytes: bytes,
        part_name: str,
        struct: TemplateStructure,
        loop_tracker: Dict[str, "TableLoop"],
        is_header_footer: bool,
    ) -> List[str]:
        """Scans one XML part and populates struct in-place. Returns raw markers found."""
        part_markers: List[str] = []
        try:
            root = ET.fromstring(xml_bytes)
        except Exception as e:
            logger.warning(f"TemplateStructureExtractor: could not parse {part_name}: {e}")
            return part_markers

        # ---- 1. Layout style (document.xml only) ----
        if part_name == "word/document.xml":
            table_count = len(root.xpath("//w:tbl", namespaces=NS))
            para_count = len(root.xpath("//w:p", namespaces=NS))
            if table_count > 0:
                struct.layout_style = "table_based" if para_count <= table_count * 3 else "mixed"

        # ---- 2. MERGEFIELD simple fields (w:fldSimple) ----
        for fld in root.xpath("//w:fldSimple", namespaces=NS):
            instr = fld.get(f"{W}instr") or ""
            if "MERGEFIELD" in instr:
                name = _extract_mergefield_name(instr)
                if name:
                    self._register_mergefield(name, part_markers, struct, loop_tracker, is_header_footer)

        # ---- 3. MERGEFIELD complex fields (w:instrText) ----
        for instr_el in root.xpath("//w:instrText", namespaces=NS):
            text = instr_el.text or ""
            if "MERGEFIELD" in text:
                name = _extract_mergefield_name(text)
                if name:
                    self._register_mergefield(name, part_markers, struct, loop_tracker, is_header_footer)

        # ---- 4. Reconstruct paragraphs → find «...» and [...] markers ----
        current_heading: Optional[str] = None
        heading_has_bullets: bool = False

        for para in root.xpath("//w:p", namespaces=NS):
            para_text_raw = _para_text(para)
            para_text = para_text_raw.strip()

            if not para_text:
                continue

            # Check for heading (by style or bold short line)
            style_els = para.xpath(".//w:pStyle", namespaces=NS)
            is_heading_style = any(
                (s.get(f"{W}val") or "").lower().startswith("heading")
                for s in style_els
            )
            is_bold_short = _is_bold(para) and len(para_text) < 60

            if is_heading_style or is_bold_short:
                # Save previous heading's bullet status
                if current_heading and heading_has_bullets:
                    struct.bullet_slots.append(current_heading)
                current_heading = para_text
                heading_has_bullets = False

                # Check for paste zone
                if any(kw in para_text.lower() for kw in PASTE_ZONE_KEYWORDS):
                    if para_text not in struct.paste_zones:
                        struct.paste_zones.append(para_text)
                continue

            # Detect guillemet markers by reconstructing para text
            found_guillemets = re.findall(r"«\s*(.*?)\s*»", para_text_raw)
            for g in found_guillemets:
                m = f"«{g.strip()}»"
                part_markers.append(m)
                if is_header_footer and m not in struct.headers_footers_markers:
                    struct.headers_footers_markers.append(m)

            # Detect bracket markers
            found_brackets = re.finditer(r"\[\s*([^\]\s][^\]]{1,79}?)\s*\]", para_text_raw)
            for bm in found_brackets:
                inner = bm.group(1).strip()
                if inner:
                    part_markers.append(f"[{inner}]")
                    # Flag as bullet slot if under a heading
                    if current_heading:
                        heading_has_bullets = True

            # Detect instruction blocks (red/italic/quoted paragraphs)
            if _is_red_or_colored(para) or _is_all_italic(para):
                if para_text not in struct.instruction_blocks:
                    struct.instruction_blocks.append(para_text[:400])
            elif para_text.startswith('"') and para_text.endswith('"') and len(para_text) > 20:
                if para_text not in struct.instruction_blocks:
                    struct.instruction_blocks.append(para_text[:400])

        # Save last heading's bullet status
        if current_heading and heading_has_bullets:
            struct.bullet_slots.append(current_heading)

        # ---- 5. Table label → value pair extraction (document.xml only) ----
        if part_name == "word/document.xml":
            self._extract_table_pairs(root, struct, part_markers)

        # ---- 6. Fallback: raw entity scan for encoded guillemets ----
        raw_xml = xml_bytes.decode("utf-8", errors="ignore")
        for pat, wrap_l, wrap_r in [
            (r"&#171;(.*?)&#187;", "«", "»"),
            (r"&laquo;(.*?)&raquo;", "«", "»"),
        ]:
            for m in re.finditer(pat, raw_xml):
                inner = m.group(1).strip()
                if inner:
                    part_markers.append(f"{wrap_l}{inner}{wrap_r}")

        return part_markers

    def _register_mergefield(
        self,
        name: str,
        part_markers: List[str],
        struct: TemplateStructure,
        loop_tracker: Dict[str, "TableLoop"],
        is_header_footer: bool,
    ):
        """Process a detected MERGEFIELD name — handle loops separately."""
        if name.startswith(TABLE_LOOP_PREFIX):
            loop_name = name[len(TABLE_LOOP_PREFIX):]
            if loop_name not in loop_tracker:
                loop_tracker[loop_name] = TableLoop(loop_name=loop_name)
        elif name.startswith(TABLE_LOOP_SUFFIX):
            pass  # End marker — already tracked by start
        else:
            marker = f"«{name}»"
            part_markers.append(marker)
            if is_header_footer and marker not in struct.headers_footers_markers:
                struct.headers_footers_markers.append(marker)
            # Associate body fields with most recent open loop
            for loop in loop_tracker.values():
                if name not in loop.item_fields:
                    loop.item_fields.append(name)

    def _extract_table_pairs(
        self,
        root: ET._Element,
        struct: TemplateStructure,
        part_markers: List[str],
    ):
        """
        Scan tables for label → marker/blank pairs.
        Hays templates use 2-column tables: col0=label (bold), col1=marker or blank.
        """
        for tbl in root.xpath("//w:tbl", namespaces=NS):
            for row in tbl.xpath(".//w:tr", namespaces=NS):
                cells = row.xpath(".//w:tc", namespaces=NS)
                if len(cells) < 2:
                    continue

                label_cell = cells[0]
                value_cell = cells[1]

                label_text = "".join(
                    t.text or "" for t in label_cell.xpath(".//w:t", namespaces=NS)
                ).strip()
                value_text = "".join(
                    t.text or "" for t in value_cell.xpath(".//w:t", namespaces=NS)
                ).strip()

                if not label_text or len(label_text) > 80:
                    continue

                # Look for a guillemet marker in the value cell
                guillemets = re.findall(r"«\s*(.*?)\s*»", value_text)
                marker_found = ""
                if guillemets:
                    marker_found = f"«{guillemets[0].strip()}»"
                    if marker_found not in part_markers:
                        part_markers.append(marker_found)

                is_blank = not value_text or value_text.lower() in {
                    "[type text]", "type text", "", "-", "n/a",
                    "[consultant comments]", '"[consultant comments]"',
                }

                slot = TableLabelSlot(
                    label=label_text,
                    marker=marker_found,
                    is_blank=is_blank and not marker_found,
                )
                struct.table_label_value_pairs.append(slot)

                if is_blank and not marker_found:
                    struct.blank_label_slots.append(label_text)
