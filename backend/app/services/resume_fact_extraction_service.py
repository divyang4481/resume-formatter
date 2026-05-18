import logging
from typing import Optional, Any

from app.adapters.llm.bedrock_template_analyzer import BedrockTemplateAnalyzer
from app.schemas.template_analysis import CandidateFacts
# Docling extraction would happen here or be passed in
from app.services.template_structure_extractor import TemplateStructureExtractor

logger = logging.getLogger(__name__)

class ResumeFactExtractionService:
    """
    Runtime service to extract structured facts from a candidate resume.
    Uses Bedrock (Haiku) for high-speed, cost-effective extraction.
    """

    def __init__(self, analyzer: BedrockTemplateAnalyzer = None):
        self.analyzer = analyzer or BedrockTemplateAnalyzer()

    async def extract_candidate_facts(self, resume_text: str, analysis: Optional[Any] = None) -> CandidateFacts:
        """
        Converts raw resume text into a canonical CandidateFacts model.
        Accepts optional TemplateAnalysis to guide the extraction process.
        """
        logger.info("[ResumeFacts] Extracting facts from resume text")

        from app.agent.prompt_manager import prompt_manager
        
        # Build hints from the template analysis
        hints = []
        if analysis:
            all_fields = list(analysis.fields)
            for s in analysis.sections: all_fields.extend(s.fields)
            for f in all_fields:
                if f.field_name.startswith("_instruction_") or getattr(f, "source_kind", "resume_fact") != "resume_fact":
                    continue
                extraction_hints = getattr(f, "extraction_hints", {}) or {}
                source_hints = getattr(f, "source_hints", "") or ""
                hints.append(
                    f"- {f.field_name} ({getattr(f, 'field_type', 'scalar')}): {f.meaning}; "
                    f"source_hints={source_hints}; extraction_hints={extraction_hints}"
                )
        
        prompt = prompt_manager.get_prompt(
            "resume_fact_extraction.jinja2",
            resume_text=resume_text[:20000],
            template_field_hints="\n".join(hints) if hints else "No specific template hints provided."
        )

        facts = self.analyzer.extract_facts(prompt, CandidateFacts)
        
        logger.info(f"[ResumeFacts] Successfully extracted facts for {facts.full_name}")
        return facts
