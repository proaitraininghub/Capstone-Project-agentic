"""
step3_chat_app.py  --  TRAVEL BUDDY (the base project)
=============================================
A chat assistant with TWO tools:

   Tool 1  get_city_facts    information stored INSIDE our code
   Tool 2  search_wikipedia  information fetched from the INTERNET

After every answer the program prints the MESSAGES that were exchanged,
so you can SEE the agent decide which tool to use.

Run it:   python step3_chat_app.py        (type quit to stop)
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

# ------------------------------------------------------------------
# PART 1: SETTINGS AND CLIENT
# ------------------------------------------------------------------
load_dotenv()                      # read the .env file

# Set USE_OPENAI=true in your .env file to use an OpenAI key instead of Azure.
USE_OPENAI = os.environ.get("USE_OPENAI", "false").lower() == "true"

# The client = the connection to the AI model
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

# ------------------------------------------------------------------
# PART 2: TOOL 1 -- information INSIDE the code
# ------------------------------------------------------------------
CITY_FACTS = {
    "paris": "Country: France. Currency: Euro. Best time to visit: April to June. Must try: croissants and cheese.",
    "tokyo": "Country: Japan. Currency: Yen. Best time to visit: March to May. Must try: sushi and ramen.",
    "lisbon": "Country: Portugal. Currency: Euro. Best time to visit: May to October. Must try: custard tarts.",
}


@tool(approval_mode="never_require")
def get_city_facts(
    city: Annotated[str, Field(description="The city name, for example Paris")],
) -> str:
    """Get quick travel facts (country, currency, best season, food) for a city we have saved."""
    return CITY_FACTS.get(city.lower(), "Sorry, I have no saved facts for that city.")


# ------------------------------------------------------------------
# PART 3: TOOL 2 -- information from OUTSIDE (a web API)
# ------------------------------------------------------------------
@tool(approval_mode="never_require")
def search_wikipedia(
    topic: Annotated[str, Field(description="What to look up, for example Eiffel Tower or Sagrada Familia")],
) -> str:
    """Search Wikipedia on the internet. Use this for any place, landmark or topic that is NOT in our saved city facts."""
    url = "https://en.wikipedia.org/w/api.php"
    settings = {
        "action": "query",
        "generator": "search",
        "gsrsearch": topic,
        "gsrlimit": 1,
        "prop": "extracts",
        "exintro": 1,
        "explaintext": 1,
        "exsentences": 3,
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


# ------------------------------------------------------------------
# PART 4: THE AGENT = brain (client) + instructions + tools
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# PART 5: SHOW THE MESSAGES (what really happened inside)
# ------------------------------------------------------------------
def show_messages(result):
    print("   --- messages exchanged ---")
    for message in result.messages:
        for content in message.contents:
            if content.type == "function_call":
                print(f"   [{message.role}] asks for tool: {content.name}({content.arguments})")
            elif content.type == "function_result":
                print(f"   [{message.role}] tool answered: {content.result}")
            elif content.type == "text":
                print(f"   [{message.role}] final answer: {content.text}")


# ------------------------------------------------------------------
# PART 6: THE CHAT LOOP
# ------------------------------------------------------------------
async def main():
    session = agent.create_session()      # lets the agent remember the chat
    print("Travel Buddy is ready. Try: 'Best time to visit Tokyo?' or 'What is the Colosseum?'")
    print("Type 'quit' to stop.\n")

    while True:
        question = input("YOU: ")
        if question.strip().lower() == "quit":
            break

        result = await agent.run(question, session=session)
        print(f"\nTRAVEL BUDDY: {result.text}\n")
        show_messages(result)
        print()


if __name__ == "__main__":
    asyncio.run(main())
