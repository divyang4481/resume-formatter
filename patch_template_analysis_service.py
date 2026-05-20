import os

def update_template_analysis_service():
    content = """from typing import Dict, Any
from app.agent.utils.llm_sanitizer import LlmSanitizer
from app.domain.interfaces import LlmRuntimeAdapter, DocumentExtractionService
import json
import logging

logger = logging.getLogger(__name__)

class TemplateAnalysisService:
    def __init__(self, llm: LlmRuntimeAdapter, extraction_service: DocumentExtractionService):
        self.llm = llm
        self.extraction_service = extraction_service

    async def analyze_template(self, content: bytes, filename: str) -> Dict[str, Any]:
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

        from app.agent.prompt_manager import prompt_manager
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
            }
"""
    with open('backend/app/services/template_analysis_service.py', 'w') as f:
        f.write(content)
    print("Updated template_analysis_service.py")

update_template_analysis_service()
