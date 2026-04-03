from typing import Dict, Any, Optional, List
import json
from app.domain.interfaces import DocumentExtractionService
from app.adapters.base import LlmRuntimeAdapter

class ResumeAiService:
    def __init__(self, llm: LlmRuntimeAdapter, extraction_service: Optional[DocumentExtractionService] = None):

        self.llm = llm
        self.extraction_service = extraction_service

    async def generate_summary(
        self, 
        extracted_text: str, 
        guidance: str, 
        industry: Optional[str] = None, 
        language: str = "en"
    ) -> str:
        """
        Generates a high-impact professional summary based on raw extracted text and template guidance.
        """
        prompt = f"""
        TASK: Generate a high-impact 'Executive Summary' for a professional CV.
        
        INPUT TEXT:
        {extracted_text[:12000]}  # Limit context
        
        INDUSTRY CONTEXT: {industry or 'General Professional'}
        LANGUAGE: {language}
        
        GOVERNANCE & STYLE GUIDANCE:
        {guidance or "Ensure a professional, concise tone. Highlight key achievements and core competencies."}
        
        OUTPUT REQUIREMENTS:
        - Return ONLY the summary text.
        - Do not include headers like 'Professional Summary:'.
        - Strictly follow the guidance provided above.
        - Ensure NO template placeholders (like <<Name>>) are present in the output.
        """
        
        response = self.llm.generate(prompt)
        return response.strip()

    async def analyze_template(self, content: bytes, filename: str) -> Dict[str, str]:
        """
        Analyzes a .docx template to suggest metadata and guidance.
        """
        if not self.extraction_service:
            return {}

        # 1. Extract text from the template document
        from app.domain.interfaces import ExtractionContext
        context = ExtractionContext(intent="template_analysis", actor_role="admin")
        extracted_doc = await self.extraction_service.extract(content, filename, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", context=context)

        template_text = extracted_doc.extracted_text

        # 1.5 Extract placeholders programmatically if it's a docx
        detected_placeholders = []
        try:
            from docxtpl import DocxTemplate
            import io
            doc = DocxTemplate(io.BytesIO(content))
            detected_placeholders = list(doc.get_undeclared_template_variables())
            print(f"Programmatically detected {len(detected_placeholders)} Jinja2 placeholders in template.")
        except Exception as e:
            print(f"Warning: Failed to extract Jinja2 placeholders: {e}")

        # 1.6 Additional regex for alternative placeholders (e.g. << Field Name >>)
        import re
        alt_placeholders = re.findall(r'<<\s*(.*?)\s*>>', template_text)
        if alt_placeholders:
             print(f"Detected {len(alt_placeholders)} angle-bracket placeholders via regex.")
             detected_placeholders.extend(alt_placeholders)
        
        # Deduplicate and clean
        detected_placeholders = list(set([p.strip() for p in detected_placeholders if p.strip()]))


        # 2. Ask LLM to suggest guidance based on the template structure
        prompt = f"""
        TASK: Reverse-engineer this CV Template to suggest professional governance metadata and AI-steering guidance.
        
        TEMPLATE TEXT (EXTRACTED):
        {template_text[:8000]}
        
        IDENTIFIED RAW PLACEHOLDERS:
        {", ".join(detected_placeholders) if detected_placeholders else "None identified programmatically."}

        Analyze the structure, visual hierarchy, expected content, and placeholders in this template. 
        Generate highly specific guidance that will be used to steer other LLMs when they process actual candidate resumes using this template.
        
        CRITICAL INSTRUCTIONS FOR PLACEHOLDERS:
        - If the document uses generic placeholders like '<< Fill this section >>' multiple times, you MUST suggest UNIQUE and DESCRIPTIVE mapping names for each one based on the preceding header.
        - For example, if '<< Fill this section >>' appears under 'Professional Experience', suggest 'experience' as a field name.
        - If it appears under 'Technical Skills', suggest 'skills'.
        - Use snake_case for field names.

        Provide suggestions for the following categories:
        1. 'purpose': A concise description of the ideal profile for this template.
        2. 'expected_sections': A comma-separated string of logical sections (e.g., 'Summary, Experience, Education').
        3. 'expected_fields': A comma-separated string of specific fields or placeholders (e.g., 'summary, skills, experience, projects, education, certifications').
        4. 'summary_guidance': Specific stylistic and content rules for the Executive Summary.
        5. 'formatting_guidance': Rules for data extraction and structural layout.
        6. 'validation_guidance': Semantic quality rules to flag issues.
        7. 'pii_guidance': Specific rules for PII/Privacy redaction.

        OUTPUT FORMAT: Return ONLY a valid JSON object with these keys. No markdown blocks, no preamble.

        """


        
        response = self.llm.generate(prompt)
        try:
            # Clean up potential markdown formatting if LLM ignores instructions
            cleaned_response = response.strip()
            if "```json" in cleaned_response:
                cleaned_response = cleaned_response.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_response:
                cleaned_response = cleaned_response.split("```")[1].strip()
            
            return json.loads(cleaned_response)
        except Exception as e:
            # Fallback to empty suggestions if JSON parsing fails
            print(f"Error during template analysis AI extraction: {e}")
            return {
                "purpose": "General Professional CV Template",
                "expected_sections": "Summary, Experience, Education, Skills",
                "expected_fields": "summary, experience, education, skills",
                "summary_guidance": "Standard professional summary focusing on key achievements.",
                "formatting_guidance": "Clear bullet points and standard date formats (Month YYYY).",
                "pii_guidance": "Redact sensitive personal identification like home address if not required.",
                "validation_guidance": "Ensure all section headers are preserved."
            }

    async def validate_output(self, transformed_data: Dict[str, Any], guidance: str) -> Dict[str, Any]:
        """
        Uses LLM to perform high-level semantic validation of the transformed JSON data.
        """
        prompt = f"""
        TASK: Validate the quality and integrity of this transformed CV data against specific governance rules.
        
        TRANSFORMED DATA (JSON):
        {json.dumps(transformed_data, indent=2)}
        
        GOVERNANCE & QUALITY RULES:
        {guidance or "Check for consistency, date formats, and empty mandatory sections."}
        
        OUTPUT REQUIREMENTS:
        Return a JSON object with:
        - 'status': 'PASS', 'WARN', or 'FAIL'
        - 'errors': List of critical issues
        - 'warnings': List of minor improvements
        - 'confidence_score': 0-100 score of data extraction quality
        
        Return ONLY the JSON object.
        """

        response = self.llm.generate(prompt)
        try:
            cleaned_response = response.strip()
            if "```json" in cleaned_response:
                cleaned_response = cleaned_response.split("```json")[1].split("```")[0].strip()
            return json.loads(cleaned_response)
        except Exception as e:
            print(f"Error during AI output validation: {e}")
            return {"status": "FAIL", "errors": [f"Validation engine failure: {e}"], "warnings": [], "confidence_score": 0}




