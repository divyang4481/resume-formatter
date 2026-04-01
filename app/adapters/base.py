from abc import ABC, abstractmethod
from typing import Any, Dict

class DocumentParserAdapter(ABC):
    """
    Abstract Base Class for Document Parsing adapters.
    Ensures that business services do not depend directly on AWS, Azure, GCP, or IBM specifics.
    """

    @abstractmethod
    def parse(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """
        Parse a document and return a normalized representation.

        Args:
            file_path: The local path or URI to the document.
            **kwargs: Additional provider-specific configurations.

        Returns:
            A normalized dictionary of parsed content and metadata.
        """
        pass

class LlmRuntimeAdapter(ABC):
    """
    Abstract Base Class for LLM Runtimes.
    """

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        pass

class PiiDetectorAdapter(ABC):
    """
    Abstract Base Class for PII Detection (e.g., Azure AI Language, GCP DLP, AWS Comprehend).
    """

    @abstractmethod
    def detect_and_mask(self, text: str, policy: str) -> str:
        pass
