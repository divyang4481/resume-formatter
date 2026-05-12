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

    async def generate_summary(
        self,
        extracted_text: str,
        guidance: str = "",
        industry: str = None,
        language: str = "en",
    ) -> str:
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
                if "word/document.xml" in z.namelist():
                    xml_content = z.read("word/document.xml")
                    root = ET.fromstring(xml_content)

                    # 1. Look for Simple Fields (w:fldSimple)
                    for fld in root.xpath(
                        "//w:fldSimple",
                        namespaces={
                            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                        },
                    ):
                        instr = fld.get(
                            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}instr"
                        )
                        if instr and "MERGEFIELD" in instr:
                            parts = instr.split()
                            if len(parts) >= 2:
                                placeholders.append(
                                    parts[parts.index("MERGEFIELD") + 1]
                                )

                    # 2. Look for Complex Fields (w:instrText)
                    for instr_text in root.xpath(
                        "//w:instrText",
                        namespaces={
                            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                        },
                    ):
                        text = instr_text.text
                        if text and "MERGEFIELD" in text:
                            parts = text.split()
                            if len(parts) >= 2:
                                placeholders.append(
                                    parts[parts.index("MERGEFIELD") + 1]
                                )

                    # 3. Raw regex on XML with broader entity support
                    raw_xml = xml_content.decode("utf-8", errors="ignore")
                    # Match various forms of « and » (including entities and raw bytes)
                    entity_patterns = [
                        r"&#171;(.*?)&#187;",
                        r"&laquo;(.*?)&raquo;",
                        r"«(.*?)»",
                        r"\[\s*(.*?)\s*\]" # Also look for bracketed placeholders in XML
                    ]
                    for pat in entity_patterns:
                        matches = re.findall(pat, raw_xml)
                        placeholders.extend(matches)
        except Exception as e:
            logger.error(f"Error deep-scanning docx XML: {e}")

        return list(set([p.strip() for p in placeholders if p.strip()]))

    async def analyze_template(self, content: bytes, filename: str) -> Dict[str, str]:
        """Analyzes a .docx template to suggest metadata... (Uses Context Injection)"""
        if not self.extraction_service:
            return {}

        extracted_doc = await self.extraction_service.extract(
            content,
            filename,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
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
            r"\[\s*([^\]\s].*?)\s*\]",
        ]

        detected_raw = []
        for pattern in regex_patterns:
            matches = re.findall(pattern, text_content)
            detected_raw.extend(matches)
        detected_raw.extend(xml_placeholders)

        seen = set()
        detected_placeholders = [
            p.strip()
            for p in detected_raw
            if p.strip() and not (p.strip() in seen or seen.add(p.strip()))
        ]

        # 2. CONTEXT INJECTION
        missing_from_text = [
            p
            for p in xml_placeholders
            if p not in text_content and f"«{p}»" not in text_content
        ]
        if missing_from_text:
            injection_header = (
                "\n[SYSTEM: HIDDEN METADATA MARKERS DETECTED AT TOP OF DOCUMENT]\n"
            )
            for p in missing_from_text:
                injection_header += (
                    f"Marker: «{p}» (Location: Header/Metadata/HiddenField)\n"
                )
            injection_header += "[END HIDDEN METADATA]\n\n"
            text_content = injection_header + text_content

        # 2b. Extract Tables for Visual Context
        table_context = ""
        if extracted_doc.structured_data and "items" in extracted_doc.structured_data:
            tables = [item for item in extracted_doc.structured_data["items"] if item.get("role") == "table"]
            if tables:
                table_context = "\n[STRUCTURED TABLES DETECTED]\n"
                for i, table in enumerate(tables):
                    table_context += f"\nTable {i+1}:\n"
                    # Simple MD-like representation of the table cells
                    if "cells" in table:
                        rows = {}
                        for cell in table["cells"]:
                            r = cell.get("row_index", 0)
                            c = cell.get("column_index", 0)
                            txt = cell.get("text", "").strip()
                            if r not in rows: rows[r] = {}
                            rows[r][c] = txt
                        
                        for r_idx in sorted(rows.keys()):
                            row_vals = [rows[r_idx].get(c_idx, "") for c_idx in sorted(rows[r_idx].keys())]
                            table_context += "| " + " | ".join(row_vals) + " |\n"
                table_context += "[END TABLES]\n"

        # 3. LLM Analysis - Simplified to single text source and markers
        prompt = prompt_manager.get_prompt(
            "template_analysis.jinja2",
            template_text=text_content[:10000], # Provide more text context in a single block
            detected_placeholders=detected_placeholders,
        )

        logger.info("\n" + "="*60 + "\n--- TEMPLATE ANALYSIS PROMPT ---\n" + "="*60)
        logger.info(prompt)
        logger.info("="*60 + "\n")

        response = self.llm.generate(prompt)
        
        logger.info("\n" + "="*60 + "\n--- TEMPLATE ANALYSIS LLM RESPONSE ---\n" + "="*60)
        logger.info(response)
        logger.info("="*60 + "\n")

        try:
            cleaned_json = LlmSanitizer.clean_json(response)
            data = json.loads(cleaned_json)
        except Exception as e:
            logger.error(f"Failed to parse template analysis JSON: {e}")
            data = {}
            
        manifest = data.get("field_extraction_manifest", [])
        if not isinstance(manifest, list): manifest = []

        # --- AI HEALING: Prevent empty marker_text for critical fields ---
        for m in manifest:
            if not m.get("marker_text") and m.get("fieldname") == "candidate_name":
                # Look for something that looks like 'FullName' or 'Candidate' in detected placeholders
                for p in detected_placeholders:
                    if "name" in p.lower() or "candidate" in p.lower():
                        m["marker_text"] = f"«{p}»" if "«" not in p else p
                        logger.info(f"HEALED: Assigned '{m['marker_text']}' to candidate_name")
                        break
                if not m.get("marker_text") and detected_placeholders:
                    # Absolute fallback: first detected placeholder
                    m["marker_text"] = detected_placeholders[0]
                    logger.info(f"FALLBACK HEALED: Assigned '{m['marker_text']}' to candidate_name")

        # 4. Final Reconciliation & Hallucination Guard
        manifest_markers = [str(m.get("marker_text", "")) for m in manifest if m.get("marker_text")]
        
        # --- HALLUCINATION GUARD: Check for repetitive markers ---
        if len(manifest_markers) > 3:
            from collections import Counter
            counts = Counter(manifest_markers)
            most_common, count = counts.most_common(1)[0]
            if count / len(manifest_markers) > 0.6:
                logger.error(f"HALLUCINATION DETECTED: Marker '{most_common}' repeated {count} times. Rejecting manifest.")
                # Force a partial cleanup: remove the hallucinated markers from fields that clearly don't match
                for m in manifest:
                    if m.get("marker_text") == most_common and most_common.lower().strip("«»") not in m.get("fieldname", "").lower():
                        if "email" not in m.get("fieldname", "").lower():
                            m["marker_text"] = "" 
                            logger.info(f"Cleaned hallucinated marker from {m.get('fieldname')}")

        for p in detected_placeholders:
            found = False
            for m in manifest_markers:
                if p in m:
                    found = True
                    break

            if not found:
                logger.warning(f"AI STILL missed placeholder '{p}'. Using fallback.")
                clean_name = re.sub(r"[^a-z0-9]", "_", p.lower()).strip("_")
                if not clean_name:
                    clean_name = f"field_{p}"
                manifest.insert(
                    0,
                    {
                        "fieldname": clean_name,
                        "marker_text": f"«{p}»",
                        "visual_context": "Automatically identified at document level",
                        "meaning": f"Metadata placeholder for {p}",
                        "source_hints": clean_name.replace("_", " "),
                    },
                )

        fields = [m.get("fieldname") for m in manifest if m.get("fieldname")]
        expected_fields = ", ".join(fields)

        return {
            "purpose": data.get("purpose") or "General Template",
            "expected_sections": data.get("expected_sections") or "Summary, Experience",
            "expected_fields": expected_fields,
            "summary_guidance": data.get("summary_guidance") or "",
            "formatting_guidance": data.get("formatting_guidance") or "",
            "field_extraction_manifest": manifest,
        }

    async def harmonize_data_to_template_style(
        self,
        structured_data: Dict[str, Any],
        template_text: str,
        detected_placeholders: List[str],
        field_manifest: List[Dict[str, Any]],
        formatting_guidance: str = "",
        job_id: str = "N/A",
    ) -> Dict[str, Any]:
        """Restored method to map resume data to the template contract."""

        prompt = prompt_manager.get_prompt(
            "data_linearization.jinja2",
            structured_data_json=json.dumps(structured_data, indent=2),
            field_extraction_manifest=field_manifest,
            detected_placeholders_list=detected_placeholders,
            formatting_guidance=formatting_guidance,
            template_text=template_text[:4000],
            job_id=job_id,
        )

        logger.info(
            "\n" + "=" * 60 + "\n--- DATA LINEARIZATION PROMPT ---\n" + "=" * 60
        )
        logger.info(prompt)
        logger.info("=" * 60 + "\n")

        response = self.llm.generate(prompt)

        logger.info(
            "\n" + "=" * 60 + "\n--- DATA LINEARIZATION LLM RESPONSE ---\n" + "=" * 60
        )
        logger.info(response)
        logger.info("=" * 60 + "\n")

        try:
            cleaned_json = LlmSanitizer.clean_json(response)
            logger.info("\n" + "=" * 60 + "\n--- CLEANED JSON ---\n" + "=" * 60)
            logger.info(cleaned_json)
            logger.info("=" * 60 + "\n")
            data = json.loads(cleaned_json)

            logger.info(
                "\n" + "=" * 60 + "\n--- FINAL HARMONIZED DATA ---\n" + "=" * 60
            )
            logger.info(data)
            logger.info("=" * 60 + "\n")

            return data
        except Exception as e:
            logger.error(f"Failed to parse harmonized data JSON: {e}")
            # Fallback: Return raw data if AI fails
            return structured_data

    async def apply_composition_logic(self, harmonized_data: Dict[str, Any], template_text: str, manifest: List[Dict[str, Any]] = None, formatting_guidance: str = "") -> Dict[str, Any]:
        """Performs a secondary formatting and professional phrasing pass."""
        
        prompt = prompt_manager.get_prompt(
            "composition_logic.jinja2",
            harmonized_json=json.dumps(harmonized_data, indent=2),
            manifest_json=json.dumps(manifest, indent=2) if manifest else "None",
            formatting_guidance=formatting_guidance,
            template_text=template_text[:3000]
        )
        
        logger.info("\n" + "="*60 + "\n--- COMPOSITION LOGIC PROMPT ---\n" + "="*60)
        logger.info(prompt)
        logger.info("="*60 + "\n")
        
        response = self.llm.generate(prompt)
        
        logger.info("\n" + "="*60 + "\n--- COMPOSITION LOGIC LLM RESPONSE ---\n" + "="*60)
        logger.info(response)
        logger.info("="*60 + "\n")
        
        try:
            cleaned_json = LlmSanitizer.clean_json(response)
            data = json.loads(cleaned_json)
            return data
        except Exception as e:
            logger.error(f"Failed to parse composition logic JSON: {e}")
            return harmonized_data

    async def linearize_data(
        self, structured_data: Dict[str, Any], template_metadata: Dict[str, Any]
    ) -> str:
        """Linearizes structured resume data into a narrative format (Legacy support)."""
        result = await self.harmonize_data_to_template_style(
            structured_data=structured_data,
            template_text="",
            detected_placeholders=template_metadata.get("expected_fields", "").split(
                ", "
            ),
            field_manifest=template_metadata.get("field_extraction_manifest", []),
        )
        return json.dumps(result)
