import time
from typing import Any, Dict, Optional, Tuple
from app.config import settings
from app.domain.interfaces.document_parser import DocumentParser
from app.schemas.parsed_document import ParsedDocument
from app.schemas.parser_events import ParseResultTrace, ParserAttempt
from app.adapters.parsers.docling_parser import DoclingParser
from app.adapters.parsers.tika_parser import TikaParser
from app.adapters.parsers.azure_document_intelligence_parser import AzureDocumentIntelligenceParser

class ParserRouter:
    def __init__(self):
        # In a real app, these would be injected via dependency injection
        self.parsers: Dict[str, DocumentParser] = {
            "docling": DoclingParser(),
            "tika": TikaParser(),
            "azure_document_intelligence": AzureDocumentIntelligenceParser()
        }

    def _get_parsers_for_file(self, extension: str) -> Tuple[str, str]:
        ext = extension.lower()
        if ext == ".pdf":
            return settings.document_parser_primary_pdf, settings.document_parser_fallback_pdf
        elif ext in [".docx", ".doc"]:
            return settings.document_parser_primary_docx, settings.document_parser_fallback_docx
        else:
            # Default to tika for unsupported/other formats as a fallback safety
            return "tika", "tika"

    async def route_and_parse(self, file_bytes: bytes, file_name: str, mime_type: str, file_id: str) -> Tuple[ParsedDocument, ParseResultTrace]:
        from app.services.parse_confidence_service import ParseConfidenceService
        import os
        ext = os.path.splitext(file_name)[1]
        primary_name, fallback_name = self._get_parsers_for_file(ext)

        trace = ParseResultTrace(
            file_id=file_id,
            mime_type=mime_type,
            primary_parser_attempted=primary_name,
            fallback_parser_attempted=fallback_name,
            final_parser_used=primary_name,
            total_duration_seconds=0.0
        )

        start_time = time.time()

        primary_parser = self.parsers.get(primary_name)
        if not primary_parser:
            raise ValueError(f"Primary parser {primary_name} not found")

        parsed_doc = None
        confidence = 0.0
        primary_success = False

        attempt_start = time.time()
        try:
            parsed_doc = await primary_parser.parse(file_bytes, file_name, mime_type)
            confidence = ParseConfidenceService.calculate_confidence(parsed_doc)
            parsed_doc.confidence = confidence
            primary_success = confidence >= settings.parser_min_confidence

            trace.attempts.append(ParserAttempt(
                parser_name=primary_name,
                success=primary_success,
                confidence=confidence,
                duration_seconds=time.time() - attempt_start,
                extracted_char_count=len(parsed_doc.text),
                section_count=len(parsed_doc.sections)
            ))

        except Exception as e:
            trace.attempts.append(ParserAttempt(
                parser_name=primary_name,
                success=False,
                duration_seconds=time.time() - attempt_start,
                error_message=str(e)
            ))

        # Fallback Logic
        if not primary_success and fallback_name and fallback_name != primary_name:
            fallback_parser = self.parsers.get(fallback_name)
            if fallback_parser:
                attempt_start = time.time()
                try:
                    fallback_doc = await fallback_parser.parse(file_bytes, file_name, mime_type)
                    fallback_confidence = ParseConfidenceService.calculate_confidence(fallback_doc)
                    fallback_doc.confidence = fallback_confidence

                    trace.attempts.append(ParserAttempt(
                        parser_name=fallback_name,
                        success=True,
                        confidence=fallback_confidence,
                        duration_seconds=time.time() - attempt_start,
                        extracted_char_count=len(fallback_doc.text),
                        section_count=len(fallback_doc.sections)
                    ))

                    parsed_doc = fallback_doc
                    trace.final_parser_used = fallback_name
                    trace.warnings.append(f"Primary parser {primary_name} failed or had low confidence. Fallback {fallback_name} used.")

                except Exception as e:
                    trace.attempts.append(ParserAttempt(
                        parser_name=fallback_name,
                        success=False,
                        duration_seconds=time.time() - attempt_start,
                        error_message=str(e)
                    ))
                    trace.warnings.append(f"Fallback parser {fallback_name} also failed.")

        if parsed_doc is None:
            # Both failed or primary failed and no fallback
            trace.review_flagged = True
            trace.total_duration_seconds = time.time() - start_time
            raise RuntimeError(f"All parsers failed to process file {file_name}")

        trace.final_confidence = parsed_doc.confidence
        trace.total_duration_seconds = time.time() - start_time

        if trace.final_confidence < settings.parser_min_confidence:
            trace.review_flagged = True
            trace.warnings.append(f"Final confidence {trace.final_confidence} is below threshold {settings.parser_min_confidence}. Flagged for review.")

        return parsed_doc, trace
