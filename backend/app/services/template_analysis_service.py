from typing import Dict, Any, Optional
from app.services.resume_ai_service import ResumeAiService

class TemplateAnalysisService:
    def __init__(self, ai_service: ResumeAiService):
        self.ai_service = ai_service

    async def analyze_template(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Delegates the AI analysis logic to the centralized ResumeAiService.
        """
        try:
            result = await self.ai_service.analyze_template_metadata(file_bytes, filename)
            return result.model_dump()
        except Exception as e:
            print(f"Template analysis delegation failed: {e}")
            return {
                "purpose": "General Professional Template",
                "expected_sections": "Summary, Experience, Education, Skills",
                "global_guidance": "Standard executive summary focusing on career progression. Clear, bulleted lists and consistent date formatting (Jan 2024).",
                "field_extraction_manifest": []
            }

