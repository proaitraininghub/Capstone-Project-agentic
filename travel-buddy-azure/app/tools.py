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

import os

import requests
from pydantic import Field
from agent_framework import tool

from redis_util import get_sync

WIKI_CACHE_TTL = int(os.environ.get("WIKI_CACHE_TTL", "3600"))  # seconds. 0 turns the cache off

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
    # CACHE: if anybody asked for this topic recently, reuse the saved text.
    # With many users this saves most web calls and keeps us inside Wikipedia's fair-use limits.
    cache_key = "tb:wiki:" + " ".join(topic.lower().split())
    cache = get_sync() if WIKI_CACHE_TTL > 0 else None
    if cache is not None:
        try:
            saved = cache.get(cache_key)
            if saved:
                return saved
        except Exception:
            pass  # if Redis is down, just carry on without the cache

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
        text = f"{first_page['title']}: {first_page['extract']}"
        if cache is not None:
            try:
                cache.set(cache_key, text, ex=WIKI_CACHE_TTL)  # only good answers are saved
            except Exception:
                pass
        return text
    except Exception as error:
        return f"The search failed: {error}"
