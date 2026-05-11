import json
import logging
import os
import re
import zipfile
import lxml.etree as ET
from typing import Dict, List, Any

from app.config import settings
from app.agent.prompt_manager import prompt_manager
from app.agent.utils.llm_sanitizer import LlmSanitizer

logger = logging.getLogger(__name__)

class ResumeAiService:
    def __init__(self, llm_adapter, extraction_service=None):
        self.llm = llm_adapter
        self.extraction_service = extraction_service

    async def generate_summary(self, extracted_text: str, guidance: str = "", industry: str = None, language: str = "en") -> str:
        """Restored method for worker nodes to generate professional summaries."""
        prompt = f"Summarize the following professional experience into 3 punchy bullet points. Language: {language}. Industry: {industry}.\nGuidance: {guidance}\n\n{extracted_text[:10000]}"
        summary = self.llm.generate(prompt)
        return summary.strip()

    async def summarize_experience(self, experience_text: str) -> str:
        """Alias for short-form summarization."""
        return await self.generate_summary(experience_text)

    def _get_docx_placeholders_from_xml(self, content: bytes) -> List[str]:
        """Deep-scans DOCX XML for hidden Merge Fields (w:fldSimple, w:instrText)."""
        placeholders = []
        try:
            import io
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                if 'word/document.xml' in z.namelist():
                    xml_content = z.read('word/document.xml')
                    root = ET.fromstring(xml_content)
                    
                    # 1. Look for Simple Fields (w:fldSimple)
                    for fld in root.xpath("//w:fldSimple", namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}):
                        instr = fld.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}instr")
                        if instr and "MERGEFIELD" in instr:
                            parts = instr.split()
                            if len(parts) >= 2:
                                placeholders.append(parts[parts.index("MERGEFIELD") + 1])
                    
                    # 2. Look for Complex Fields (w:instrText)
                    for instr_text in root.xpath("//w:instrText", namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}):
                        text = instr_text.text
                        if text and "MERGEFIELD" in text:
                            parts = text.split()
                            if len(parts) >= 2:
                                placeholders.append(parts[parts.index("MERGEFIELD") + 1])
                                
                    # 3. Raw regex on XML
                    raw_xml = xml_content.decode('utf-8', errors='ignore')
                    extra_matches = re.findall(r"&#171;(.*?)&#187;", raw_xml)
                    placeholders.extend(extra_matches)
                    extra_matches_raw = re.findall(r"«(.*?)»", raw_xml)
                    placeholders.extend(extra_matches_raw)
        except Exception as e:
            logger.error(f"Error deep-scanning docx XML: {e}")
            
        return list(set([p.strip() for p in placeholders if p.strip()]))

    async def analyze_template(self, content: bytes, filename: str) -> Dict[str, str]:
        """Analyzes a .docx template to suggest metadata... (Uses Context Injection)"""
        if not self.extraction_service: return {}
        
        extracted_doc = await self.extraction_service.extract(
            content, filename, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        text_content = extracted_doc.extracted_text
        
        # 1. Gather all placeholders
        xml_placeholders = []
        if filename.lower().endswith(".docx"):
            xml_placeholders = self._get_docx_placeholders_from_xml(content)
            logger.info(f"Deep XML Scan found: {xml_placeholders}")
            
        regex_patterns = [
            r"<<\s*(.*?)\s*>>",
            r"\{\{\s*(.*?)\s*\}\}",
            r"\[\[\s*(.*?)\s*\]\]",
            r"«\s*(.*?)\s*»",
            r"\[\s*([^\]\s].*?)\s*\]"
        ]
        
        detected_raw = []
        for pattern in regex_patterns:
            matches = re.findall(pattern, text_content)
            detected_raw.extend(matches)
        detected_raw.extend(xml_placeholders)
        
        seen = set()
        detected_placeholders = [p.strip() for p in detected_raw if p.strip() and not (p.strip() in seen or seen.add(p.strip()))]
        
        # 2. CONTEXT INJECTION
        missing_from_text = [p for p in xml_placeholders if p not in text_content and f"«{p}»" not in text_content]
        if missing_from_text:
            injection_header = "\n[SYSTEM: HIDDEN METADATA MARKERS DETECTED AT TOP OF DOCUMENT]\n"
            for p in missing_from_text:
                injection_header += f"Marker: «{p}» (Location: Header/Metadata/HiddenField)\n"
            injection_header += "[END HIDDEN METADATA]\n\n"
            text_content = injection_header + text_content

        # 3. LLM Analysis
        prompt = prompt_manager.get_prompt(
            "template_analysis.jinja2",
            template_text=text_content[:8000],
            docling_metadata_json=json.dumps(extracted_doc.structured_data, indent=2)[:4000] if extracted_doc.structured_data else "None",
            detected_placeholders=detected_placeholders,
        )

        response = self.llm.generate(prompt)
        
        try:
            cleaned_json = LlmSanitizer.clean_json(response)
            data = json.loads(cleaned_json)
        except Exception as e:
            logger.error(f"Failed to parse template analysis JSON: {e}")
            data = {}

        manifest = data.get("field_extraction_manifest", [])
        if not isinstance(manifest, list): manifest = []

        # 4. Final Reconciliation
        manifest_markers = [str(m.get("marker_text", "")) for m in manifest]
        for p in detected_placeholders:
            found = False
            for m in manifest_markers:
                if p in m:
                    found = True
                    break
            
            if not found:
                logger.warning(f"AI STILL missed placeholder '{p}'. Using fallback.")
                clean_name = re.sub(r'[^a-z0-9]', '_', p.lower()).strip('_')
                if not clean_name: clean_name = f"field_{p}"
                manifest.insert(0, {
                    "fieldname": clean_name,
                    "marker_text": f"«{p}»",
                    "visual_context": "Automatically identified at document level",
                    "meaning": f"Metadata placeholder for {p}",
                    "source_hints": clean_name.replace('_', ' ')
                })

        fields = [m.get("fieldname") for m in manifest if m.get("fieldname")]
        expected_fields = ", ".join(fields)

        return {
            "purpose": data.get("purpose") or "General Template",
            "expected_sections": data.get("expected_sections") or "Summary, Experience",
            "expected_fields": expected_fields,
            "summary_guidance": data.get("summary_guidance") or "",
            "formatting_guidance": data.get("formatting_guidance") or "",
            "field_extraction_manifest": manifest
        }

    async def harmonize_data_to_template_style(self, structured_data: Dict[str, Any], template_text: str, detected_placeholders: List[str], field_manifest: List[Dict[str, Any]], formatting_guidance: str = "") -> Dict[str, Any]:
        """Restored method to map resume data to the template contract."""
        
        prompt = prompt_manager.get_prompt(
            "data_linearization.jinja2",
            structured_data_json=json.dumps(structured_data, indent=2),
            field_extraction_manifest=field_manifest,
            detected_placeholders_list=detected_placeholders,
            formatting_guidance=formatting_guidance,
            template_text=template_text[:4000]
        )
        
        response = self.llm.generate(prompt)
        
        try:
            cleaned_json = LlmSanitizer.clean_json(response)
            data = json.loads(cleaned_json)
            return data
        except Exception as e:
            logger.error(f"Failed to parse harmonized data JSON: {e}")
            # Fallback: Return raw data if AI fails
            return structured_data

    async def linearize_data(self, structured_data: Dict[str, Any], template_metadata: Dict[str, Any]) -> str:
        """Linearizes structured resume data into a narrative format (Legacy support)."""
        result = await self.harmonize_data_to_template_style(
            structured_data=structured_data,
            template_text="",
            detected_placeholders=template_metadata.get("expected_fields", "").split(", "),
            field_manifest=template_metadata.get("field_extraction_manifest", [])
        )
        return json.dumps(result)
