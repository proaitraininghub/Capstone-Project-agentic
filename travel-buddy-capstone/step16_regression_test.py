"""
step16_regression_test.py        (PART 4: Regression Testing)
==============================================================
NEW IDEA: this is why the test cases matter. Before you change the
agent's instructions, run the SAME tests on the OLD and NEW versions
and compare the scores. If the new one scores LOWER, you broke something.

The "improvement" below makes the agent more brief. It sounds harmless.
Watch what it breaks.

Run it:   python step16_regression_test.py
"""
import asyncio
import os

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

judge = Agent(
    client=client,
    name="Judge",
    instructions=(
        "You are a strict grader. You get a question, an answer, and a rule. "
        "Reply with PASS if the answer follows the rule, otherwise FAIL. "
        "Start your reply with PASS or FAIL, then give a one-sentence reason."
    ),
)

OLD_INSTRUCTIONS = (
    "You are Travel Buddy, a friendly travel helper. "
    "For cities we have saved, use get_city_facts. "
    "For anything else, use search_wikipedia. "
    "Never guess. Answer in two or three sentences."
)

# Someone wanted shorter answers, and changed the instructions...
NEW_INSTRUCTIONS = (
    "You are Travel Buddy. Reply in 4 words or fewer, no exceptions. "
    "For cities we have saved, use get_city_facts. "
    "For anything else, use search_wikipedia."
)

TEST_CASES = [
    {"question": "What is the best time to visit Tokyo?", "expected_tool": "get_city_facts",
     "rule": "The answer must say March to May."},
    {"question": "What currency does Paris use?", "expected_tool": "get_city_facts",
     "rule": "The answer must say Euro."},
    {"question": "Tell me about the Eiffel Tower.", "expected_tool": "search_wikipedia",
     "rule": "The answer must say it is a tower in Paris."},
    {"question": "Hello!", "expected_tool": None,
     "rule": "The answer must be a friendly greeting."},
]


async def score_version(instructions):
    """Build an agent with these instructions, run all test cases, return how many passed."""
    agent = Agent(
        client=client,
        name="TravelBuddy",
        instructions=instructions,
        tools=[get_city_facts, search_wikipedia],
    )

    passed = 0
    for case in TEST_CASES:
        result = await agent.run(case["question"])

        used = []
        for message in result.messages:
            for content in message.contents:
                if content.type == "function_call":
                    used.append(content.name)

        if case["expected_tool"] is None:
            tool_ok = len(used) == 0
        else:
            tool_ok = case["expected_tool"] in used

        judge_prompt = f"Question: {case['question']}\nAnswer: {result.text}\nRule: {case['rule']}"
        verdict = (await judge.run(judge_prompt)).text
        answer_ok = verdict.strip().upper().startswith("PASS")

        passed += 1 if (tool_ok and answer_ok) else 0
    return passed


async def main():
    print("Scoring the OLD instructions...")
    old_score = await score_version(OLD_INSTRUCTIONS)
    print(f"  OLD: {old_score} of {len(TEST_CASES)} passed")

    print("Scoring the NEW instructions...")
    new_score = await score_version(NEW_INSTRUCTIONS)
    print(f"  NEW: {new_score} of {len(TEST_CASES)} passed")

    if new_score < old_score:
        print("\nREGRESSION DETECTED. The new version is worse. Do NOT release it.")
    else:
        print("\nNo regression. The new version is at least as good.")


if __name__ == "__main__":
    asyncio.run(main())
