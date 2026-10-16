"""
step12_summary_buffer.py         (PART 3: Compression Strategy - Summary Buffer)
================================================================================
NEW IDEA: keep the RECENT turns word for word, and let a second small
agent (a "summarizer") squeeze the OLD turns into a few sentences.

   + Important old facts survive, inside the summary.
   - One extra AI call whenever you summarize, and the summary can
     lose small details.

Same conversation, same question as step 11. This time it remembers.

Run it:   python step12_summary_buffer.py
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

# Agent 1: the travel helper (same as before)
agent = Agent(
    client=client,
    name="TravelBuddy",
    instructions="You are Travel Buddy, a friendly travel helper. Use ONLY the conversation given to you. If something is not in it, say you do not know. Answer in 2 sentences.",
)

# Agent 2: a summarizer whose only job is to shorten old conversation
summarizer = Agent(
    client=client,
    name="Summarizer",
    instructions=(
        "Summarize this conversation in 2 or 3 sentences. "
        "Keep every concrete fact: names, allergies, budgets, places, dates. "
        "Drop greetings and small talk."
    ),
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

RECENT_SIZE = 4      # keep the last 4 turns word for word


async def summary_buffer_context(turns, recent_size):
    older_turns = turns[:-recent_size]       # everything EXCEPT the last 4 turns
    recent_turns = turns[-recent_size:]      # the last 4 turns

    older_text = "\n".join(f"{role}: {text}" for role, text in older_turns)
    summary_result = await summarizer.run(older_text)     # the extra AI call
    summary = summary_result.text

    recent_text = "\n".join(f"{role}: {text}" for role, text in recent_turns)
    return f"[Summary of earlier conversation]: {summary}\n\n{recent_text}"


async def main():
    context = await summary_buffer_context(TURNS, RECENT_SIZE)
    print("=== What the AI gets (summary + recent turns) ===")
    print(context)

    question = "Quick reminder: what was I allergic to, and what is my budget?"
    prompt = f"Conversation so far:\n{context}\n\nNew question: {question}"

    result = await agent.run(prompt)
    print(f"\nYOU: {question}")
    print(f"TRAVEL BUDDY: {result.text}")
    print("\nThe allergy and budget were in the OLD turns, but they survived inside the summary.")


if __name__ == "__main__":
    asyncio.run(main())
