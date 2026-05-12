import logging
from typing import Dict, Any, List

from app.schemas.template_analysis import CandidateFacts, TemplateAnalysis, TemplateFillPlan
from app.adapters.llm.bedrock_template_analyzer import BedrockTemplateAnalyzer

logger = logging.getLogger(__name__)

class TemplateFieldMapper:
    """
    Logic layer that aligns extracted candidate facts with a specific template schema.
    Produces a deterministic TemplateFillPlan for the renderer.
    """

    def __init__(self, analyzer: BedrockTemplateAnalyzer = None):
        self.analyzer = analyzer or BedrockTemplateAnalyzer()

    async def generate_fill_plan(
        self, 
        facts: CandidateFacts, 
        analysis: TemplateAnalysis, 
        recruiter_input: Dict[str, Any] = None
    ) -> TemplateFillPlan:
        """
        Maps facts to template fields using a semantic alignment pass.
        """
        logger.info(f"[FieldMapper] Generating fill plan for template {analysis.template_id}")

        # 1. Prepare inputs for semantic mapping
        recruiter_data = recruiter_input or {}
        
        # Flatten all fields from the analysis
        template_fields = []
        for section in analysis.sections:
            for field in section.fields:
                template_fields.append({
                    "field_name": field.field_name,
                    "meaning": field.meaning,
                    "source_kind": field.source_kind,
                    "required": field.required
                })
        # Add legacy flat fields
        for field in analysis.fields:
             template_fields.append({
                    "field_name": field.field_name,
                    "meaning": field.meaning,
                    "source_kind": field.source_kind,
                    "required": field.required
                })

        # 2. Use Bedrock to perform the semantic mapping (CandidateFacts -> Template Fields)
        from app.agent.prompt_manager import prompt_manager
        
        prompt = prompt_manager.get_prompt(
            "template_field_mapping.jinja2",
            facts_json=facts.model_dump_json(indent=2),
            recruiter_input=recruiter_data,
            template_fields=template_fields
        )

        # We reuse the analyzer's generic extraction capability
        mapped_data = self.analyzer.runtime.generate(
            prompt,
            system_prompt="You are a data alignment engine. Map source facts to target template fields precisely.",
            task_name="data_mapping",
            temperature=0.0
        )
        
        try:
            import json
            from app.agent.utils.llm_sanitizer import LlmSanitizer
            cleaned = LlmSanitizer.clean_json(mapped_data)
            data_dict = json.loads(cleaned)
        except Exception as e:
            logger.error(f"[FieldMapper] Failed to parse mapping JSON: {e}")
            data_dict = {}

        # 3. Assemble the Fill Plan
        plan = TemplateFillPlan(
            template_id=analysis.template_id,
            fields=data_dict,
            instructions_to_clear=[ib.text for ib in analysis.instruction_blocks],
            metadata={
                "candidate_name": facts.full_name,
                "mapping_confidence": 0.9 # placeholder
            }
        )

        return plan
