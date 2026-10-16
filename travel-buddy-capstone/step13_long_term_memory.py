"""
step13_long_term_memory.py       (PART 3: Memory Types - Long-term Memory)
===========================================================================
NEW IDEA: there are three kinds of memory.

   Working memory     what is in the prompt for THIS call.
   Session memory     the chat so far (lost when the session ends).
   LONG-TERM memory   facts saved to a FILE, so a brand new chat
                      still knows them.   <-- this step

In Agent Framework, long-term memory is built with a CONTEXT PROVIDER.
It has two hooks that run automatically around every agent call:
   before_run  -> add saved facts to the instructions.
   after_run   -> look at the new message and save any new facts.

Run it:   python step13_long_term_memory.py
"""
import asyncio
import json
import os
import re

from dotenv import load_dotenv
from azure.identity import AzureCliCredential
from agent_framework import Agent, ContextProvider
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

MEMORY_FILE = "memory_store.json"        # our simple "database": one small file


def load_facts():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE) as file:
            return json.load(file)
    return {}


def save_facts(facts):
    with open(MEMORY_FILE, "w") as file:
        json.dump(facts, file, indent=2)


def find_facts(text):
    """Look for simple facts in a message, using patterns."""
    found = {}
    name = re.search(r"my name is (\w+)", text, re.IGNORECASE)
    if name:
        found["name"] = name.group(1).capitalize()
    allergy = re.search(r"allergic to (\w+)", text, re.IGNORECASE)
    if allergy:
        found["allergy"] = allergy.group(1).lower()
    return found


class TravelMemory(ContextProvider):
    """Long-term memory for Travel Buddy."""

    def __init__(self):
        super().__init__("travel_memory")

    async def before_run(self, *, agent, session, context, state) -> None:
        facts = load_facts()
        if facts:
            known = ", ".join(f"{key} = {value}" for key, value in facts.items())
            context.extend_instructions(self.source_id, f"Known facts about this traveller: {known}. Use them.")
        else:
            context.extend_instructions(self.source_id, "You do not know anything about this traveller yet.")

    async def after_run(self, *, agent, session, context, state) -> None:
        facts = load_facts()
        for message in context.input_messages:
            text = getattr(message, "text", "")
            if isinstance(text, str):
                facts.update(find_facts(text))
        save_facts(facts)


agent = Agent(
    client=client,
    name="TravelBuddy",
    instructions="You are Travel Buddy, a friendly travel helper. Answer in 2 sentences.",
    context_providers=[TravelMemory()],
)


async def main():
    if os.path.exists(MEMORY_FILE):
        os.remove(MEMORY_FILE)                 # start clean so the demo is repeatable

    # ---- CHAT 1 ----
    session_one = agent.create_session()
    print("=== CHAT 1 ===")
    message = "Hi, my name is Priya and I am allergic to peanuts."
    print(f"YOU: {message}")
    print(f"TRAVEL BUDDY: {(await agent.run(message, session=session_one)).text}")

    print(f"\nSaved in {MEMORY_FILE}: {load_facts()}")

    # ---- CHAT 2: a brand new session. Session memory is empty! ----
    session_two = agent.create_session()
    print("\n=== CHAT 2 (a completely new session) ===")
    message = "What is my name, and what food should I avoid in Tokyo?"
    print(f"YOU: {message}")
    print(f"TRAVEL BUDDY: {(await agent.run(message, session=session_two)).text}")
    print("\nThe new session knew, because the facts came from the FILE, not from the chat.")


if __name__ == "__main__":
    asyncio.run(main())
