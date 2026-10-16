"""
step6_tracing.py                 (PART 2: Operability and Observability)
=====================================================================
NEW IDEA: when something goes wrong at 2 AM, nobody is watching the
screen. A TRACE is a written record of what happened: what was asked,
which tools ran, how long it took, and whether it worked.

We write a tiny tracer by hand so you can see what a trace looks like.
(In real production you would use OpenTelemetry + Application Insights,
which record the same kind of information automatically.)

Run it:   python step6_tracing.py        then open traces.jsonl
"""
import asyncio
import json
import os
import time
from contextlib import asynccontextmanager

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


@asynccontextmanager
async def span(name, **details):
    """Wrap any piece of work. It records the name, the details, how long it took, and ok/error."""
    record = {"span": name, "details": details, "status": "ok"}
    start = time.time()
    try:
        yield record                       # your work runs here; you can add more details to `record`
    except Exception as error:
        record["status"] = "error"
        record["error"] = str(error)
        raise
    finally:
        record["seconds"] = round(time.time() - start, 2)
        line = json.dumps(record)
        print(f"TRACE: {line}")
        with open("traces.jsonl", "a") as file:    # keep a permanent log
            file.write(line + "\n")


async def ask(question):
    async with span("agent.run", question=question) as record:
        result = await agent.run(question)

        tools_used = []
        for message in result.messages:
            for content in message.contents:
                if content.type == "function_call":
                    tools_used.append(content.name)

        record["tools_used"] = tools_used          # add facts to the trace
        record["answer_length"] = len(result.text)
        return result


async def main():
    for question in ["Best time to visit Paris?", "Tell me about the Colosseum.", "Hello!"]:
        result = await ask(question)
        print(f"ANSWER: {result.text}\n")
    print("Open traces.jsonl to see the saved records.")


if __name__ == "__main__":
    asyncio.run(main())
