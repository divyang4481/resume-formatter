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
            "runtime": "/v1/documents/submit"
        }
    }
