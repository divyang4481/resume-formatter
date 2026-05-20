import re

with open("backend/app/services/docx_template_renderer.py", "r") as f:
    content = f.read()

# Add _format_complex_list
if "def _format_complex_list" not in content:
    format_code = """
    def _format_complex_list(self, v: list) -> str:
        formatted_lines = []
        for item in v:
            if "job_title" in item or "company" in item:
                title = item.get("job_title", "Position")
                company = item.get("company", "Company")
                dates = f"{item.get('start_date', '')} - {item.get('end_date', 'Present')}"
                desc = (
                    item.get("description")
                    or item.get("responsibilities")
                    or ""
                )
                block = f"• {title} | {company} ({dates})"
                if desc:
                    if isinstance(desc, list):
                        desc_str = "\\n  - " + "\\n  - ".join(desc)
                        block += desc_str
                    else:
                        block += f"\\n  {desc}"
                formatted_lines.append(block)
            elif "degree" in item or "institution" in item:
                degree = item.get("degree", "Qualification")
                school = item.get("institution", "Institution")
                year = item.get("graduation_year") or item.get("year") or ""
                formatted_lines.append(f"• {degree}, {school} ({year})")
            else:
                formatted_lines.append(f"• {str(item)}")
        return "\\n\\n".join(formatted_lines)
"""
    content = content.replace("    def _prepare_render_context", format_code + "\n    def _prepare_render_context")

# Update _direct_replace_ai_markers
old_code = """                if isinstance(value, str) and value != "N/A":
                    self._replace_in_doc(doc, marker, value)"""
new_code = """                if isinstance(value, str) and value != "N/A":
                    self._replace_in_doc(doc, marker, value)
                elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                    formatted_str = self._format_complex_list(value)
                    self._replace_complex_block(doc, marker, formatted_str)"""
content = content.replace(old_code, new_code)

# Update _inject_jinja_markers
old_inject = """            elif strategy_info.strategy == "replace_section_body" and strategy_info.heading:
                self._replace_section_content(doc, strategy_info.heading, tag)"""
new_inject = """            elif strategy_info.strategy == "replace_section_body" and strategy_info.heading:
                self._replace_section_content(doc, strategy_info.heading, tag)
            elif strategy_info.strategy == "replace_complex_block":
                self._replace_complex_block(doc, strategy_info.marker_text, tag)"""
content = content.replace(old_inject, new_inject)

with open("backend/app/services/docx_template_renderer.py", "w") as f:
    f.write(content)
