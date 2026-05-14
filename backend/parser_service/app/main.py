import json
import logging

from fastapi import FastAPI, HTTPException

from app.adapters.parsers.docling_parser import DoclingParser
from app.schemas.parsed_document import ParsedDocument
from parser_service.app.schemas import ParseDocumentRequest, ParseDocumentResponse
from parser_service.app.storage_io import get_parser_storage, put_json_bytes

logger = logging.getLogger(__name__)
app = FastAPI(title="Resume Formatter Parser Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "parser-docling"}


@app.post("/parse-document", response_model=ParseDocumentResponse)
async def parse_document(request: ParseDocumentRequest) -> ParseDocumentResponse:
    storage = get_parser_storage()
    parser = DoclingParser()

    try:
        file_bytes = storage.get_bytes(request.input_uri)
        filename = request.input_uri.rsplit("/", 1)[-1] or f"{request.job_id}.pdf"
        parsed_doc = await parser.parse(
            file_bytes=file_bytes,
            file_name=filename,
            mime_type="application/octet-stream",
            options={"profile": request.parser_profile, "requested_outputs": request.requested_outputs},
        )
    except Exception as exc:
        logger.exception("Failed to parse %s", request.input_uri)
        raise HTTPException(status_code=500, detail=f"Document parsing failed: {exc}") from exc

    filtered = ParsedDocument(
        text=parsed_doc.text if "text" in request.requested_outputs else "",
        sections=parsed_doc.sections if "sections" in request.requested_outputs else [],
        tables=parsed_doc.tables if "tables" in request.requested_outputs else [],
        metadata={
            **parsed_doc.metadata,
            "job_id": request.job_id,
            "parser_profile": request.parser_profile,
            "input_uri": request.input_uri,
        },
        page_count=parsed_doc.page_count,
        language=parsed_doc.language,
        warnings=parsed_doc.warnings,
        parser_used=parsed_doc.parser_used or "docling",
        confidence=parsed_doc.confidence,
        artifacts=parsed_doc.artifacts,
        raw_structured_payload=(
            parsed_doc.raw_structured_payload if "layout_blocks" in request.requested_outputs else None
        ),
    )

    payload = json.dumps(filtered.model_dump(mode="json"), ensure_ascii=False).encode("utf-8")
    output_uri = put_json_bytes(storage, request.output_uri, payload)

    return ParseDocumentResponse(
        job_id=request.job_id,
        output_uri=output_uri,
        parser_used=filtered.parser_used,
        parser_profile=request.parser_profile,
        requested_outputs=request.requested_outputs,
        text_chars=len(filtered.text),
        section_count=len(filtered.sections),
        table_count=len(filtered.tables),
        confidence=filtered.confidence,
    )
