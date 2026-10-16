"""
=======================
STEP 1: Build TOOL 1 -- a tool that has its information INSIDE it.

The facts live in a Python dictionary (CITY_FACTS). No internet needed
for the tool itself. The agent can only reach this data through the tool.

Run it:   python step1_tool_with_data.py
"""
import asyncio
import os
from typing import Annotated

from dotenv import load_dotenv
from pydantic import Field
from azure.identity import AzureCliCredential
from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework.openai import OpenAIChatClient

# ---- 1. Load secret settings from the .env file ----
load_dotenv()

# Set USE_OPENAI=true in your .env file to use an OpenAI key instead of Azure.
USE_OPENAI = os.environ.get("USE_OPENAI", "false").lower() == "true"

# ---- 2. Connect to the AI model (the "brain") ----
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

# ---- 3. The information that lives INSIDE tool 1 ----
CITY_FACTS = {
    "paris": "Country: France. Currency: Euro. Best time to visit: April to June. Must try: croissants and cheese.",
    "tokyo": "Country: Japan. Currency: Yen. Best time to visit: March to May. Must try: sushi and ramen.",
    "lisbon": "Country: Portugal. Currency: Euro. Best time to visit: May to October. Must try: custard tarts.",
}


# ---- 4. TOOL 1: look up the facts we stored ----
@tool(approval_mode="never_require")
def get_city_facts(
    city: Annotated[str, Field(description="The city name, for example Paris")],
) -> str:
    """Get quick travel facts (country, currency, best season, food) for a city we have saved."""
    return CITY_FACTS.get(city.lower(), "Sorry, I have no saved facts for that city.")


# ---- 5. The agent: brain + instructions + tools ----
agent = Agent(
    client=client,
    name="TravelBuddy",
    instructions=(
        "You are Travel Buddy, a friendly travel helper. "
        "Use your tool to get facts instead of guessing. "
        "Answer in two or three sentences."
    ),
    tools=[get_city_facts],
)


# ---- 6. Ask a question ----
async def main():
    result = await agent.run("When is the best time to visit Lisbon?")
    print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
