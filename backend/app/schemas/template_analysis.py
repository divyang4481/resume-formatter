from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class RenderLocator(BaseModel):
    strategy: str = Field(..., description="replace_marker, fill_blank_cell_after_label, replace_section_body, replace_bullets_under_heading, clear_instruction_block")
    marker: str = ""
    label: str = ""
    heading: str = ""

class TemplateField(BaseModel):
    field_name: str = Field(..., alias="fieldname")
    marker_text: str = ""
    field_type: str = "scalar"  # scalar, rich_text, table_loop, etc.
    source_kind: str = "resume_fact"  # resume_fact, recruiter_input, generated, static, instruction
    render_locator: RenderLocator
    meaning: str = ""
    source_hints: str = ""
    required: bool = False
    confidence: float = 0.0

    model_config = {
        "populate_by_name": True
    }

class InstructionBlock(BaseModel):
    text: str
    action: str = "remove_or_replace"
    meaning: str = ""

class RepeatableBlock(BaseModel):
    block_name: str
    starts_at: str  # heading or marker
    repeat_pattern: Dict[str, str]  # fieldname -> marker/pattern

class StaticBlock(BaseModel):
    text: str
    action: str = "preserve"
    meaning: str = ""

class TemplateSection(BaseModel):
    section_name: str
    page: Optional[int] = None
    fields: List[TemplateField] = Field(default_factory=list)

class TemplateAnalysis(BaseModel):
    template_id: str = ""
    template_type: str = "candidate_profile"
    brand: str = "Generic"
    purpose: str = ""
    expected_sections: List[str] = Field(default_factory=list)
    expected_fields: List[str] = Field(default_factory=list)
    summary_guidance: str = ""
    formatting_guidance: str = ""
    validation_guidance: str = ""
    pii_guidance: str = ""

    sections: List[TemplateSection] = Field(default_factory=list)
    instruction_blocks: List[InstructionBlock] = Field(default_factory=list)
    repeatable_blocks: List[RepeatableBlock] = Field(default_factory=list)
    static_blocks: List[StaticBlock] = Field(default_factory=list)
    
    # Flat field list for easier iteration in renderer
    # Alias matches the prompt's key
    fields: List[TemplateField] = Field(default_factory=list, alias="field_extraction_manifest")

    model_config = {
        "populate_by_name": True,
        "extra": "ignore"
    }

# --- Candidate Facts Schema ---

class WorkExperience(BaseModel):
    job_title: str
    company: str
    start_date: str
    end_date: str
    responsibilities: List[str] = Field(default_factory=list)

class Education(BaseModel):
    degree: str
    institution: str
    completion_date: str
    details: str = ""

class CandidateFacts(BaseModel):
    full_name: str
    location: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    summary: str = ""
    skills: List[str] = Field(default_factory=list)
    work_experience: List[WorkExperience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    professional_qualifications: List[str] = Field(default_factory=list)
    salary_current: Optional[str] = None
    salary_required: Optional[str] = None
    notice_period: Optional[str] = None
    
    # Extension for dynamic fields or additional facts not in the core schema
    extension_metadata: Dict[str, Any] = Field(default_factory=dict)

class TemplateFillPlan(BaseModel):
    template_id: str
    fields: Dict[str, Any] = Field(default_factory=dict)
    instructions_to_clear: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
