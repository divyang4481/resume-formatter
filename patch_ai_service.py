import re

def update_resume_ai_service():
    with open('backend/app/services/resume_ai_service.py', 'r') as f:
        content = f.read()

    old_analyze = """    async def analyze_template(self, content: bytes, filename: str) -> Dict[str, str]:
        \"\"\"Analyzes a .docx template to suggest metadata... (Uses Tags for Stability)\"\"\"
        # (Template Analysis Logic - Simplified to Tags)
        if not self.extraction_service: return {}

        from app.domain.interfaces import ExtractionContext
        extracted_doc = await self.extraction_service.extract(
            content, filename, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

        # Retrieve placeholders
        from docxtpl import DocxTemplate
        import io, re
        doc = DocxTemplate(io.BytesIO(content))
        detected_placeholders = list(set([str(p).strip() for p in doc.get_undeclared_template_variables()]))

        prompt = prompt_manager.get_prompt(
            "template_analysis.jinja2",
            template_text=extracted_doc.extracted_text[:8000],
            detected_placeholders=detected_placeholders,
        )

        response = self.llm.generate(prompt)
        blocks = LlmSanitizer.extract_tagged_blocks(response)

        # Build Suggestions from Tags
        return {
            "purpose": blocks.get("PURPOSE") or blocks.get("purpose") or "General Template",
            "expected_sections": blocks.get("SECTIONS") or blocks.get("sections") or "Summary, Experience",
            "expected_fields": blocks.get("FIELDS") or blocks.get("fields") or ",".join(detected_placeholders),
        }"""

    new_analyze = """    async def analyze_template(self, content: bytes, filename: str) -> Dict[str, Any]:
        \"\"\"Analyzes a .docx template to suggest metadata and generate a field manifest.\"\"\"
        if not self.extraction_service: return {}

        from app.domain.interfaces import ExtractionContext
        extracted_doc = await self.extraction_service.extract(
            content, filename, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

        # Retrieve placeholders
        from docxtpl import DocxTemplate
        import io, re
        doc = DocxTemplate(io.BytesIO(content))
        detected_placeholders = list(set([str(p).strip() for p in doc.get_undeclared_template_variables()]))

        prompt = prompt_manager.get_prompt(
            "template_analysis.jinja2",
            template_text=extracted_doc.extracted_text[:8000],
            detected_placeholders=detected_placeholders,
        )

        response = self.llm.generate(prompt)
        print(f"\\n--- [LLM RAW RESPONSE: TEMPLATE ANALYSIS] ---\\n{response[:1000]}...\\n")

        # Use clean_json to robustly parse the JSON since the prompt asks for a JSON object
        cleaned_json_str = LlmSanitizer.clean_json(response)

        try:
            parsed = json.loads(cleaned_json_str)
            return {
                "purpose": parsed.get("purpose", "General Template"),
                "expected_sections": parsed.get("expected_sections", "Summary, Experience"),
                "expected_fields": parsed.get("expected_fields") or ",".join(detected_placeholders),
                "summary_guidance": parsed.get("summary_guidance", ""),
                "formatting_guidance": parsed.get("formatting_guidance", ""),
                "field_extraction_manifest": parsed.get("field_extraction_manifest", [])
            }
        except Exception as e:
            logger.error(f"Failed to parse template analysis JSON: {e}")
            # Fallback
            return {
                "purpose": "General Template",
                "expected_sections": "Summary, Experience",
                "expected_fields": ",".join(detected_placeholders),
                "field_extraction_manifest": []
            }"""

    if old_analyze in content:
        content = content.replace(old_analyze, new_analyze)
        with open('backend/app/services/resume_ai_service.py', 'w') as f:
            f.write(content)
        print("Updated backend/app/services/resume_ai_service.py")
    else:
        print("Could not find block to replace in resume_ai_service.py")

update_resume_ai_service()
