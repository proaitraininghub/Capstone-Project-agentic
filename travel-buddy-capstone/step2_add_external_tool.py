"""
step2_add_external_tool.py
==========================
STEP 2: Add TOOL 2 -- a tool that goes OUT to the internet.

Tool 1 (get_city_facts)   -> information is INSIDE our code.
Tool 2 (search_wikipedia) -> information comes from OUTSIDE, from a
                             real web service, through an API call.

Wikipedia's API is free and needs no key, so every student can run it.

Run it:   python step2_add_external_tool.py
"""
import asyncio
import os
from typing import Annotated

import requests
from dotenv import load_dotenv
from pydantic import Field
from azure.identity import AzureCliCredential
from agent_framework import Agent, tool
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

CITY_FACTS = {
    "paris": "Country: France. Currency: Euro. Best time to visit: April to June. Must try: croissants and cheese.",
    "tokyo": "Country: Japan. Currency: Yen. Best time to visit: March to May. Must try: sushi and ramen.",
    "lisbon": "Country: Portugal. Currency: Euro. Best time to visit: May to October. Must try: custard tarts.",
}


# TOOL 1 -- information INSIDE the code
@tool(approval_mode="never_require")
def get_city_facts(
    city: Annotated[str, Field(description="The city name, for example Paris")],
) -> str:
    """Get quick travel facts (country, currency, best season, food) for a city we have saved."""
    return CITY_FACTS.get(city.lower(), "Sorry, I have no saved facts for that city.")


# TOOL 2 -- information from OUTSIDE (a web API)
@tool(approval_mode="never_require")
def search_wikipedia(
    topic: Annotated[str, Field(description="What to look up, for example Eiffel Tower or Sagrada Familia")],
) -> str:
    """Search Wikipedia on the internet. Use this for any place, landmark or topic that is NOT in our saved city facts."""
    url = "https://en.wikipedia.org/w/api.php"
    settings = {
        "action": "query",
        "generator": "search",     # search for the topic...
        "gsrsearch": topic,
        "gsrlimit": 1,             # ...and keep only the best match
        "prop": "extracts",        # give us the article text...
        "exintro": 1,              # ...only the introduction...
        "explaintext": 1,          # ...as plain text...
        "exsentences": 3,          # ...3 sentences long
        "format": "json",
    }
    try:
        response = requests.get(url, params=settings, headers={"User-Agent": "TravelBuddyClassDemo/1.0"}, timeout=10)
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
        if not pages:
            return "Wikipedia found nothing for that topic."
        first_page = list(pages.values())[0]
        return f"{first_page['title']}: {first_page['extract']}"
    except Exception as error:
        return f"The search failed: {error}"


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


async def main():
    result = await agent.run("Tell me about the Eiffel Tower.")
    print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
