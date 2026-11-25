"""Webcite tools in an ADK agent through the hosted MCP server.

Install: pip install "google-adk[mcp]"

Run `python google_adk_mcp.py` to list the tools the agent receives (no model call).
Run `adk web` from the parent folder to chat with `root_agent` (needs GOOGLE_API_KEY).
"""

import asyncio
import os

from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

webcite_tools = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://api.webcite.co/mcp?profile=core",
        headers={"Authorization": f"Bearer {os.environ['WEBCITE_API_KEY']}"},
        timeout=30.0,
        sse_read_timeout=300.0,
    ),
)

root_agent = Agent(
    model="gemini-flash-latest",
    name="webcite_agent",
    instruction=(
        "Check factual claims with verify_claim and report the verdict with its citations. "
        "To read a document, call upload_url and then extract_document."
    ),
    tools=[webcite_tools],
)


async def main() -> None:
    try:
        tools = await webcite_tools.get_tools()
        print(len(tools), "tools:", ", ".join(t.name for t in tools))
    finally:
        await webcite_tools.close()


if __name__ == "__main__":
    asyncio.run(main())
