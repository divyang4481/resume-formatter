from app.config import settings
from app.schemas.parsed_document import ParsedDocument

class ParseConfidenceService:
    @staticmethod
    def calculate_confidence(parsed_doc: ParsedDocument) -> float:
        """
        Calculates a basic confidence score based on thresholds.
        Returns a float between 0.0 and 1.0.
        """
        score = 1.0
        text_len = len(parsed_doc.text)

        # Text length heuristic
        if text_len == 0:
            return 0.0
        elif text_len < settings.parser_min_text_chars:
            score -= 0.5

        # Structure heuristic (Docling should find sections)
        if len(parsed_doc.sections) < settings.parser_min_section_count:
            score -= 0.3

        return max(0.0, min(1.0, score))
