"""API backend entrypoint.

This module keeps the API/A2A/MCP container entrypoint separate from the
long-running worker container while reusing the shared ``app`` package.
"""

from app.main import app, create_app

__all__ = ["app", "create_app"]
