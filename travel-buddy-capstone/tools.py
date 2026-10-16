"""
tools.py
========
The two tools you built in the project. They are unchanged.
From step 4 onward we import them from here, so each new file can
focus on the NEW idea instead of repeating the tools.

   Tool 1  get_city_facts    information stored INSIDE our code
   Tool 2  search_wikipedia  information fetched from the INTERNET
"""
from typing import Annotated

import requests
from pydantic import Field
from agent_framework import tool

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
