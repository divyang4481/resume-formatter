from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ParsedSection(BaseModel):
    title: Optional[str] = None
    level: int = 1
    content: str

class ParsedTable(BaseModel):
    title: Optional[str] = None
    data: List[List[str]] = []

class ParsedDocument(BaseModel):
    text: str = ""
    sections: List[ParsedSection] = Field(default_factory=list)
    tables: List[ParsedTable] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    page_count: Optional[int] = None
    language: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    parser_used: str = ""
    confidence: Optional[float] = None
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    raw_structured_payload: Optional[Dict[str, Any]] = None
