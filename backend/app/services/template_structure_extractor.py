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
FIELD_ALIAS_MAP: Dict[str, Dict[str, Any]] = {
    "candidate_full_name": {"type": "scalar", "aliases": ["CandidateFullName", "FullName", "CandidateName", "Candidate_Full_Name", "Name", "Candidate name"]},
    "candidate_id": {"type": "scalar", "aliases": ["CandidateID", "CandidateId", "ID", "Candidate_ID"]},
    "notice_period": {"type": "scalar", "aliases": ["NoticePeriod", "Notice_Period", "Availability", "Notice_period"]},
    "expected_salary": {"type": "scalar", "aliases": ["ExpectedSalary", "SalaryRequired", "ExpectedSalaryAmount", "Salary_Required", "SalaryRequiredValue", "Salary required", "salary_required"]},
    "candidate_town": {"type": "scalar", "aliases": ["CandidateTown", "CandidateLocation", "Town", "Current_Location", "living_in", "Living in"]},
    "cv_comments": {"type": "rich_text", "aliases": ["CVcomments", "ExpertOpinion", "CVComments", "Cvcomments", "ConsultantComments", "Consultant_comments", "Expert_Opinion", "expert_opinion", "Our expert opinion"]},
    "employee_name": {"type": "scalar", "aliases": ["EmployeeName", "ConsultantName", "PresenterName", "HaysConsultant"]},
    "employee_job_title": {"type": "scalar", "aliases": ["EmployeeJobTitle", "ConsultantJobTitle", "JobTitle"]},
    "employee_email": {"type": "scalar", "aliases": ["EmployeeEmail", "ConsultantEmail", "Email"]},
    "employee_tel_no": {"type": "scalar", "aliases": ["EmployeeTelNo", "EmployeeTelNumber", "ConsultantTelNo", "Phone"]},
    "employee_specialist_area": {"type": "scalar", "aliases": ["EmployeeSpecialistArea", "SpecialistArea", "ConsultantSpecialism"]},
    "current_salary_benefits": {"type": "scalar", "aliases": ["CurrentSalary", "Salary", "CurrentSalaryBenefits", "Current_Salary"]},
    "work_experience": {"type": "rich_text", "aliases": ["WorkExperience", "EmploymentHistory", "Work_Experience", "Experience", "Employment_History"]},
    "education": {"type": "rich_text", "aliases": ["Education", "AcademicBackground", "Qualifications", "Academic_Background", "Professional qualifications"]},
    "professional_qualifications": {"type": "array_simple", "aliases": ["ProfessionalQualifications", "CheckType", "Certifications", "Professional qualifications"]},
    "skills": {"type": "array_simple", "aliases": ["Skills", "KeySkills", "CoreCompetencies", "Key_Skills", "Key skills"]},
    "interests_and_activities": {"type": "rich_text", "aliases": ["InterestsAndActivities", "Hobbies", "PersonalInterests", "Interests_and_Activities"]},
}

# Inverted alias map: CamelCase marker → canonical fieldname
_ALIAS_INVERTED: Dict[str, str] = {}
for _fn, _info in FIELD_ALIAS_MAP.items():
    for _alias in _info["aliases"]:
        _ALIAS_INVERTED[_alias.lower()] = _fn

PASTE_ZONE_KEYWORDS = [
    "own cv", "paste", "insert cv", "candidate cv", "candidate's cv",
    "work experience", "employment history", "professional experience",
    "education", "academic background", "key skills",
    "interests and activities", "hobbies", "personal interests"
]
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
    marker_text: str = ""   # If marker found in value cell
    is_blank: bool = False  # True when value cell has no useful content

    def to_dict(self) -> Dict[str, Any]:
        return {"label": self.label, "marker_text": self.marker_text, "is_blank": self.is_blank}


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

    all_headings: List[str] = field(default_factory=list)
    """All detected document headings/titles"""

    all_table_labels: List[str] = field(default_factory=list)
    """All detected table labels (bold first-column text)"""

    repeated_markers: List[str] = field(default_factory=list)
    """Markers found more than once in the document"""

    heading_to_placeholder: Dict[str, str] = field(default_factory=dict)
    """Mapping of heading text to its first non-empty paragraph content"""

    layout_style: str = "freeflow"
    """table_based | freeflow | mixed"""

    heading_to_loop: Dict[str, str] = field(default_factory=dict)
    """Maps a heading text to the name of the TableLoop that immediately follows it."""

    heading_to_smart_pattern: Dict[str, List[str]] = field(default_factory=dict)
    """Maps a heading to a sequence of multi-line placeholders that form an object template."""

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
            "all_headings": self.all_headings,
            "all_table_labels": self.all_table_labels,
            "repeated_markers": self.repeated_markers,
            "heading_to_placeholder": self.heading_to_placeholder,
            "layout_style": self.layout_style,
            "heading_to_loop": self.heading_to_loop,
            "heading_to_smart_pattern": self.heading_to_smart_pattern,
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
    # Strip enclosing brackets (longest pairs first)
    inner = marker.strip()
    for pair in [("«", "»"), ("[[", "]]"), ("{{", "}}"), ("<<", ">>"), ("[", "]")]:
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
    """Reconstruct full paragraph text, including Word symbols and fields."""
    parts = []
    # Iterate through all children to catch w:t and w:sym
    for el in para.xpath(".//*", namespaces=NS):
        if el.tag == f"{W}t":
            parts.append(el.text or "")
        elif el.tag == f"{W}sym":
            # Convert common guillemet symbols
            char = el.get(f"{W}char") or ""
            if char.upper() == "AB": parts.append("«")
            elif char.upper() == "BB": parts.append("»")
    
    return "".join(parts).strip()


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
        return parts[idx + 1].replace("\\*MERGEFORMAT", "").strip()
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

                # Final pass: Refine loops with structural containment (must happen after table_loops is populated)
                # We need the root of document.xml for this
                if "word/document.xml" in available:
                    doc_xml = ET.fromstring(z.read("word/document.xml"))
                    self._refine_table_loops(doc_xml, struct, raw_markers)

                # Deduplicate markers preserving order
                seen: set = set()
                all_raw_seen = []
                for m in raw_markers:
                    m = m.strip()
                    # Normalize guillemets to standard « and »
                    m = m.replace("\xab", "«").replace("\xbb", "»")
                    if m:
                        all_raw_seen.append(m)
                        if m not in seen:
                            seen.add(m)
                            struct.detected_markers.append(m)
                            struct.marker_normalized_map[m] = normalize_marker_name(m)

                # Identify repeated markers
                from collections import Counter
                counts = Counter(all_raw_seen)
                struct.repeated_markers = [m for m, count in counts.items() if count > 1]

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
            is_bold_short = _is_bold(para) and len(para_text) < 60 and not para_text.startswith("[")

            if is_heading_style or is_bold_short:
                # Save previous heading's bullet status
                if current_heading and heading_has_bullets:
                    struct.bullet_slots.append(current_heading)
                
                # Register all headings
                if para_text not in struct.all_headings:
                    struct.all_headings.append(para_text)
                    
                current_heading = para_text
                heading_has_bullets = False

                # Check for paste zone
                if any(kw in para_text.lower() for kw in PASTE_ZONE_KEYWORDS):
                    if para_text not in struct.paste_zones:
                        struct.paste_zones.append(para_text)
                continue

            # If we just saw a heading, the next non-empty paragraph might be its placeholder
            if current_heading and not para_text.startswith("["): # skip if already a bracket marker
                 if current_heading not in struct.heading_to_placeholder:
                     # Only take short-to-medium snippets as placeholders
                     if 5 < len(para_text) < 300:
                         struct.heading_to_placeholder[current_heading] = para_text
                         logger.info(f"Placeholder for '{current_heading}': {para_text[:50]}...")

            # Detect guillemet markers by reconstructing para text
            found_guillemets = re.findall(r"[\xab\u00ab]\s*(.*?)\s*[\xbb\u00bb]", para_text_raw)
            for g in found_guillemets:
                m = f"«{g.strip()}»"
                part_markers.append(m)
                
                # LINK HEADING TO LOOP: If this is a TableStart marker and we just saw a heading
                if m.startswith("«TableStart:") and current_heading:
                    loop_name = m.replace("«TableStart:", "").replace("»", "").strip()
                    struct.heading_to_loop[current_heading] = loop_name
                    logger.info(f"Linked heading '{current_heading}' to loop '{loop_name}'")

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
            # EXCLUDE common placeholders like [Organisation] or [Job description] or [Bullet point list]
            is_content_placeholder = bool(re.search(r"\[(Job description|Organisation|Bullet point|Date|Title|List|Grades)\]", para_text, re.I))
            
            if (_is_red_or_colored(para) or _is_all_italic(para)) and not is_content_placeholder:
                if para_text not in struct.instruction_blocks:
                    struct.instruction_blocks.append(para_text[:400])
            elif para_text.startswith('"') and para_text.endswith('"') and len(para_text) > 20 and not is_content_placeholder:
                if para_text not in struct.instruction_blocks:
                    struct.instruction_blocks.append(para_text[:400])

            # Detect object template patterns (multi-line placeholder sequences)
            # Handle quoted or bulleted placeholders like "[Job title]", "“Job title”", or • [Organisation]
            # Strip standard and smart quotes, bullets, and whitespace
            clean_para = para_text.strip(' "•\t“”‘’')
            
            if current_heading and clean_para:
                if clean_para.startswith("[") and clean_para.endswith("]"):
                    if current_heading not in struct.heading_to_smart_pattern:
                        struct.heading_to_smart_pattern[current_heading] = []
                    
                    # Capture ALL structural placeholders; the LLM will decide if they form an object
                    struct.heading_to_smart_pattern[current_heading].append(clean_para)
                    logger.info(f"Captured structural placeholder for '{current_heading}': {clean_para}")
                else:
                    # If we see non-placeholder text after a heading, it might break the pattern
                    # logger.debug(f"Non-placeholder text after '{current_heading}': {clean_para[:30]}")
                    pass

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
        loop_tracker: Dict[str, TableLoop],
        is_header_footer: bool,
    ):
        """Process a detected MERGEFIELD name."""
        if name.startswith(TABLE_LOOP_PREFIX):
            loop_name = name[len(TABLE_LOOP_PREFIX):]
            if loop_name not in loop_tracker:
                loop_tracker[loop_name] = TableLoop(loop_name=loop_name)
        elif name.startswith(TABLE_LOOP_SUFFIX):
            pass 
        else:
            marker = f"«{name}»"
            part_markers.append(marker)
            if is_header_footer and marker not in struct.headers_footers_markers:
                struct.headers_footers_markers.append(marker)

    def _refine_table_loops(self, root: ET._Element, struct: TemplateStructure, all_found_markers: List[str]):
        """
        Scan the paragraph flow to see which markers actually belong inside which loops.
        Uses aggressive alphanumeric normalization to bypass encoding issues.
        """
        def normalize(s: str) -> str:
            return "".join(re.findall(r"[A-Za-z0-9]+", s)).lower()

        raw_to_full = {}
        for m in all_found_markers:
            norm = normalize(m)
            if norm:
                raw_to_full[norm] = m

        all_paras = root.xpath("//w:p", namespaces=NS)
        
        for loop in struct.table_loops:
            start_tag_norm = normalize(f"TableStart:{loop.loop_name}")
            end_tag_norm = normalize(f"TableEnd:{loop.loop_name}")
            loop.item_fields = []
            in_loop = False
            
            for p in all_paras:
                p_text_raw = _para_text(p)
                if not p_text_raw: continue
                p_norm = normalize(p_text_raw)
                
                has_start = start_tag_norm in p_norm
                has_end = end_tag_norm in p_norm

                found_in_para = []
                for norm_name in raw_to_full:
                    if "tablestart" in norm_name or "tableend" in norm_name: continue
                    if norm_name in p_norm:
                        found_in_para.append(norm_name)

                if has_start and has_end:
                    # Same para containment: just add them all since we normalized
                    for norm_name in found_in_para:
                        full_marker = raw_to_full[norm_name].strip("«»[] ")
                        if full_marker not in loop.item_fields:
                            loop.item_fields.append(full_marker)
                    continue

                if has_start:
                    in_loop = True
                    for norm_name in found_in_para:
                        if norm_name not in loop.item_fields:
                            full_marker = raw_to_full[norm_name].strip("«»[] ")
                            loop.item_fields.append(full_marker)
                    continue

                if has_end:
                    for norm_name in found_in_para:
                        if norm_name not in loop.item_fields:
                            full_marker = raw_to_full[norm_name].strip("«»[] ")
                            loop.item_fields.append(full_marker)
                    in_loop = False
                    continue

                if in_loop:
                    for norm_name in found_in_para:
                        if norm_name not in loop.item_fields:
                            full_marker = raw_to_full[norm_name].strip("«»[] ")
                            loop.item_fields.append(full_marker)

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
                if "TableStart:" in label_text or "TableEnd:" in label_text:
                    continue
                if "TableStart:" in value_text or "TableEnd:" in value_text:
                    continue

                # Look for a marker in the value cell
                marker_found = ""
                # Guillemets first
                guillemets = re.findall(r"[\xab\u00ab]\s*(.*?)\s*[\xbb\u00bb]", value_text)
                if guillemets:
                    marker_found = f"«{guillemets[0].strip()}»"
                else:
                    # Brackets second
                    brackets = re.findall(r"\[(.*?)\]", value_text)
                    if brackets:
                        marker_found = f"[{brackets[0].strip()}]"

                # Check if the marker is a generic placeholder like [Type text]
                is_generic = marker_found.lower() in ("[type text]", "[consultant comments]", "[...]", "type text")
                
                is_blank = not value_text or is_generic
                
                if label_text not in struct.all_table_labels:
                    struct.all_table_labels.append(label_text)

                if marker_found and not is_generic:
                    slot = TableLabelSlot(label=label_text, marker_text=marker_found, is_blank=False)
                    if marker_found not in part_markers:
                        part_markers.append(marker_found)
                else:
                    slot = TableLabelSlot(label=label_text, marker_text=marker_found if is_generic else "", is_blank=True)
                    if label_text not in struct.blank_label_slots:
                        struct.blank_label_slots.append(label_text)
                
                struct.table_label_value_pairs.append(slot)
