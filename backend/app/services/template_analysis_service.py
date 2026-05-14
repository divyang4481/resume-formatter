import logging
import re
from typing import Dict, Any, List

from app.services.template_structure_extractor import TemplateStructureExtractor, FIELD_ALIAS_MAP
from app.adapters.llm.bedrock_template_analyzer import BedrockTemplateAnalyzer
from app.schemas.template_analysis import (
    TemplateAnalysis, 
    TemplateField, 
    RenderLocator, 
    InstructionBlock, 
    StaticBlock,
    TemplateSection
)

logger = logging.getLogger(__name__)

class TemplateAnalysisService:
    """
    Production-ready service for template discovery and semantic mapping.
    Separates deterministic Python extraction from LLM structural reasoning.
    """

    def __init__(self, analyzer: BedrockTemplateAnalyzer = None):
        self.analyzer = analyzer or BedrockTemplateAnalyzer()
        self.extractor = TemplateStructureExtractor()

    async def analyze_template(self, docx_content: bytes, filename: str) -> TemplateAnalysis:
        """Wrapper for backward compatibility with older service interfaces."""
        template_id = filename.replace(".docx", "")
        return await self.analyze_template_asset(docx_content, template_id)

    async def analyze_template_asset(self, docx_content: bytes, template_id: str) -> TemplateAnalysis:
        """
        Performs end-to-end template analysis.
        Input: Raw DOCX bytes.
        Output: Validated TemplateAnalysis Pydantic model.
        """
        logger.info(f"[TemplateAnalysis] Starting analysis for {template_id}")

        # 1. Deterministic Structural Extraction
        structure = self.extractor.extract(docx_content, template_id + ".docx")
        
        # 2. Build context for LLM reasoning
        full_context = self._assemble_context(structure)
        
        # 3. LLM Reasoning Pass (Claude 3.5 Sonnet)
        from app.agent.prompt_manager import prompt_manager
        
        prompt = prompt_manager.get_prompt(
            "template_analysis.jinja2",
            template_text=full_context,
            detected_placeholders=structure.detected_markers,
            field_taxonomy=FIELD_ALIAS_MAP # Pass the taxonomy for semantic alignment
        )
        
        analysis = self.analyzer.analyze_template(prompt, TemplateAnalysis)
        analysis.template_id = template_id
        analysis.raw_structure = structure.to_dict()

        # 4. Deterministic Reconciliation (Healing Typos/Wrappings)
        self._reconcile_and_enrich(analysis, structure)

        logger.info(f"[TemplateAnalysis] Successfully analyzed {template_id}. Found {len(analysis.fields)} fields.")
        return analysis

    def _assemble_context(self, structure) -> str:
        """Flattens the detected structure into a readable block for the LLM."""
        blocks = []
        
        blocks.append(f"LAYOUT_STYLE: {structure.layout_style}")
        blocks.append(f"DETECTED_MARKERS: {structure.detected_markers}")
        
        if structure.table_label_value_pairs:
            blocks.append("\n[TABLE LABEL-VALUE PAIRS]")
            for slot in structure.table_label_value_pairs:
                blocks.append(f"  Label: '{slot.label}' | Marker/Value: '{slot.marker_text}' | IsBlank: {slot.is_blank}")
        
        if hasattr(structure, 'table_loops') and structure.table_loops:
            blocks.append("\n[DYNAMIC TABLE LOOPS]")
            for loop in structure.table_loops:
                blocks.append(f"  LoopName: '{loop.loop_name}' | Fields: {loop.item_fields}")

        if hasattr(structure, 'heading_to_loop') and structure.heading_to_loop:
            blocks.append("\n[HEADING -> LOOP MAPPINGS]")
            for h, l in structure.heading_to_loop.items():
                blocks.append(f"  Heading: '{h}' -> Loop: '{l}'")

        if hasattr(structure, 'heading_to_smart_pattern') and structure.heading_to_smart_pattern:
            blocks.append("\n[SMART OBJECT BLUEPRINTS (Visual Patterns)]")
            for h, patterns in structure.heading_to_smart_pattern.items():
                blocks.append(f"  Heading: '{h}' | Patterns: {patterns}")

        if structure.instruction_blocks:
            blocks.append("\n[INSTRUCTION BLOCKS (Red/Italic/Quoted)]")
            for inst in structure.instruction_blocks:
                blocks.append(f"  - '{inst[:300]}'")
                
        if structure.all_headings:
            blocks.append(f"\n[DOCUMENT HEADINGS]\n{structure.all_headings}")
            
        return "\n".join(blocks)

    def _reconcile_and_enrich(self, analysis: TemplateAnalysis, structure):
        """
        Hardens the LLM output against hallucinations and normalization issues.
        Ensures markers in the manifest exactly match markers found in XML.
        """
        detected_norm = {self._norm(m): m for m in structure.detected_markers}
        
        # Flattened list for convenience
        all_fields = []
        for section in analysis.sections:
            all_fields.extend(section.fields)
        
        # If LLM returned a flat 'fields' list, use that too
        all_fields.extend(analysis.fields)

        used_markers = set()

        for field in all_fields:
            m_text = field.marker_text.strip()
            if not m_text:
                continue
                
            # Typos/Wrapping Healing
            norm_m = self._norm(m_text)
            if m_text not in structure.detected_markers and norm_m in detected_norm:
                actual = detected_norm[norm_m]
                logger.info(f"[Reconcile] Healed marker typo: '{m_text}' -> '{actual}'")
                field.marker_text = actual
                field.render_locator.marker_text = actual
                
            used_markers.add(field.marker_text)

        # Ensure instructions from structure are present
        for inst in structure.instruction_blocks:
            if not any(i.text in inst for i in analysis.instruction_blocks):
                analysis.instruction_blocks.append(InstructionBlock(
                    text=inst,
                    action="remove_or_replace",
                    meaning="Detected structural instruction"
                ))

    def _norm(self, text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", text.lower())
