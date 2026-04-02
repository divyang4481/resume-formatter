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
        if parsed_doc.parser_used == "docling":
            if len(parsed_doc.sections) < settings.parser_min_section_count:
                score -= 0.3

            # If docling didn't extract any tables, we don't penalize heavily,
            # but we could add a minor penalty if we expected a complex document.

        # Tika heuristic (Tika doesn't find sections, so we only judge on text length)
        elif parsed_doc.parser_used == "tika":
            # Tika is naturally lower confidence for structure,
            # so we might cap its max confidence
            score = min(score, 0.8)

        return max(0.0, min(1.0, score))
