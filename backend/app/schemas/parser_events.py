from typing import List, Optional
from pydantic import BaseModel, Field

class ParserAttempt(BaseModel):
    parser_name: str
    success: bool
    confidence: Optional[float] = None
    duration_seconds: float
    error_message: Optional[str] = None
    extracted_char_count: int = 0
    section_count: int = 0

class ParseResultTrace(BaseModel):
    file_id: str
    mime_type: str
    primary_parser_attempted: str
    fallback_parser_attempted: Optional[str] = None
    final_parser_used: str
    attempts: List[ParserAttempt] = Field(default_factory=list)
    total_duration_seconds: float
    final_confidence: Optional[float] = None
    review_flagged: bool = False
    warnings: List[str] = Field(default_factory=list)
