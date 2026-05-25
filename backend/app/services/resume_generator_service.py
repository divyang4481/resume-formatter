import io
import re
import logging
import traceback
from typing import Any, Dict, List, Optional, Union
from docxtpl import DocxTemplate, RichText
from docx import Document
from docx.table import _Cell, _Row
from docx.text.paragraph import Paragraph
import copy

# 3. Apply CVML rendering actions (recursive)

from app.services.template_structure_extractor import FIELD_ALIAS_MAP
from app.services.document_marker_locator import DocumentMarkerLocator
from app.services.resume_data_formatter import ResumeDataFormatter
from app.services.rich_text_renderer import RichTextRenderer

logger = logging.getLogger(__name__)


TemplateManifestInput = Union[List[Dict[str, Any]], Dict[str, Any]]

class ResumeGeneratorService:
    """
    Handles the physical generation of resume documents (DOCX rendering).
    Extracts the template manipulation logic out of the agent nodes into a reusable service.
    """

    def __init__(self):
        self.marker_locator = DocumentMarkerLocator()
        self.data_formatter = ResumeDataFormatter()
        self.rich_text_renderer = RichTextRenderer()

    def _get_manifest_fields(self, field_manifest: Any) -> List[Dict[str, Any]]:
        if not field_manifest:
            return []
        if isinstance(field_manifest, dict):
            return field_manifest.get("fields", []) or []
        if isinstance(field_manifest, list):
            return field_manifest
        return []

    def render_formatted_document(
        self,
        template_bytes: bytes,
        resume_data: Dict[str, Any],
        expected_fields: Optional[str] = "",
        field_manifest: Optional[TemplateManifestInput] = None,
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

            # 1.5. Un-nest the AI mapping results - this is our main guide, it must overwrite raw data
            if "template_fill_result" in resume_data:
                logger.info("Found template_fill_result in resume_data, un-nesting mappings...")
                mapping_results = resume_data["template_fill_result"]
                if isinstance(mapping_results, dict):
                    for k, v in mapping_results.items():
                        # Always prioritize AI-mapped results (they are healed/validated)
                        if isinstance(v, dict) and "value" in v:
                            val = v.get("value")
                            if val is None and isinstance(v.get("field_extraction_manifest"), dict):
                                val = v["field_extraction_manifest"].get("value")
                            resume_data[k] = val if val is not None else ""
                            logger.info(f"[Un-nest] Extracted '{k}': {str(resume_data[k])[:100]}")
                        else:
                            resume_data[k] = v if v is not None else ""
                            logger.info(f"[Un-nest] Extracted raw '{k}': {str(resume_data[k])[:100]}")

            # 1.5. Expand array/complex fields into rendering-ready form FIRST
            expanded_data = self.data_formatter.expand_array_fields(resume_data, self._get_manifest_fields(field_manifest))

            # 2. Prepare document markers (uses expanded data like _str)
            processed_template_stream = self.marker_locator.prepare_document_markers(
                template_stream, expected_fields_list, field_manifest, expanded_data
            )

            processed_resume_data = self.rich_text_renderer.apply_rendering_actions(expanded_data)

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
                            val = v.get("value")
                            if val is None and isinstance(v.get("field_extraction_manifest"), dict):
                                val = v["field_extraction_manifest"].get("value")
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

                def get(self, key, default=None):
                    value = self.__getitem__(key)
                    return default if value == "" else value

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
                if val is None or val == "" or val == []:
                    std_key = "".join(filter(str.isalnum, key.lower()))
                    val = render_context_with_scope.get("_", {}).get(std_key)

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
            out_stream.seek(0)
            
            # --- POST-RENDER VALIDATION ---
            try:
                final_doc = Document(out_stream)
                out_stream.seek(0)
                
                unresolved = []
                check_texts = ["«", "»", "{{", "}}", "TableStart", "TableEnd", "MACROBUTTON", "[Type text]"]
                
                def check_text(t):
                    if not t: return
                    if any(m in t for m in check_texts):
                        unresolved.append(t)
                    elif "paste the candidate" in t.lower() and "cv" in t.lower():
                        unresolved.append(t)

                for p in final_doc.paragraphs:
                    check_text(p.text)
                for tbl in final_doc.tables:
                    for row in tbl.rows:
                        for cell in row.cells:
                            check_text(cell.text)
                            
                if unresolved:
                    logger.warning(f"POST-RENDER WARNING: Found {len(unresolved)} unresolved markers or instruction texts in final document. Sample: {unresolved[:3]}")
                    missing_fields.append("UNRESOLVED_MARKERS_PRESENT")
            except Exception as v_err:
                logger.warning(f"Failed to run post-render validation: {v_err}")

            return out_stream.getvalue(), missing_fields

        except Exception as e:
            logger.exception("Document rendering failed with exception details:")
            raise RuntimeError(f"Failed to render document: {str(e)}\n{traceback.format_exc()}")

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
