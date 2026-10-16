"""
step14_nondeterminism.py         (PART 4: Why Evaluate at All)
===============================================================
NEW IDEA: normal code gives the same output for the same input, so one
test is enough. An AI agent does NOT. Ask the same question five times
and you can get five different answers.

So we cannot just "run it once and see". We need a way to MEASURE quality
across many tries. The next steps build that.

Run it:   python step14_nondeterminism.py
"""
import asyncio
import os

from dotenv import load_dotenv
from azure.identity import AzureCliCredential
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework.openai import OpenAIChatClient

from tools import get_city_facts, search_wikipedia

load_dotenv()

# Set USE_OPENAI=true in your .env file to use an OpenAI key instead of Azure.
USE_OPENAI = os.environ.get("USE_OPENAI", "false").lower() == "true"

if USE_OPENAI:
    # OPTION B: OpenAI (uses your OPENAI_API_KEY)
    client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"],
        model=os.environ["OPENAI_MODEL"],
    )
else:
    # OPTION A: Azure AI Foundry (uses az login)
    client = FoundryChatClient(
        project_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
        credential=AzureCliCredential(),
    )

agent = Agent(
    client=client,
    name="TravelBuddy",
    instructions=(
        "You are Travel Buddy, a friendly travel helper. "
        "For cities we have saved, use get_city_facts. "
        "For anything else, use search_wikipedia. "
        "Never guess. Answer in two or three sentences."
    ),
    tools=[get_city_facts, search_wikipedia],
)


async def main():
    question = "What is the best time to visit Tokyo?"
    answers = []

    for attempt in range(1, 6):
        result = await agent.run(question)        # the SAME question every time
        answers.append(result.text.strip())
        print(f"Run {attempt}: {result.text.strip()}\n")

    different = len(set(answers))
    print(f"Out of 5 identical questions, there were {different} different answers.")
    print("All may be CORRECT, but the wording changes. This is why testing an agent is different.")


if __name__ == "__main__":
    asyncio.run(main())
