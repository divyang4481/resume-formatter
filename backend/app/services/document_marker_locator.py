import io
import re
import logging
import copy
from typing import Any, Dict, List, Optional
from docx import Document
from docx.table import _Cell, _Row
from docx.text.paragraph import Paragraph
from app.services.template_structure_extractor import FIELD_ALIAS_MAP

logger = logging.getLogger(__name__)

class DocumentMarkerLocator:
    """
    Handles preprocessing of DOCX markers and applying structural rendering locators
    using python-docx primitives directly, before docxtpl runs.
    """

    def apply_render_locators(
        self,
        doc: Document,
        field_manifest: List[Dict[str, Any]],
        render_context: Dict[str, Any]
    ) -> None:
        """
        Executes explicit structural render locator strategies directly on the DOCX before docxtpl runs.
        """
        logger.info(f"Applying structural render locators...")
        if not field_manifest:
            return

        fields_list = field_manifest.get("fields", []) if isinstance(field_manifest, dict) else field_manifest
        if not fields_list:
            return

        for field_def in fields_list:
            if not isinstance(field_def, dict):
                continue
            
            fieldname = field_def.get("fieldname")
            if not fieldname:
                continue

            locator = field_def.get("render_locator", {})
            if not locator:
                continue

            strategy = locator.get("strategy")
            label = locator.get("label", "").strip()
            
            # --- STRATEGY: fill_blank_cell_after_label ---
            if strategy == "fill_blank_cell_after_label" and label:
                for tbl in doc.tables:
                    for row in tbl.rows:
                        for i, cell in enumerate(row.cells):
                            cell_text = cell.text.strip().lower()
                            label_norm = label.lower()
                            
                            if cell_text == label_norm or (label_norm in cell_text and len(cell_text) < len(label_norm) + 10):
                                if i + 1 < len(row.cells):
                                    adj_cell = row.cells[i + 1]
                                    adj_text = adj_cell.text.strip()
                                    
                                    is_placeholder = (
                                        not adj_text or 
                                        adj_text == "£" or 
                                        adj_text == "$" or 
                                        "type text" in adj_text.lower() or
                                        "macrobutton" in adj_text.lower()
                                    )
                                    
                                    if is_placeholder:
                                        prefix = "£ " if "£" in adj_text else ""
                                        prefix = "$ " if "$" in adj_text and not prefix else prefix
                                        
                                        for p in adj_cell.paragraphs:
                                            p.text = ""
                                        
                                        if f"{fieldname}_str" in render_context:
                                            adj_cell.paragraphs[0].text = f"{prefix}{{{{r _['{fieldname}_str'] }}}}"
                                        else:
                                            adj_cell.paragraphs[0].text = f"{prefix}{{{{ _['{fieldname}'] }}}}"
                                        logger.info(f"Structural fill: '{label}' -> field '{fieldname}'")

            # --- STRATEGY: replace_table_loop ---
            elif strategy == "replace_table_loop":
                marker_text = field_def.get("marker_text", "")
                if "TableStart:" in marker_text:
                    loop_name = marker_text.split("TableStart:")[1].split("»")[0].strip("><]}[{")
                    
                    for tbl in doc.tables:
                        for r_idx, row in enumerate(tbl.rows):
                            row_text = "".join(c.text for c in row.cells)
                            if f"TableStart:{loop_name}" in row_text or f"tablestart:{loop_name.lower()}" in row_text.lower():
                                items = render_context.get(fieldname, [])
                                if not isinstance(items, list):
                                    items = render_context.get(loop_name, [])
                                    
                                if isinstance(items, list) and items:
                                    logger.info(f"Replacing table loop for {loop_name} with {len(items)} items")
                                    item_key = loop_name
                                    match = re.search(r'(?:«|\[|<|{)(?!TableStart|TableEnd)(.*?)(?:»|\]|>|})', row_text, flags=re.IGNORECASE)
                                    if match:
                                        item_key = match.group(1).strip()
                                    
                                    row_elm = row._tr
                                    parent = row_elm.getparent()
                                    idx = parent.index(row_elm)
                                    for item_val in items:
                                        val_str = ""
                                        if isinstance(item_val, str):
                                            val_str = item_val
                                        elif isinstance(item_val, dict):
                                            val_str = str(item_val.get(item_key, item_val.get("value", "")))
                                            
                                        new_row_elm = copy.deepcopy(row_elm)
                                        new_row_obj = _Row(new_row_elm, tbl)
                                        
                                        for cell in new_row_obj.cells:
                                            text = cell.text
                                            text = re.sub(r'(?:«|\[|<|{)\s*TableStart:[^»\]>}]*(?:»|\]|>|})', '', text, flags=re.IGNORECASE)
                                            text = re.sub(r'(?:«|\[|<|{)\s*TableEnd:[^»\]>}]*(?:»|\]|>|})', '', text, flags=re.IGNORECASE)
                                            text = re.sub(rf'(?:«|\[|<|{{)\s*{item_key}\s*(?:»|\]|>|}})', val_str, text, flags=re.IGNORECASE)
                                            if item_key in text:
                                                text = text.replace(item_key, val_str)
                                                
                                            for p in cell.paragraphs:
                                                p.text = ""
                                            if cell.paragraphs:
                                                cell.paragraphs[0].text = text
                                                
                                        parent.insert(idx, new_row_elm)
                                        idx += 1
                                        
                                    parent.remove(row_elm)

            # --- STRATEGY: replace_section_body or paste_zone ---
            elif strategy in ("replace_bullet_list_under_heading", "replace_bullets_under_heading"):
                heading = (locator.get("heading") or locator.get("heading_text") or "").strip()
                values = render_context.get(fieldname)
                if not heading or not isinstance(values, list):
                    continue
                def process_bullet_container(paragraphs_list):
                    heading_idx = None
                    for i, p in enumerate(paragraphs_list):
                        if re.sub(r"\s+", " ", p.text.strip()).lower() == re.sub(r"\s+", " ", heading).lower():
                            heading_idx = i
                            break
                    if heading_idx is None:
                        return False
                    placeholder_re = re.compile(r"^\s*(?:\[type text\]|«type text»|type text)?\s*$", re.IGNORECASE)
                    anchor_p = paragraphs_list[heading_idx]
                    next_elm = anchor_p._element.getnext()
                    removed = 0
                    while next_elm is not None and next_elm.tag.endswith("p"):
                        p_obj = Paragraph(next_elm, doc)
                        txt = p_obj.text.strip()
                        p_style = (p_obj.style.name.lower() if p_obj.style and p_obj.style.name else "")
                        is_heading = "heading" in p_style or (txt.isupper() and len(txt) < 80)
                        is_bullet_like = txt.startswith("•") or txt.startswith("-") or placeholder_re.match(txt) or not txt
                        if is_heading:
                            break
                        if txt and not is_bullet_like and removed > 0:
                            break
                        if placeholder_re.match(txt) or txt.startswith("• [Type text]") or txt.startswith("• «Type text»") or not txt:
                            to_remove = next_elm
                            next_elm = next_elm.getnext()
                            to_remove.getparent().remove(to_remove)
                            removed += 1
                            continue
                        next_elm = next_elm.getnext()
                    for item in reversed([str(v) for v in values if str(v).strip()]):
                        p = doc.add_paragraph(f"• {item}")
                        anchor_p._element.addnext(p._element)
                    logger.info(f"Structural fill: replaced bullet section '{heading}' with {len(values)} item(s)")
                    return True
                
                if not process_bullet_container(doc.paragraphs):
                    for tbl in doc.tables:
                        for row in tbl.rows:
                            for cell in row.cells:
                                if process_bullet_container(cell.paragraphs):
                                    break
                            else:
                                continue
                            break
                        else:
                            continue
                        break

            # --- STRATEGY: replace_section_body or paste_zone or replace_complex_block ---
            elif strategy in ("replace_section_body", "paste_zone", "replace_complex_block"):
                def is_heading_match(p_text: str, target_heading: str) -> bool:
                    if not p_text or not target_heading:
                        return False
                    norm_p = re.sub(r'[^a-zA-Z0-9]', '', p_text).lower()
                    norm_t = re.sub(r'[^a-zA-Z0-9]', '', target_heading).lower()
                    return norm_p == norm_t or (len(norm_t) > 3 and norm_t in norm_p and len(norm_p) < len(norm_t) + 10)

                def is_heading_boundary(p) -> bool:
                    text = p.text.strip()
                    if not text:
                        return False
                    
                    # Check if it matches any other known field heading
                    for f in fields_list:
                        f_loc = f.get("render_locator", {})
                        f_head = f_loc.get("heading") or f.get("marker_text") or f.get("canonical_fieldname", "")
                        if f_head and is_heading_match(text, f_head):
                            return True
                            
                    style_name = p.style.name.lower() if p.style and p.style.name else ""
                    if "heading" in style_name or style_name.startswith("h") and any(style_name.endswith(str(i)) for i in range(1, 7)):
                        return True
                    is_bold = any(run.bold for run in p.runs)
                    if is_bold and len(text) < 60 and not text.startswith("["):
                        return True
                    if text.isupper() and len(text) < 60:
                        return True
                    return False

                if fieldname in render_context and render_context[fieldname]:
                    target_heading = locator.get("heading") or field_def.get("marker_text") or fieldname
                    def process_section_container(paragraphs_list):
                        found_heading = False
                        for idx, p in enumerate(paragraphs_list):
                            p_text = p.text.strip()
                            if is_heading_match(p_text, target_heading):
                                # Find first non-empty paragraph immediately following
                                target_p = None
                                for next_idx in range(idx + 1, len(paragraphs_list)):
                                    next_p = paragraphs_list[next_idx]
                                    text_strip = next_p.text.strip()
                                    if text_strip:
                                        if is_heading_boundary(next_p) or (len(text_strip) > 2 and len(text_strip) < 40 and text_strip.isupper()):
                                            break # Hit next heading, so no placeholder here
                                        target_p = next_p
                                        break
                                
                                # If no target paragraph is found in the same block, 
                                # and we are in a table cell, look at the next cell in the row
                                if not target_p and hasattr(p._element, "getparent"):
                                    parent_tc = p._element.getparent()
                                    if parent_tc is not None and parent_tc.tag.endswith("tc"):
                                        parent_tr = parent_tc.getparent()
                                        if parent_tr is not None:
                                            tcs = [c for c in parent_tr if c.tag.endswith("tc")]
                                            try:
                                                my_tc_idx = tcs.index(parent_tc)
                                                if my_tc_idx + 1 < len(tcs):
                                                    next_tc = tcs[my_tc_idx + 1]
                                                    for child in next_tc:
                                                        if child.tag.endswith("p"):
                                                            next_p = Paragraph(child, parent_tc)
                                                            text_strip = next_p.text.strip()
                                                            if text_strip:
                                                                if is_heading_boundary(next_p) or (len(text_strip) > 2 and len(text_strip) < 40 and text_strip.isupper()):
                                                                    break
                                                                target_p = next_p
                                                                break
                                            except ValueError:
                                                pass
                                
                                if target_p:
                                    logger.info(f"[Locator] Found heading '{p_text}' for field '{fieldname}'. Replacing section body...")
                                    if f"{fieldname}_str" in render_context:
                                        target_p.text = f"{{{{r _['{fieldname}_str'] }}}}"
                                    else:
                                        target_p.text = f"{{{{ _['{fieldname}'] }}}}"
                                    
                                    # Prune subsequent paragraphs in this section until next heading or table
                                    curr = target_p._element.getnext()
                                    to_delete = []
                                    while curr is not None:
                                        tag = curr.tag
                                        if tag.endswith("tbl"):
                                            break
                                        elif tag.endswith("p"):
                                            p_obj = Paragraph(curr, doc)
                                            if is_heading_boundary(p_obj):
                                                break
                                            to_delete.append(curr)
                                        curr = curr.getnext()
                                    
                                    if to_delete:
                                        logger.info(f"[Locator] Pruning {len(to_delete)} placeholder paragraphs from section '{p_text}'")
                                        for elm in to_delete:
                                            elm.getparent().remove(elm)
                                    
                                    found_heading = True
                                    break
                                else:
                                    logger.info(f"[Locator] Found heading '{p_text}' for field '{fieldname}' but no placeholder text found. Appending content.")
                                    # Insert a new paragraph immediately after the heading
                                    from docx.oxml import OxmlElement
                                    new_p = OxmlElement('w:p')
                                    p._p.addnext(new_p)
                                    new_p_obj = Paragraph(new_p, p._parent)
                                    if f"{fieldname}_str" in render_context:
                                        new_p_obj.text = f"{{{{r _['{fieldname}_str'] }}}}"
                                    else:
                                        new_p_obj.text = f"{{{{ _['{fieldname}'] }}}}"
                                    p._element.addnext(new_p_obj._element)
                                    found_heading = True
                                    break
                        return found_heading

                    found_heading = process_section_container(doc.paragraphs)
                    if not found_heading:
                        for tbl in doc.tables:
                            for row in tbl.rows:
                                for cell in row.cells:
                                    if process_section_container(cell.paragraphs):
                                        found_heading = True
                                        break
                                if found_heading:
                                    break
                            if found_heading:
                                break
                    
                    # Fallback to simple paragraph content check
                    if not found_heading:
                        for p in doc.paragraphs:
                            p_text = p.text.lower()
                            if "paste" in p_text and "cv" in p_text:
                                p.text = f"{{{{ _['{fieldname}'] }}}}"
                                logger.info(f"[Locator] Fallback structural fill: replaced CV paste zone.")

        return

    def prepare_document_markers(
        self,
        template_stream: io.BytesIO,
        field_list: List[str],
        field_manifest: Optional[List[Dict[str, Any]]] = None,
        resume_data: Optional[Dict[str, Any]] = None,
    ) -> io.BytesIO:
        """
        Scans the document for various marker patterns and normalizes them.
        """
        doc = Document(template_stream)
        counter = 0

        # Build a lookup for direct replacement if we have data
        data_lookup = {}
        if resume_data:
            # Flatten/standardize for easier lookup
            for k, v in resume_data.items():
                if isinstance(v, (str, int, float)) and str(v).strip() and v != "N/A":
                    data_lookup["".join(filter(str.isalnum, k.lower()))] = v
                if isinstance(v, dict) and "value" in v:
                    val = v.get("value")
                    if val is None and isinstance(v.get("field_extraction_manifest"), dict):
                        val = v["field_extraction_manifest"].get("value")
                    if isinstance(val, (str, int, float)) and str(val).strip() and val != "N/A":
                        data_lookup["".join(filter(str.isalnum, k.lower()))] = val
            logger.info(
                f"[Lookup] Created data_lookup with {len(data_lookup)} keys: {list(data_lookup.keys())[:20]}..."
            )

        # --- Phase 0: Clear instruction blocks ---
        if field_manifest:
            instruction_texts = []
            
            # Support new dict manifest format
            if isinstance(field_manifest, dict):
                instruction_texts.extend(field_manifest.get("instruction_blocks", []))
                
            fields_list = field_manifest.get("fields", []) if isinstance(field_manifest, dict) else field_manifest
            if not fields_list:
                fields_list = []
            for item in fields_list:
                if not isinstance(item, dict):
                    continue
                if (
                    item.get("render_locator", {}).get("strategy") == "clear_instruction_block" or
                    item.get("field_type") == "instruction_block"
                ):
                    target_text = item.get("marker_text", "").strip()
                    if target_text:
                        instruction_texts.append(target_text)

            for target_text in instruction_texts:
                if not isinstance(target_text, str) or not target_text:
                    continue
                
                # Normalize whitespace and case for robust matching
                match_prefix = target_text.strip()[:100].replace("\xa0", " ").lower()
                
                for para in doc.paragraphs:
                    p_text_norm = para.text.replace("\xa0", " ").lower()
                    if match_prefix in p_text_norm:
                        para.text = ""
                for tbl in doc.tables:
                    for row in tbl.rows:
                        for cell in row.cells:
                            c_text_norm = cell.text.replace("\xa0", " ").lower()
                            if match_prefix in c_text_norm:
                                for p in cell.paragraphs:
                                    p.text = ""

        # Regex for common placeholder patterns - handle guillemets and brackets with wide whitespace support
        # Supports: «Field», <<Field>>, [[Field]], [Field], {Field}
        MARKER_PATTERN = r"(?:<<|\[\[|«|\[|<|\{)\s*([^\xab\xbb\(\)\[\]\{\}><]+?)\s*(?:>>|\]\]|»|\]|>|\})"

        def normalize_key(k: str) -> str:
            return re.sub(r"[^a-z0-9]", "", k.lower())

        def transform_text(text, fields, current_counter, manifest):
            # Find all matches in the original text (including guillemets)
            matches = list(re.finditer(MARKER_PATTERN, text))

            if not matches:
                # Try raw brackets
                matches = list(re.finditer(r"\[([^\]]+)\]", text))

            new_text = text

            # Sort matches in reverse order to replace without messing up indices
            for match in sorted(matches, key=lambda x: x.start(), reverse=True):
                original = match.group(0)
                start, end = match.span()

                # Skip if this match is part of an already injected Jinja tag
                # Our injected tags look like {{ _['fieldname'] }} or {{ item['fieldname'] }}
                if original.startswith("['") and original.endswith("']"):
                    prefix = text[max(0, start-5):start]
                    if prefix.endswith("_") or prefix.endswith("item"):
                        continue

                raw_marker_text = match.group(1).strip()
                target_key = None
                # --- HAYS SPECIAL: TableStart / TableEnd (Must be checked first) ---
                if "tablestart:" in raw_marker_text.lower():
                    loop_key = raw_marker_text.split(":", 1)[1].strip()
                    # Clean the loop key from guillemets if any
                    loop_key = loop_key.strip("«»[]<>{} ")
                    # Use standard for loop with fallback to global context
                    replacement = f"{{% for item in _['{loop_key}'] %}}"
                    target_key = "LOOP_START"  # Mark as handled
                elif "tableend:" in raw_marker_text.lower():
                    replacement = "{% endfor %}"
                    target_key = "LOOP_END"  # Mark as handled

                if not target_key:
                    # 1. Try to find in manifest
                    if manifest:
                        norm_raw = normalize_key(raw_marker_text)
                        fields_list = manifest.get("fields", []) if isinstance(manifest, dict) else manifest
                        for item in fields_list:
                            if not isinstance(item, dict):
                                continue
                            m_text = item.get("marker_text", "")
                            norm_m = normalize_key(m_text)

                            if (
                                m_text == original
                                or m_text == raw_marker_text
                                or norm_m == norm_raw
                            ):
                                target_key = item.get("fieldname")
                                break

                            clean_m = m_text.strip("«»[]<>{}")
                            if normalize_key(clean_m) == norm_raw:
                                target_key = item.get("fieldname")
                                break

                    # 2. Smart Fuzzy Mapping
                    if not target_key:
                        norm_marker = normalize_key(raw_marker_text)
                        for field in fields:
                            norm_field = normalize_key(field)
                            if (
                                norm_marker
                                and norm_field
                                and (
                                    norm_marker == norm_field
                                    or norm_marker in norm_field
                                    or norm_field in norm_marker
                                )
                            ):
                                target_key = field
                                break
                    
                    # 2.5 Alias mapping fallback via canonical taxonomy map
                    if not target_key:
                        norm_marker = normalize_key(raw_marker_text)
                        for canonical, info in FIELD_ALIAS_MAP.items():
                            candidates = [canonical] + list((info or {}).get("aliases", []))
                            for alias in candidates:
                                if normalize_key(alias) == norm_marker:
                                    target_key = canonical
                                    break
                            if target_key:
                                break

                    # 3. Fallback
                    if not target_key:
                        target_key = raw_marker_text

                    # INJECT JINJA2 TAG (instead of direct replacement)
                    # This allows docxtpl to handle formatting tags like [:B:] and [:L1:] correctly
                    # while our smart context provides the values.
                    norm_target = normalize_key(target_key)
                    # If no concrete value exists, preserve original marker text.
                    # This avoids blanking unresolved placeholders such as EmployeeJobTitle.
                    if norm_target not in data_lookup:
                        logger.info(
                            f"Preserving unresolved marker '{original}' (mapped='{target_key}') due to empty/missing value."
                        )
                        continue

                    # If we are inside a loop, we might need 'item.'
                    subfields = {
                        "jobtitle",
                        "company",
                        "startdate",
                        "enddate",
                        "description",
                        "degree",
                        "institution",
                        "year",
                        "grade",
                    }
                    if normalize_key(target_key) in subfields:
                        replacement = f"{{{{ item['{target_key}'] if item is defined else _['{target_key}'] }}}}"
                    else:
                        # Use a very safe check using our scoped context '_'
                        # We use _['key'] which our CaseInsensitiveDict handles gracefully
                        replacement = f"{{{{ _['{target_key}'] }}}}"

                    logger.info(
                        f"Mapped marker '{original}' to Jinja2 tag: '{replacement}'"
                    )

                start, end = match.span()
                new_text = new_text[:start] + replacement + new_text[end:]
                logger.debug(f"Marker Replaced: '{original}' -> '{replacement}'")

            return new_text, current_counter

        def process_paragraph(paragraph, fields, current_counter, manifest):
            full_text = paragraph.text
            if not full_text or len(full_text.strip()) < 2:
                return current_counter

            # 1. First, check manifest for VERBATIM matches (Instruction blocks, etc.)
            if manifest:
                # If manifest is a dict (new TemplateManifest structure), extract 'fields'
                fields_list = manifest.get("fields", []) if isinstance(manifest, dict) else manifest
                
                for item in fields_list:
                    if not isinstance(item, dict):
                        continue
                    field_type = item.get("field_type", "scalar")
                    anchor = item.get("marker_text", "")
                    fieldname = item.get("fieldname", "")

                    if not anchor:
                        continue

                    if field_type == "instruction_block" and anchor in full_text:
                        logger.info(f"Instruction Block Clear: '{anchor}'")
                        paragraph.text = ""
                        return current_counter

                    if field_type == "paste_zone" and anchor.lower() in full_text.lower():
                        strategy = item.get("render_locator", {}).get("strategy") or item.get("injection_hints", {}).get("strategy")
                        if strategy == "replace_section_body":
                            logger.info(f"Skipping heading '{full_text}' for field '{fieldname}' since it is handled by replace_section_body strategy.")
                            return current_counter
                            
                        logger.info(f"Paste Zone Replace: '{anchor}' -> '{fieldname}'")
                        # If the anchor is just a heading (e.g., 'Work Experience'), append the content. 
                        # If it's an instruction (e.g., 'Paste CV here'), replace it entirely.
                        if any(kw in anchor.lower() for kw in ["paste", "insert", "own cv"]):
                            paragraph.text = f"{{{{ _['{fieldname}'] }}}}"
                        else:
                            paragraph.text = full_text + f"\n{{{{ _['{fieldname}'] }}}}"
                        return current_counter

            # 2. Check for patterns (guillemets, brackets, etc.)
            has_marker = any(
                m in full_text
                for m in ["«", "»", "<<", ">>", "[[", "]]", "{{", "}}", "[", "<", "{"]
            )
            if has_marker:
                logger.info(
                    f"Potential marker detected in paragraph: '{full_text[:100]}'"
                )
                new_text, next_counter = transform_text(
                    full_text, fields, current_counter, manifest
                )
                if new_text != full_text:
                    logger.info(f"PARAGRAPH UPDATE: '{full_text}' -> '{new_text}'")
                    # Direct update is safer than clearing runs if we don't care about run-level bold/italic
                    paragraph.text = new_text
                return next_counter

            return current_counter

        def iter_all_paragraphs(parent):
            """Recursively finds all paragraphs in the document (including text boxes and nested tables)."""
            # Handle the fact that Document is a factory function, the class is _Document
            from docx.document import Document as _Document

            if isinstance(parent, _Document):
                parent_elm = parent.element.body
            elif hasattr(parent, "_element"):
                parent_elm = parent._element
            elif isinstance(parent, _Cell):
                parent_elm = parent._tc
            else:
                parent_elm = parent

            if parent_elm is not None:
                # Use XPath to find ALL paragraphs regardless of nesting
                # This catches text boxes, tables, etc.
                for p_elm in parent_elm.xpath(".//w:p"):
                    yield Paragraph(p_elm, parent)

        def flatten_merge_fields(doc):
            """
            NORMALIZATION PHASE:
            Converts Word MERGEFIELD structures into plain text markers like «FieldName».
            We replace the specific XML nodes so we don't lose surrounding text.
            """
            from lxml import etree

            W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

            parts = [doc]
            for s in doc.sections:
                parts.extend(
                    [
                        s.header,
                        s.first_page_header,
                        s.even_page_header,
                        s.footer,
                        s.first_page_footer,
                        s.even_page_footer,
                    ]
                )

            for part in parts:
                if not part or not hasattr(part, "_element"):
                    continue

                # 1. Handle Simple Fields (w:fldSimple)
                # These are single nodes, easy to replace.
                simple_fields = part._element.xpath(
                    './/w:fldSimple[contains(@w:instr, "MERGEFIELD")]'
                )
                for fld in simple_fields:
                    instr = fld.get(W_NS + "instr")
                    match = re.search(r'MERGEFIELD\s+"?([^"\s>]+)"?', instr)
                    if match:
                        field_name = match.group(1)
                        # Create a new run node with the marker text
                        new_r = etree.Element(W_NS + "r")
                        new_t = etree.SubElement(new_r, W_NS + "t")
                        new_t.text = f"«{field_name}»"
                        # Replace fldSimple with the new run
                        parent = fld.getparent()
                        parent.replace(fld, new_r)
                        logger.info(f"Flattened SimpleField: {field_name}")

                # 2. Handle Complex Fields (split across multiple runs)
                # We find the instrText and replace the whole begin...end sequence if possible
                # But for now, just replacing the instrText's containing run with a marker is often enough
                # if we also clear the separate/end characters.
                # A simpler but robust way: replace the instrText with the marker and let the let the rest be.
                instr_texts = part._element.xpath(
                    './/w:instrText[contains(text(), "MERGEFIELD")]'
                )
                for instr in instr_texts:
                    match = re.search(r'MERGEFIELD\s+"?([^"\s>]+)"?', instr.text)
                    if match:
                        field_name = match.group(1)
                        # We turn the instrText into a normal text node and clear the instruction
                        instr.text = f"«{field_name}»"
                        # Change tag from w:instrText to w:t
                        instr.tag = W_NS + "t"
                        logger.info(f"Flattened ComplexField: {field_name}")

                # 3. Handle Macro Buttons (MACROBUTTON nomacro [Type text])
                macros = part._element.xpath(
                    './/w:instrText[contains(text(), "MACROBUTTON")]'
                )
                for macro in macros:
                    match = re.search(r"MACROBUTTON\s+nomacro\s+\[(.*?)\]", macro.text)
                    if match:
                        placeholder = match.group(1)
                        macro.text = f"«{placeholder}»"
                        macro.tag = W_NS + "t"
                        logger.info(f"Flattened MacroButton: {placeholder}")

        # 0. Flatten MergeFields into plain text markers
        logger.info("Starting document normalization (flattening complex fields)...")
        flatten_merge_fields(doc)
        
        # 0.5. Apply Structural Locators
        if resume_data:
            self.apply_render_locators(doc, field_manifest or [], resume_data)

        # 1. Process all parts of the document in a single pass
        parts = [doc]
        for section in doc.sections:
            parts.extend(
                [section.header, section.first_page_header, section.even_page_header]
            )
            parts.extend(
                [section.footer, section.first_page_footer, section.even_page_footer]
            )

        logger.info(f"Scanning {len(parts)} document parts for markers...")
        for part in parts:
            if not part:
                continue
            for p in iter_all_paragraphs(part):
                # 1.1 Heuristic Run Healing (consolidate split markers)
                t = p.text
                if any(m in t for m in ["«", "»", "<<", ">>", "[[", "]]", "[", "<"]):
                    if len(p.runs) > 1:
                        full_text = p.text
                        for run in p.runs:
                            run.text = ""
                        p.runs[0].text = full_text

                # 1.2 Replace markers with tags or direct values
                counter = process_paragraph(p, field_list, counter, field_manifest)

        processed_stream = io.BytesIO()
        doc.save(processed_stream)
        processed_stream.seek(0)
        logger.info("Document normalization and marker injection complete.")
        return processed_stream
