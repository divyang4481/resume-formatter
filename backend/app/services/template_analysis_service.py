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
            return await self.ai_service.analyze_template(file_bytes, filename)
        except Exception as e:
            print(f"Template analysis delegation failed: {e}")
            raise e

