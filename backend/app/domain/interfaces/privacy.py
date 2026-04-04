from abc import ABC, abstractmethod

class PiiDetectorAdapter(ABC):
    """
    Abstract Base Class for PII Detection (e.g., Azure AI Language, GCP DLP, AWS Comprehend).
    """

    @abstractmethod
    def detect_and_mask(self, text: str, policy: str) -> str:
        """
        Detects PII entities in the content and applies a masking policy.
        """
        pass
