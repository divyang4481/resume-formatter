from typing import Literal

from pydantic import BaseModel, Field

RequestedOutput = Literal["text", "sections", "tables", "layout_blocks"]


class ParseDocumentRequest(BaseModel):
    job_id: str
    input_uri: str
    output_uri: str
    parser_profile: str = "resume_v1"
    requested_outputs: list[RequestedOutput] = Field(default_factory=lambda: ["text", "sections"])


class ParseDocumentResponse(BaseModel):
    job_id: str
    output_uri: str
    parser_used: str
    parser_profile: str
    requested_outputs: list[RequestedOutput]
    text_chars: int
    section_count: int
    table_count: int
    confidence: float | None = None
