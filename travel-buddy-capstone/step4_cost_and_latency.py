"""
step4_cost_and_latency.py        (PART 2: Cost and Latency)
===========================================================
NEW IDEA: every agent call costs MONEY (tokens) and TIME (seconds).
Before you put an agent in front of real users, measure both.

This file adds three measurements to Travel Buddy:
   1. How long did the whole answer take?
   2. How many tokens were used, and what did that cost?
   3. Streaming: the first words appear sooner, even though the
      total time is the same.

Run it:   python step4_cost_and_latency.py
"""
import asyncio
import os
import time

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

# EXAMPLE prices per 1,000 tokens. Look up your own model's real prices
# on the Azure pricing page and change these two numbers.
PRICE_PER_1K_INPUT = 0.0004
PRICE_PER_1K_OUTPUT = 0.0016


async def main():
    # ---- 1. TIME: how long does one answer take? ----
    question = "What is the best time to visit Tokyo?"
    start = time.time()
    result = await agent.run(question)
    seconds = time.time() - start

    print(f"ANSWER: {result.text}")
    print(f"TIME  : {seconds:.1f} seconds")

    # ---- 2. COST: how many tokens did that use? ----
    usage = getattr(result, "usage_details", None) or {}
    tokens_in = usage.get("input_token_count", 0) or 0
    tokens_out = usage.get("output_token_count", 0) or 0
    cost = tokens_in / 1000 * PRICE_PER_1K_INPUT + tokens_out / 1000 * PRICE_PER_1K_OUTPUT
    print(f"TOKENS: {tokens_in} in + {tokens_out} out")
    print(f"COST  : about ${cost:.5f} for this one question")
    print(f"        = ${cost * 100000:.2f} for 100,000 questions")

    # ---- 3. STREAMING: show words as they arrive ----
    print("\nNow the same kind of call, but streamed:")
    start = time.time()
    first_word_time = None
    async for chunk in agent.run("Say hello and welcome me to Travel Buddy in 20 words.", stream=True):
        if chunk.text:
            if first_word_time is None:
                first_word_time = time.time() - start
            print(chunk.text, end="", flush=True)
    total_time = time.time() - start
    print(f"\n\nFirst words after {first_word_time:.1f}s, finished after {total_time:.1f}s.")
    print("Streaming does not make the answer finish sooner. It makes it FEEL faster.")


if __name__ == "__main__":
    asyncio.run(main())
