"""Webcite tools in an OpenAI Agents SDK agent through the hosted MCP server.

Install: pip install openai-agents

Run `python openai_agents_mcp.py` to list the tools (no model call).
Run `python openai_agents_mcp.py "claim to check"` to run the agent (needs OPENAI_API_KEY).
"""

import asyncio
import os
import sys

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp


async def main() -> None:
    async with MCPServerStreamableHttp(
        name="Webcite",
        params={
            "url": "https://api.webcite.co/mcp?profile=core",
            "headers": {"Authorization": f"Bearer {os.environ['WEBCITE_API_KEY']}"},
            "timeout": 30,
            "sse_read_timeout": 300,
        },
        client_session_timeout_seconds=300,
        cache_tools_list=True,
    ) as webcite:
        if len(sys.argv) < 2:
            tools = await webcite.list_tools()
            print(len(tools), "tools:", ", ".join(t.name for t in tools))
            return
        agent = Agent(
            name="Fact checker",
            instructions="Check the claim with verify_claim. Report the verdict and cite sources.",
            mcp_servers=[webcite],
        )
        result = await Runner.run(agent, sys.argv[1])
        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
