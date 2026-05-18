import io
import re
import logging
import traceback
from typing import Any, Dict, List, Optional
from docxtpl import DocxTemplate, RichText
from docx import Document
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

# 3. Apply CVML rendering actions (recursive)
from docxtpl import DocxTemplate

from app.services.template_structure_extractor import FIELD_ALIAS_MAP

logger = logging.getLogger(__name__)


class ResumeGeneratorService:
    """
    Handles the physical generation of resume documents (DOCX rendering).
    Extracts the template manipulation logic out of the agent nodes into a reusable service.
    """

    def render_formatted_document(
        self,
        template_bytes: bytes,
        resume_data: Dict[str, Any],
        expected_fields: Optional[str] = "",
        field_manifest: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple[bytes, List[str]]:
        """
        Takes raw template bytes and AI-harmonized data, prepares the document markers,
        and renders the final DOCX file.
        Handles scalar, array_simple, array_complex, table_loop, paste_zone,
        and instruction_block field types.
        """
        try:
            template_stream = io.BytesIO(template_bytes)

            expected_fields_list = [
                f.strip() for f in expected_fields.split(",") if f.strip()
            ]

            processed_template_stream = self.prepare_document_markers(
                template_stream, expected_fields_list, field_manifest, resume_data
            )

            # 1.5. Un-nest the AI mapping results - this is our main guide, it must overwrite raw data
            if "template_fill_result" in resume_data:
                mapping_results = resume_data["template_fill_result"]
                if isinstance(mapping_results, dict):
                    for k, v in mapping_results.items():
                        # Always prioritize AI-mapped results (they are healed/validated)
                        resume_data[k] = v

            # 2. Expand array/complex fields into rendering-ready form
            expanded_data = self._expand_array_fields(resume_data, field_manifest or [])

            dummy_doc = DocxTemplate(io.BytesIO())
            processed_resume_data = self._apply_rendering_actions(
                expanded_data, dummy_doc
            )

            # 4. Render final content using docxtpl
            doc = DocxTemplate(processed_template_stream)

            # Flatten the context for universal access
            def flatten_dict(d, parent_key="", sep="_"):
                items = []
                for k, v in d.items():
                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                    if isinstance(v, dict):
                        # It's a field info object from ResumeAiService: { "value": "...", "marker_text": "..." }
                        if "value" in v:
                            val = v["value"]
                            items.append((k, val))
                            if parent_key:
                                items.append((new_key, val))
                        else:
                            items.extend(flatten_dict(v, new_key, sep=sep).items())
                    else:
                        items.append((k, v))
                        if parent_key:
                            items.append((new_key, v))
                return dict(items)

            flattened_context = flatten_dict(processed_resume_data)

            # Prepare render context
            render_context = {**processed_resume_data, **flattened_context}

            import json

            logger.info("\n" + "=" * 60 + "\n--- FINAL RENDER CONTEXT ---\n" + "=" * 60)
            logger.info(json.dumps(render_context, indent=2, default=str))
            logger.info("=" * 60 + "\n")

            # 0. Prep Scoped Context: supports original, lowercase snake_case, and clean alphanumeric keys
            normalized_context = {}
            for k, v in render_context.items():
                normalized_context[k] = v
                std_key = "".join(filter(str.isalnum, k.lower()))
                normalized_context[std_key] = v

            # --- DYNAMIC TAXONOMY MAPPING ---
            # Use FIELD_ALIAS_MAP to provide aliases and fallbacks dynamically
            for canonical, info in FIELD_ALIAS_MAP.items():
                if not isinstance(info, dict):
                    continue
                val = normalized_context.get(canonical)
                if not val:
                    # Try aliases
                    for alias in info.get("aliases", []):
                        val = normalized_context.get(alias) or normalized_context.get(alias.lower()) or normalized_context.get("".join(filter(str.isalnum, alias.lower())))
                        if val:
                            normalized_context[canonical] = val
                            logger.info(f"[Context] Matched alias '{alias}' -> canonical '{canonical}'")
                            break
                
                # If still missing, check if it's a critical field with semantic fallbacks
                # (We can keep some hardcoded semantic fallbacks for logic that isn't just naming)
                if not normalized_context.get(canonical):
                    fallbacks = {
                        "cv_comments": ["summary", "profile_summary"],
                        "professional_qualifications": ["certifications", "education", "skills"],
                        "skills": ["key_skills", "core_competencies"],
                        "employee_name": ["consultant_name"]
                    }
                    if canonical in fallbacks:
                        for fb in fallbacks[canonical]:
                            if normalized_context.get(fb):
                                normalized_context[canonical] = normalized_context[fb]
                                logger.info(f"[Context] Using semantic fallback for '{canonical}' from '{fb}'")
                                break

            class CaseInsensitiveDict(dict):
                def __getitem__(self, key):
                    if key in self:
                        val = super().__getitem__(key)
                        return val if val is not None else ""

                    std_key = "".join(filter(str.isalnum, str(key).lower()))
                    if std_key in self:
                        return super().__getitem__(std_key)

                    snake_key = re.sub(r"(?<!^)(?=[A-Z])", "_", str(key)).lower()
                    if snake_key in self:
                        return super().__getitem__(snake_key)

                    return ""

            smart_context = CaseInsensitiveDict(normalized_context)
            
            # Inject all aliases from taxonomy into smart_context for explicit marker support
            for canonical, info in FIELD_ALIAS_MAP.items():
                if not isinstance(info, dict):
                    continue
                if normalized_context.get(canonical):
                    for alias in info.get("aliases", []):
                        if alias not in smart_context:
                            smart_context[alias] = normalized_context[canonical]

            render_context_with_scope = {
                **render_context,
                **smart_context,
                "_": smart_context,
            }
            logger.info(
                f"[Context] Smart context initialized with {len(smart_context)} keys"
            )

            # --- MISSING FIELD VALIDATION (skip instruction_block fields) ---
            skip_types = {"instruction_block"}
            missing_fields = []
            all_target_keys = set()
            if field_manifest:
                fields_list = field_manifest.get("fields", []) if isinstance(field_manifest, dict) else field_manifest
                all_target_keys.update(
                    [
                        item["fieldname"]
                        for item in fields_list
                        if isinstance(item, dict) and "fieldname" in item and item.get("field_type") not in skip_types
                    ]
                )
            if expected_fields_list:
                all_target_keys.update(expected_fields_list)

            for key in all_target_keys:
                val = render_context_with_scope.get("_", {}).get(key)
                if (
                    val is None
                    or val == ""
                    or val == []
                    or (isinstance(val, str) and "not found" in val.lower())
                ):
                    missing_fields.append(key)

            # Merge missing fields discovered during rendering
            if missing_fields:
                logger.warning(
                    f"RENDERING WARNING: The following template fields remained empty: {missing_fields}"
                )

            logger.info(
                "\n"
                + "#" * 60
                + "\n--- FINAL INJECTED CONTEXT (SMART SCOPE) ---\n"
                + "#" * 60
            )
            for k, v in render_context_with_scope.get("_", {}).items():
                if isinstance(v, (str, list)):
                    val_preview = str(v)[:200] + "..." if len(str(v)) > 200 else str(v)
                    logger.info(f"Field: '{k}' -> Value: {val_preview}")
            logger.info("#" * 60 + "\n")

            doc.render(render_context_with_scope)

            # 5. Save to bytes
            out_stream = io.BytesIO()
            doc.save(out_stream)
            return out_stream.getvalue(), missing_fields

        except Exception as e:
            logger.exception("Document rendering failed with exception details:")
            raise RuntimeError(f"Failed to render document: {str(e)}\n{traceback.format_exc()}")

    def _apply_rendering_actions(self, data: Any, tpl: DocxTemplate) -> Any:
        """
        Recursively pass through the data to convert CVML tags into docxtpl objects.
        """
        if isinstance(data, dict):
            # Process each value in the dictionary
            return {
                k: self._apply_rendering_actions(v, tpl)
                for k, v in data.items()
                if k != "_"
            }

        elif isinstance(data, list):
            # Process each item in the list
            return [self._apply_rendering_actions(item, tpl) for item in data]

        elif isinstance(data, str):
            # Check for CVML tags or line breaks that need conversion
            if "[:" in data or "\n" in data:
                return self._parse_rich_text(data, tpl)
            return data

        return data

    def _parse_rich_text(self, text: str, tpl: DocxTemplate) -> Any:
        """Converts CVML tags like [:B:], [:L1:], etc. into docxtpl RichText."""
        if not text:
            return ""

        rt = RichText()
        text = text.replace("\r\n", "\n")

        # Tokenize by tags
        parts = re.split(r"(\[:/?(?:B|I|U|L|C|H\d|PIPE|BR|L1|L2):?\])", text)

        active_bold = False
        active_italic = False

        for part in parts:
            if not part:
                continue

            if part == "[:B:]":
                active_bold = True
            elif part == "[:/B:]":
                active_bold = False
            elif part == "[:I:]":
                active_italic = True
            elif part == "[:/I:]":
                active_italic = False
            elif part == "[:PIPE:]":
                rt.add("  |  ")
            elif part == "[:BR:]":
                rt.add("\n")
            elif part == "[:L1:]":
                rt.add("\n• ")
            elif part == "[:L2:]":
                rt.add("\n    - ")
            elif part.startswith("[:"):
                continue  # Ignore unknown tags
            else:
                # Actual content
                rt.add(part, bold=active_bold, italic=active_italic)

        return rt

    def _expand_array_fields(
        self, resume_data: Dict[str, Any], field_manifest: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Expands array/complex/loop fields in resume_data into render-ready form.
        """
        expanded = dict(resume_data)

        # Build a quick lookup of field_type by fieldname
        if not field_manifest:
            fields_list = []
        elif isinstance(field_manifest, dict):
            fields_list = field_manifest.get("fields", []) or []
        else:
            fields_list = field_manifest
            
        manifest_map: Dict[str, Dict] = {}
        if fields_list:
            manifest_map = {
                entry["fieldname"]: entry
                for entry in fields_list
                if isinstance(entry, dict) and entry.get("fieldname")
            }

        for fieldname, value in list(expanded.items()):
            entry = manifest_map.get(fieldname, {})
            field_type = entry.get("field_type", "scalar")

            # --- instruction_block: clear from render context ---
            if field_type == "instruction_block" or fieldname.startswith(
                "_instruction_"
            ):
                expanded.pop(fieldname, None)
                continue

            # Unwrap dict-wrapped values (e.g. from template_fill_result containing "value" key)
            if isinstance(value, dict) and "value" in value:
                value = value["value"]

            # --- array_simple: list of strings ---
            if field_type == "array_simple" and isinstance(value, list):
                expanded[fieldname] = [str(v) for v in value if v]
                bullet_str = "\n".join(f"• {v}" for v in expanded[fieldname])
                expanded[f"{fieldname}_str"] = bullet_str

            # --- array_complex: list of sub-field dicts ---
            elif field_type == "array_complex" and isinstance(value, list):
                expanded[fieldname] = value
                for i, item in enumerate(value, start=1):
                    if isinstance(item, dict):
                        for sub_key, sub_val in item.items():
                            expanded[f"{fieldname}_{i}_{sub_key}"] = sub_val

            # --- table_loop: list of dicts for docxtpl tr loops ---
            elif field_type == "table_loop" and isinstance(value, list):
                loop_variable = entry.get("loop_variable", fieldname)
                loop_items = [
                    item if isinstance(item, dict) else {"value": str(item)}
                    for item in value
                ]
                expanded[loop_variable] = loop_items
                if loop_variable != fieldname:
                    expanded[fieldname] = loop_items

        return expanded

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
                if isinstance(v, (str, int, float)) and v != "N/A":
                    data_lookup["".join(filter(str.isalnum, k.lower()))] = v
                if isinstance(v, dict) and "value" in v:
                    val = v["value"]
                    if isinstance(val, (str, int, float)) and val != "N/A":
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

                    # 3. Fallback
                    if not target_key:
                        target_key = raw_marker_text

                    # INJECT JINJA2 TAG (instead of direct replacement)
                    # This allows docxtpl to handle formatting tags like [:B:] and [:L1:] correctly
                    # while our smart context provides the values.
                    norm_target = normalize_key(target_key)

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

            # logger.info(f"SCANNING: '{full_text[:100]}'") # Too verbose for 500 paragraphs

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
                # A simpler but robust way: replace the instrText with the marker and let the rest be.
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

    def generate_error_docx(self, template_id: str, error_message: str) -> bytes:
        """
        Generates a valid (but minimal) DOCX file containing failure details.
        """
        # docx is imported at the top level
        error_doc = Document()
        error_doc.add_heading("TEMPLATE RENDERING ERROR", level=1)
        error_doc.add_paragraph(f"Template Identification: {template_id}")
        error_doc.add_paragraph("-" * 20)
        error_doc.add_paragraph(f"Failure reason detected by system:")
        error_doc.add_paragraph(error_message)

        error_stream = io.BytesIO()
        error_doc.save(error_stream)
        return error_stream.getvalue()
