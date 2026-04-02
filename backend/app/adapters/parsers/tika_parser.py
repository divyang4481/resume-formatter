import io
from typing import Any, Dict, List
from tika import parser as tika_parser
from app.domain.interfaces.document_parser import DocumentParser
from app.schemas.parsed_document import ParsedDocument

class TikaParser(DocumentParser):
    def __init__(self):
        pass

    async def parse(self, file_bytes: bytes, file_name: str, mime_type: str, options: Dict[str, Any] = None) -> ParsedDocument:
        # Tika can parse from bytes via an in-memory buffer, but tika library might need a stream or temp file
        # We'll use the buffer directly here if tika supports it, else we need a temp file or stream
        parsed = tika_parser.from_buffer(file_bytes)

        text = parsed.get("content", "")
        if text:
            text = text.strip()

        metadata = parsed.get("metadata", {})

        return ParsedDocument(
            text=text or "",
            metadata=metadata,
            parser_used="tika",
            warnings=["Tika used for extraction, structured elements like tables/sections may be lost."]
        )

    async def healthcheck(self) -> bool:
        try:
            # Just test if tika server is reachable / starts
            tika_parser.from_buffer(b"test")
            return True
        except Exception:
            return False

    def supports(self, mime_type: str, extension: str) -> bool:
        # Tika supports almost everything
        return True

    def capabilities(self) -> List[str]:
        return ["text", "metadata"]
