"""Use Webcite's hosted MCP server from a CrewAI agent.

    pip install crewai "crewai-tools[mcp]"
    export WEBCITE_API_KEY=...   # from https://webcite.co/api-keys
    python crewai_mcp.py

Environment variables:
    WEBCITE_API_KEY  required; tool calls spend credits in the key's account.
    OPENAI_API_KEY or MODEL  the crew runs only when one of them is set.

Without a model key the script connects to https://api.webcite.co/mcp and lists the
Webcite tools, which spends no credits.
"""

import os

from crewai import Agent, Crew, Task
from crewai.mcp import MCPServerHTTP

WEBCITE_MCP_URL = "https://api.webcite.co/mcp"
CLAIM = "The Great Wall of China is visible from the Moon with the naked eye."


def webcite_server(api_key: str) -> MCPServerHTTP:
    return MCPServerHTTP(
        url=WEBCITE_MCP_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        cache_tools_list=True,
    )


def main() -> None:
    api_key = os.environ.get("WEBCITE_API_KEY")
    if not api_key:
        print("Set WEBCITE_API_KEY (from https://webcite.co/api-keys) and run this file again.")
        return

    agent = Agent(
        role="Fact checker",
        goal="Say whether a claim holds, citing the sources Webcite returns",
        backstory="You call Webcite's verify_claim tool before you report on any claim.",
        mcps=[webcite_server(api_key)],
    )

    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("MODEL"):
        tools = agent.get_mcp_tools(agent.mcps or [])
        print(f"Connected to {WEBCITE_MCP_URL}: {len(tools)} tools")
        for tool in tools:
            print(f"- {tool.name}")
        print("Set OPENAI_API_KEY, or MODEL for another provider, to run the crew.")
        return

    task = Task(
        description=f"Check this claim with Webcite and report the verdict: {CLAIM}",
        expected_output="The verdict, a one-sentence reason and the cited URLs.",
        agent=agent,
    )
    print(Crew(agents=[agent], tasks=[task]).kickoff())


if __name__ == "__main__":
    main()
