"""
step5_retry_and_timeout.py       (PART 2: Reliability)
=====================================================
NEW IDEA: AI calls sometimes fail for a moment (busy server, network
glitch). A good app does not give up on the first failure.

Two separate protections:
   TIMEOUT  stops ONE attempt from waiting forever.
   RETRY    tries again a few times, waiting longer each time
            (1s, 2s, 4s...) so we do not hammer a struggling server.

To let you SEE it work, the first 2 attempts fail ON PURPOSE.

Run it:   python step5_retry_and_timeout.py
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

INSTRUCTIONS = (
    "You are Travel Buddy, a friendly travel helper. "
    "For cities we have saved, use get_city_facts. "
    "For anything else, use search_wikipedia. "
    "Never guess. Answer in two or three sentences."
)

agent = Agent(
    client=client,
    name="TravelBuddy",
    instructions=INSTRUCTIONS,
    tools=[get_city_facts, search_wikipedia],
)

SIMULATED_FAILURES = 2          # the first 2 attempts fail on purpose
attempts_so_far = {"count": 0}  # a little counter we can change from inside the function


async def ask_with_retry(question, max_attempts=4, timeout_seconds=30):
    """Ask the agent. If it fails for a temporary reason, wait and try again."""
    for attempt in range(1, max_attempts + 1):
        try:
            attempts_so_far["count"] += 1
            if attempts_so_far["count"] <= SIMULATED_FAILURES:
                raise ConnectionError("simulated network glitch")

            # wait_for = the TIMEOUT: give up on this attempt after 30 seconds
            return await asyncio.wait_for(agent.run(question), timeout=timeout_seconds)

        except (ConnectionError, asyncio.TimeoutError) as error:
            wait_seconds = 2 ** (attempt - 1)      # 1, 2, 4, 8 ...
            print(f"  Attempt {attempt} failed ({error}). Waiting {wait_seconds}s, then retrying...")
            await asyncio.sleep(wait_seconds)

    raise RuntimeError("All attempts failed. Telling the user nicely is better than crashing.")


async def main():
    print("Asking about the Eiffel Tower...")
    result = await ask_with_retry("Tell me about the Eiffel Tower.")
    print(f"\nANSWER (after {attempts_so_far['count']} attempts): {result.text}")


if __name__ == "__main__":
    asyncio.run(main())
