"""
step9_parallel_specialists.py    (PART 2: Orchestration Builders - Concurrent)
================================================================================
NEW IDEA: some jobs are better done by SEVERAL specialist agents working
AT THE SAME TIME on the same request, then combined.

Here, three specialists plan one day in a city, all in parallel:
   FoodExpert, SightsExpert, BudgetExpert

ConcurrentBuilder is the ready-made tool for this. You list the agents,
call .build(), and run it. It is the first place in this course where
using several agents can be FASTER than using one.

Run it:   python step9_parallel_specialists.py
"""
import asyncio
import os
import time

from dotenv import load_dotenv
from azure.identity import AzureCliCredential
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework.openai import OpenAIChatClient
from agent_framework.orchestrations import ConcurrentBuilder

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

food_expert = Agent(
    client=client,
    name="FoodExpert",
    instructions="You are a food expert. For the city mentioned, suggest 2 local dishes to try. Keep it to 3 sentences.",
)

sights_expert = Agent(
    client=client,
    name="SightsExpert",
    instructions="You are a sightseeing expert. For the city mentioned, suggest 2 places to visit. Keep it to 3 sentences.",
)

budget_expert = Agent(
    client=client,
    name="BudgetExpert",
    instructions="You are a budget expert. For the city mentioned, give 2 money-saving tips. Keep it to 3 sentences.",
)


async def main():
    # Build the parallel workflow from the three specialists
    workflow = ConcurrentBuilder(participants=[food_expert, sights_expert, budget_expert]).build()

    start = time.time()
    events = await workflow.run("Plan one day in Lisbon.")
    seconds = time.time() - start

    # One result comes back with a message from each specialist
    for output in events.get_outputs():
        for message in output.messages:
            print(f"--- {message.author_name} ---")
            print(message.text)
            print()

    print(f"All three specialists finished in {seconds:.1f} seconds (they ran at the same time).")
    print("Run them one after the other and the time would be roughly three times longer.")


if __name__ == "__main__":
    asyncio.run(main())
