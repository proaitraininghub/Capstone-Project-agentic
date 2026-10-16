"""
step15_offline_eval.py           (PART 4: Offline Evaluation)
==============================================================
NEW IDEA: test the agent against a FIXED list of questions ("golden
cases") BEFORE you release it. Like a school exam for your agent.

Each test case is checked in TWO ways:
   1. TOOL CHECK   did the agent call the right tool? (plain Python, exact)
   2. JUDGE CHECK  does the answer meet the rule? (a second AI, the
                   "judge", reads the answer and says PASS or FAIL)

Run it:   python step15_offline_eval.py
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

# The judge: a separate agent whose only job is to grade answers
judge = Agent(
    client=client,
    name="Judge",
    instructions=(
        "You are a strict grader. You get a question, an answer, and a rule. "
        "Reply with PASS if the answer follows the rule, otherwise FAIL. "
        "Start your reply with PASS or FAIL, then give a one-sentence reason."
    ),
)

# The golden test cases
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


def tools_used_in(result):
    used = []
    for message in result.messages:
        for content in message.contents:
            if content.type == "function_call":
                used.append(content.name)
    return used


async def main():
    passed = 0

    for case in TEST_CASES:
        result = await agent.run(case["question"])
        used = tools_used_in(result)

        # CHECK 1: the right tool? (None means "no tool should be used")
        if case["expected_tool"] is None:
            tool_ok = len(used) == 0
        else:
            tool_ok = case["expected_tool"] in used

        # CHECK 2: ask the judge
        judge_prompt = f"Question: {case['question']}\nAnswer: {result.text}\nRule: {case['rule']}"
        verdict = (await judge.run(judge_prompt)).text
        answer_ok = verdict.strip().upper().startswith("PASS")

        case_ok = tool_ok and answer_ok
        passed += 1 if case_ok else 0

        print(f"\nQ: {case['question']}")
        print(f"   tool check  : {'OK' if tool_ok else 'WRONG'}  (used: {used or 'none'})")
        print(f"   judge check : {'OK' if answer_ok else 'WRONG'}  ({verdict.strip()})")
        print(f"   RESULT      : {'PASS' if case_ok else 'FAIL'}")

    print(f"\n=== SCORE: {passed} of {len(TEST_CASES)} test cases passed ===")
    print("Remember: the judge is also an AI, so it can be wrong too. Real test sets are much bigger.")


if __name__ == "__main__":
    asyncio.run(main())
