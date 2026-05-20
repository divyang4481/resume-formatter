import re

with open("backend/app/services/docx_template_renderer.py", "r") as f:
    content = f.read()

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
