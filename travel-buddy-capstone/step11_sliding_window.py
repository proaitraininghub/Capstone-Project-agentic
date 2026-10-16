"""
step11_sliding_window.py         (PART 3: Compression Strategy - Sliding Window)
================================================================================
NEW IDEA: keep only the LAST few turns and throw the rest away.

   + Size stays small and fixed. No extra AI calls needed.
   - Anything older is completely gone. The AI cannot remember it.

Watch what happens when we ask about something said at the very START
of the conversation.

Run it:   python step11_sliding_window.py
"""
import asyncio
import os

from dotenv import load_dotenv
from azure.identity import AzureCliCredential
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework.openai import OpenAIChatClient

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
    instructions="You are Travel Buddy, a friendly travel helper. Use ONLY the conversation given to you. If something is not in it, say you do not know. Answer in 2 sentences.",
)

TURNS = [
    ("user", "Hi! I'm Priya. I'm planning a trip and I'm allergic to peanuts."),
    ("assistant", "Nice to meet you, Priya! I'll keep the peanut allergy in mind. Where would you like to go?"),
    ("user", "I'm thinking about Tokyo in spring."),
    ("assistant", "Great choice. Spring, from March to May, is cherry blossom season."),
    ("user", "My budget is about 2000 dollars for the whole trip."),
    ("assistant", "That is workable for a week if you choose budget hotels."),
    ("user", "I also want to see some famous landmarks."),
    ("assistant", "Tokyo Tower and Senso-ji temple are popular choices."),
    ("user", "What about food?"),
    ("assistant", "Try sushi and ramen, and tell every restaurant about your allergy."),
]

WINDOW_SIZE = 4      # keep only the last 4 turns


def sliding_window_context(turns, window_size):
    recent_turns = turns[-window_size:]          # the last N turns
    return "\n".join(f"{role}: {text}" for role, text in recent_turns)


async def main():
    context = sliding_window_context(TURNS, WINDOW_SIZE)
    print("=== What the AI is allowed to remember (the window) ===")
    print(context)

    question = "Quick reminder: what was I allergic to, and what is my budget?"
    prompt = f"Conversation so far:\n{context}\n\nNew question: {question}"

    result = await agent.run(prompt)
    print(f"\nYOU: {question}")
    print(f"TRAVEL BUDDY: {result.text}")
    print("\nThe allergy and the budget were said in turns 1 and 5, outside the window.")
    print("They are gone. That is the price of the sliding window.")


if __name__ == "__main__":
    asyncio.run(main())
