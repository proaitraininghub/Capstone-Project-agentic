"""
step17_online_sampling.py        (PART 4: Online Evaluation - Sampling)
========================================================================
NEW IDEA: your test cases only cover what YOU imagined. Real users ask
surprising things. ONLINE evaluation checks real traffic after release.

You cannot judge every conversation (it would double your cost), so you
check a random SAMPLE, for example 30%.

Here the "real traffic" is a list of questions. The judge gives each
sampled answer a score from 1 to 5.

Run it:   python step17_online_sampling.py
"""
import asyncio
import os
import random

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

judge = Agent(
    client=client,
    name="Judge",
    instructions=(
        "You rate how helpful and correct a travel answer is. "
        "Reply with ONE digit from 1 (bad) to 5 (excellent) and nothing else."
    ),
)

SAMPLE_RATE = 0.3          # judge about 30% of conversations

LIVE_TRAFFIC = [
    "Best time to visit Paris?",
    "What currency does Tokyo use?",
    "Tell me about the Sagrada Familia.",
    "Hello there!",
    "What food should I try in Lisbon?",
    "Tell me about Mount Fuji.",
    "Is Berlin good in winter?",
    "What is the Colosseum?",
    "Best time to visit Lisbon?",
    "Tell me about the Louvre.",
]


async def main():
    scores = []

    for question in LIVE_TRAFFIC:
        result = await agent.run(question)            # every question gets an answer

        if random.random() < SAMPLE_RATE:             # but only ~30% get judged
            verdict = (await judge.run(f"Question: {question}\nAnswer: {result.text}")).text.strip()
            score = int(verdict[0]) if verdict and verdict[0].isdigit() else 0
            scores.append(score)
            print(f"JUDGED  score {score}/5 : {question}")
        else:
            print(f"skipped              : {question}")

    print(f"\nJudged {len(scores)} of {len(LIVE_TRAFFIC)} conversations.")
    if scores:
        print(f"Average score: {sum(scores) / len(scores):.1f} out of 5")
    print("\nThink: what if SAMPLE_RATE were 1.0? (Full visibility, but double the cost.)")
    print("What if it were 0.01? (Cheap, but you might miss problems.)")


if __name__ == "__main__":
    asyncio.run(main())
