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

    @abstractmethod
    def generate_template_contract(
        self,
        *,
        template_text: str,
        template_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyzes template text and generates a structured contract/schema."""
        pass

    @abstractmethod
    def evaluate_output_quality(
        self,
        *,
        mapped_data: Dict[str, Any],
        template_contract: Dict[str, Any],
        job_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluates mapping quality, reasoning about missing fields or formatting issues."""
        pass
