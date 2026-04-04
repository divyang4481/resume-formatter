from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter()

@router.get("/.well-known/agent.json")
async def get_agent_card() -> Dict[str, Any]:
    """
    Exposes an A2A-discoverable agent card.
    Allows orchestrators to discover the service, skills, and schemas.
    """
    return {
        "agent_name": "Agentic Document Platform",
        "version": "1.0",
        "description": "Transforms unstructured documents into structured, template-driven outputs.",
        "skills": [
            "format_document",
            "summarize_profile",
            "generate_blind_profile",
            "validate_document"
        ],
        "endpoints": {
            "lookup_industries": "/v1/processing/lookups/industries",
            "lookup_templates": "/v1/processing/lookups/templates",
            "submit_document": "/v1/processing/documents/submit",
            "confirm_document": "/v1/processing/documents/{id}/confirm",
            "get_document_status": "/v1/processing/jobs/{id}",
            "stream_document_events": "/v1/processing/documents/{id}/stream",
            "download_document": "/v1/processing/documents/{id}/download",
            "get_job_output": "/v1/processing/jobs/{id}/output",
            "get_job_summary": "/v1/processing/jobs/{id}/summary",
            "submit_feedback": "/v1/processing/jobs/{id}/feedback"
        }
    }
