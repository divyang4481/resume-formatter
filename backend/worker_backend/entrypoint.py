"""Worker backend entrypoint.

This module keeps the background worker container entrypoint separate from the
API/A2A/MCP container while reusing the shared ``app`` package.
"""

import asyncio

from app.core.worker import run_worker


def main() -> None:
    """Run the async worker loop."""
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
