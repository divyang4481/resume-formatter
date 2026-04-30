from abc import ABC, abstractmethod
from typing import Dict, Any

class ResumeFormattingAgent(ABC):
    @abstractmethod
    def map_resume_to_template(
        self,
        *,
        parsed_resume: Dict[str, Any],
        template_contract: Dict[str, Any],
        template_rules: Dict[str, Any],
        pii_policy: Dict[str, Any],
        job_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Maps parsed resume data to the structured schema required by the template."""
        pass
