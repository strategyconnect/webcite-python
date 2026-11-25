"""Webcite tools in a Pydantic AI agent through the hosted MCP server.

Install: pip install "pydantic-ai-slim[mcp]"

Run `python pydantic_ai_mcp.py` to list the tools (no model call).
Run `python pydantic_ai_mcp.py "claim to check"` to run the agent (needs a model key, for example
OPENAI_API_KEY, and a model name in PYDANTIC_AI_MODEL such as "openai:gpt-5").
"""

import asyncio
import os
import sys

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset

webcite = MCPToolset(
    "https://api.webcite.co/mcp?profile=core",
    headers={"Authorization": f"Bearer {os.environ['WEBCITE_API_KEY']}"},
)


async def main() -> None:
    async with webcite:
        if len(sys.argv) < 2:
            tools = await webcite.list_tools()
            print(len(tools), "tools:", ", ".join(t.name for t in tools))
            return
        agent = Agent(
            os.environ.get("PYDANTIC_AI_MODEL", "openai:gpt-5"),
            instructions="Check the claim with verify_claim. Report the verdict and cite sources.",
            toolsets=[webcite],
        )
        result = await agent.run(sys.argv[1])
        print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
