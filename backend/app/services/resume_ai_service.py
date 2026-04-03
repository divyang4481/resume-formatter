from typing import Dict, Any, Optional, List
import json
import logging
from app.domain.interfaces import DocumentExtractionService
from app.adapters.base import LlmRuntimeAdapter

logger = logging.getLogger(__name__)

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
        
        logger.info("Sending prompt to LLM for summary generation.")
        logger.debug(f"Prompt content:\n{prompt}")

        response = self.llm.generate(prompt)

        logger.info("Received response from LLM for summary generation.")
        logger.debug(f"LLM Response:\n{response}")

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
        logger.info(f"Extracted template text length: {len(template_text)}")
        logger.debug(f"Extracted template text excerpt:\n{template_text[:1000]}")

        # 1.5 Extract placeholders programmatically if it's a docx
        detected_placeholders = []
        try:
            from docxtpl import DocxTemplate
            import io
            doc = DocxTemplate(io.BytesIO(content))
            detected_placeholders = list(doc.get_undeclared_template_variables())
            logger.info(f"Programmatically detected {len(detected_placeholders)} Jinja2 placeholders in template.")
        except Exception as e:
            logger.warning(f"Warning: Failed to extract Jinja2 placeholders: {e}")

        # 1.6 Additional regex for alternative placeholders (e.g. << Field Name >>)
        import re
        alt_placeholders = re.findall(r'<<\s*(.*?)\s*>>', template_text)
        if alt_placeholders:
             logger.info(f"Detected {len(alt_placeholders)} angle-bracket placeholders via regex.")
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

        logger.info("Sending prompt to LLM for template analysis.")
        logger.debug(f"Prompt content:\n{prompt}")
        
        response = self.llm.generate(prompt)

        logger.info("Received response from LLM for template analysis.")
        logger.debug(f"LLM Response:\n{response}")

        try:
            # Robust JSON cleaning
            cleaned = response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()
            
            # Find the actual JSON markers to ignore preamble/epilogue
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                cleaned = cleaned[start:end+1]
            
            return json.loads(cleaned)
        except Exception as e:
            # Fallback to empty suggestions if JSON parsing fails
            logger.error(f"Error during template analysis AI extraction: {e}", exc_info=True)
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

        logger.info("Sending prompt to LLM for output validation.")
        logger.debug(f"Prompt content:\n{prompt}")

        response = self.llm.generate(prompt)

        logger.info("Received response from LLM for output validation.")
        logger.debug(f"LLM Response:\n{response}")

        try:
            # Robust JSON cleaning
            cleaned = response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()
            
            # Find the actual JSON markers to ignore preamble/epilogue
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                cleaned = cleaned[start:end+1]
            
            if not cleaned:
                raise ValueError("LLM returned empty or non-JSON validation result")

            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"Error during AI output validation: {e}", exc_info=True)
            return {"status": "FAIL", "errors": [f"Validation engine failure: {e}"], "warnings": [], "confidence_score": 0}

    async def format_data_for_template(
        self, 
        structured_data: Dict[str, Any], 
        template_text: str,
        formatting_guidance: str = ""
    ) -> Dict[str, str]:
        """
        Uses LLM to transform structured JSON data into strings that perfectly match
        the visual style and whitespace requirements of the target template.
        """
        prompt = f"""
        TASK: Linearize structured CV data into formatted strings for a Word (.docx) template.
        
        INPUT DATA (JSON):
        {json.dumps(structured_data, indent=2)}
        
        TEMPLATE CONTEXT (Excerpts):
        {template_text[:4000]}
        
        FORMATTING GUIDANCE FROM TEMPLATE:
        {formatting_guidance}
        
        INSTRUCTIONS:
        1. For each key in the JSON, generate a single string that represents that data formatted correctly for the CV.
        2. Use professional bulleting (e.g., '•' or '-') for lists.
        3. Maintain chronological order (newest first) for experience and education.
        4. If a key is an object or list, transform it into a readable text block.
        5. Ensure date formats are consistent (e.g., 'Jan 2020 - Present').
        6. Do NOT include any markdown formatting (like **bold**) as this is for a plain text insertion into Word.
        7. If the field is already a simple string, clean it up but keep the meaning.
        
        OUTPUT FORMAT: Return ONLY a valid JSON object where keys match the input keys and values are the formatted strings.
        """

        logger.info("Sending prompt to LLM for template-aware data formatting.")
        try:
            response = self.llm.generate(prompt)
            
            # Use robust cleaning
            cleaned = response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()
            
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                cleaned = cleaned[start:end+1]
            
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"Failed to linearize data for template: {e}")
            # Fallback to simple string representations to avoid crash
            return {k: str(v) for k, v in structured_data.items()}





