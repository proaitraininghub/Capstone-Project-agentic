"""
step7_fallback_and_circuit_breaker.py    (PART 2: Failure Handling)
=========================================================================
NEW IDEA: retries are not enough. If the main model is DOWN, every user
would wait through all the retries and then still get an error.

Two ideas fix that:
   FALLBACK         a backup that gives a simpler answer instead of nothing.
   CIRCUIT BREAKER  after a few failures, STOP trying the broken thing for
                    a while and go straight to the backup (like a fuse box
                    cutting power so nothing burns).

The main model is made to fail ON PURPOSE so you can watch both ideas.

Run it:   python step7_fallback_and_circuit_breaker.py
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

# The main client...
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

# ...and the backup client. Use a different (cheaper or separate) deployment if you have one.
if USE_OPENAI:
    # OPTION B: OpenAI (uses your OPENAI_API_KEY)
    backup_client = OpenAIChatClient(
        api_key=os.environ["OPENAI_API_KEY"],
        model=os.environ.get("OPENAI_FALLBACK_MODEL", os.environ["OPENAI_MODEL"]),
    )
else:
    # OPTION A: Azure AI Foundry (uses az login)
    backup_client = FoundryChatClient(
        project_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        model=os.environ.get("AZURE_OPENAI_FALLBACK_DEPLOYMENT", os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"]),
        credential=AzureCliCredential(),
    )

main_agent = Agent(
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

# The backup has NO tools. It gives a simpler, safer answer.
backup_agent = Agent(
    client=backup_client,
    name="TravelBuddyBackup",
    instructions=(
        "You are Travel Buddy running in backup mode. You cannot look things up right now. "
        "Give a short general answer and say that live details are temporarily unavailable."
    ),
)

MAIN_MODEL_IS_DOWN = True      # pretend the main model is broken. Set to False to see normal behaviour.


class CircuitBreaker:
    """Counts failures. After too many, it 'opens' and blocks calls for a cooldown time."""

    def __init__(self, failure_limit=3, cooldown_seconds=20):
        self.failure_limit = failure_limit
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.opened_at = None          # None means the breaker is closed (calls are allowed)

    def is_open(self):
        if self.opened_at is None:
            return False
        if time.time() - self.opened_at >= self.cooldown_seconds:
            self.opened_at = None      # cooldown over: allow a new try
            self.failures = 0
            return False
        return True

    def record_success(self):
        self.failures = 0
        self.opened_at = None

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.failure_limit:
            self.opened_at = time.time()
            print("  >>> Circuit breaker OPENED. Skipping the main model for a while.")


breaker = CircuitBreaker(failure_limit=3, cooldown_seconds=20)


async def ask(question):
    if not breaker.is_open():
        try:
            if MAIN_MODEL_IS_DOWN:
                raise ConnectionError("main model is down (simulated)")
            result = await main_agent.run(question)
            breaker.record_success()
            return "MAIN  ", result.text
        except Exception as error:
            breaker.record_failure()
            print(f"  Main model failed: {error}")

    # Either the breaker is open, or the main model just failed: use the backup.
    result = await backup_agent.run(question)
    return "BACKUP", result.text


async def main():
    questions = [
        "Best time to visit Tokyo?",
        "Best time to visit Paris?",
        "Best time to visit Lisbon?",     # the 3rd failure opens the breaker
        "What food is Tokyo known for?",  # the breaker is open: no waiting, straight to backup
        "What currency does Paris use?",
    ]
    for question in questions:
        print(f"\nYOU: {question}")
        who, answer = await ask(question)
        print(f"[{who}] {answer}")


if __name__ == "__main__":
    asyncio.run(main())
