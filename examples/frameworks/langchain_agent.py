"""A LangChain agent that checks claims with Webcite before answering.

Install:
    pip install langchain-webcite langchain langchain-anthropic
Run:     WEBCITE_API_KEY=... ANTHROPIC_API_KEY=... python langchain_agent.py
"""

from langchain.agents import create_agent
from langchain_webcite import WebciteToolkit

agent = create_agent(
    "anthropic:claude-sonnet-5",
    tools=WebciteToolkit().get_tools(),
    system_prompt="Check each claim with webcite_verify_claim and cite the URLs it returns.",
)
result = agent.invoke(
    {
        "messages": [
            {"role": "user", "content": "Can you see the Great Wall of China from the Moon?"}
        ]
    }
)
print(result["messages"][-1].content)
