from pydantic import BaseModel
from typing import List, Dict, Any, Literal, Optional

class TemplateFieldV2(BaseModel):
    field_id: str
    fieldname: str
    original_label: Optional[str] = None
    original_heading: Optional[str] = None
    field_type: Literal[
        "scalar",
        "rich_text",
        "array_simple",
        "array_complex",
        "object",
        "paste_zone",
    ]
    source_kind: Literal[
        "resume_fact",
        "recruiter_input",
        "generated",
        "static",
    ]
    required: bool = False
    meaning: str = ""
    extract: Dict[str, Any] = {}
    render: Dict[str, Any] = {}

class TemplateSlotV2(BaseModel):
    slot_id: str
    owner_field_id: str
    slot_type: Literal[
        "marker",
        "label_value",
        "bullet_list",
        "section_body",
        "repeat_block",
        "table_loop",
        "paste_zone",
    ]
    render_mode: Literal[
        "replace_marker",
        "fill_after_label",
        "replace_bullets_under_heading",
        "replace_section_body",
        "replace_repeat_block",
        "replace_table_loop",
    ]
    locator: Dict[str, Any] = {}
    item_schema: List[Dict[str, Any]] = []

class TemplateBlockV2(BaseModel):
    block_id: str
    owner_field_id: str
    block_type: Literal["repeat_block", "table_loop"]
    heading_text: Optional[str] = None
    ordered_placeholders: List[str] = []
    sample_occurrence_count: int = 0
    subfields: List[Dict[str, Any]] = []

class TemplateInstructionV2(BaseModel):
    instruction_id: str
    text: str
    nearest_heading: Optional[str] = None
    action: Literal["remove", "preserve"] = "remove"

class TemplateManifestV2(BaseModel):
    template_id: str
    template_type: str = "unknown"
    schema_version: str = "2.0"
    language: str = "auto"
    fields: List[TemplateFieldV2] = []
    slots: List[TemplateSlotV2] = []
    blocks: List[TemplateBlockV2] = []
    instructions: List[TemplateInstructionV2] = []
    validation: Dict[str, Any] = {}
