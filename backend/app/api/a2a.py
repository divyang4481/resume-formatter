from typing import Any, Dict

from fastapi import APIRouter, Request

router = APIRouter()

AGENT_NAME = "Agentic Document Platform"
AGENT_VERSION = "1.0.0"
PROCESSING_ENDPOINTS = {
    "lookup_industries": "/api/v1/processing/lookups/industries",
    "lookup_templates": "/api/v1/processing/lookups/templates",
    "submit_document": "/api/v1/processing/documents/submit",
    "confirm_document": "/api/v1/processing/documents/{id}/confirm",
    "get_document_status": "/api/v1/processing/jobs/{id}",
    "stream_document_events": "/api/v1/processing/documents/{id}/stream",
    "download_document": "/api/v1/processing/documents/{id}/download",
    "get_job_output": "/api/v1/processing/jobs/{id}/output",
    "get_job_summary": "/api/v1/processing/jobs/{id}/summary",
    "get_job_facts": "/api/v1/processing/jobs/{id}/facts",
    "get_job_transformation": "/api/v1/processing/jobs/{id}/transformation",
    "get_job_template": "/api/v1/processing/jobs/{id}/template",
    "submit_feedback": "/api/v1/processing/jobs/{id}/feedback",
}


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _agent_card(request: Request) -> Dict[str, Any]:
    base_url = _base_url(request)
    return {
        "schema_version": "a2a-agent-card-v1",
        "agent_name": AGENT_NAME,
        "name": AGENT_NAME,
        "version": AGENT_VERSION,
        "description": "Transforms resumes and CVs into governed, structured, template-driven outputs.",
        "url": base_url,
        "protocols": ["REST", "A2A", "MCP"],
        "capabilities": {
            "streaming": True,
            "push_notifications": False,
            "state_transition_history": True,
            "openapi": f"{base_url}/openapi.json",
            "mcp": f"{base_url}/mcp",
        },
        "skills": [
            {
                "id": "format_document",
                "name": "Format document",
                "description": "Submit a resume or CV and render it into a selected template.",
                "endpoint": PROCESSING_ENDPOINTS["submit_document"],
            },
            {
                "id": "summarize_profile",
                "name": "Summarize profile",
                "description": "Retrieve a generated profile summary for a processed document.",
                "endpoint": PROCESSING_ENDPOINTS["get_job_summary"],
            },
            {
                "id": "generate_client_safe_profile",
                "name": "Generate client-safe profile",
                "description": "Use the governed processing pipeline to produce privacy-safe profile outputs.",
                "endpoint": PROCESSING_ENDPOINTS["get_job_output"],
            },
            {
                "id": "validate_document",
                "name": "Validate document",
                "description": "Inspect processing status, facts, transformation data, and template mapping.",
                "endpoint": PROCESSING_ENDPOINTS["get_document_status"],
            },
        ],
        "endpoints": PROCESSING_ENDPOINTS,
        "authentication": {"type": "none"},
    }


@router.get("/.well-known/ai-plugin.json", include_in_schema=False)
async def get_ai_plugin_manifest(request: Request) -> Dict[str, Any]:
    """
    Exposes an OpenAI / Copilot compatible plugin manifest.
    """
    base_url = _base_url(request)
    return {
        "schema_version": "v1",
        "name_for_model": "AgenticDocumentPlatform",
        "name_for_human": "Document Processing Platform",
        "description_for_model": "Plugin for processing, formatting, validating, and summarizing CVs and resumes using governed templates.",
        "description_for_human": "Process, format, validate, and extract information from resumes and CVs.",
        "auth": {"type": "none"},
        "api": {
            "type": "openapi",
            "url": f"{base_url}/openapi.json",
        },
        "logo_url": f"{base_url}/logo.png",
        "contact_email": "support@example.com",
        "legal_info_url": "http://www.example.com/legal",
    }


@router.get("/.well-known/agent.json", tags=["A2A Discoverability"])
@router.get("/.well-known/agent-card.json", tags=["A2A Discoverability"])
async def get_agent_card(request: Request) -> Dict[str, Any]:
    """
    Exposes an A2A-discoverable agent card.
    Allows orchestrators to discover the service, skills, schemas, REST endpoints, and MCP endpoint.
    """
    return _agent_card(request)


@router.get("/.well-known/mcp.json", tags=["MCP Discoverability"])
async def get_mcp_manifest(request: Request) -> Dict[str, Any]:
    """
    Exposes a lightweight MCP discovery document for clients that discover tool endpoints via well-known URLs.
    """
    base_url = _base_url(request)
    return {
        "schema_version": "mcp-discovery-v1",
        "name": AGENT_NAME,
        "version": AGENT_VERSION,
        "transport": {
            "type": "streamable-http",
            "url": f"{base_url}/mcp",
        },
        "openapi_url": f"{base_url}/openapi.json",
        "tool_groups": ["Candidate Processing", "Processing", "Admin"],
    }
