from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter()

@router.get("/mcp/manifest")
async def mcp_manifest() -> Dict[str, Any]:
    """
    Exposes MCP manifest for tool-host environments.
    """
    return {
        "tools": [
            {
                "name": "submit_document",
                "description": "Submits a document for processing, optionally with industry and template IDs."
            },
            {
                "name": "confirm_document",
                "description": "Confirms the industry and template for a submitted document."
            },
            {
                "name": "get_document_status",
                "description": "Checks the processing status of a document job."
            },
            {
                "name": "format_document",
                "description": "Applies template to a document."
            },
            {
                "name": "summarize_document",
                "description": "Generates a summary of an uploaded CV."
            },
            {
                "name": "validate_document",
                "description": "Checks completeness, schema, and chronology constraints."
            },
            {
                "name": "generate_client_safe_profile",
                "description": "Generates a privacy-transformed version of the profile."
            }
        ]
    }

@router.post("/mcp/tools/{tool_name}")
async def execute_mcp_tool(tool_name: str, payload: Dict[str, Any]):
    """
    Executes an MCP capability as a tool invocation.
    Typically blocking for small payloads, may return async ref for large ones.
    """
    return {
        "tool": tool_name,
        "status": "executed",
        "result": {}
    }
