"""
step10_context_growth.py         (PART 3: Context Engineering - the problem)
=============================================================================
NEW IDEA: the AI has no memory of its own. Every time you ask something,
we send it the WHOLE conversation so far. So the text we send gets
longer and longer, and you pay for all of it, every single turn.

This file needs NO Azure connection. It simply counts how the size grows.
The next three steps show ways to keep it under control.

Run it:   python step10_context_growth.py
"""

# A pretend conversation between a traveller (user) and Travel Buddy (assistant)
TURNS = [
    ("user", "Hi! I'm Priya. I'm planning a trip and I'm allergic to peanuts."),
    ("assistant", "Nice to meet you, Priya! I'll keep the peanut allergy in mind. Where would you like to go?"),
    ("user", "I'm thinking about Tokyo in spring."),
    ("assistant", "Great choice. Spring, from March to May, is cherry blossom season."),
    ("user", "My budget is about 2000 dollars for the whole trip."),
    ("assistant", "That is workable for a week if you choose budget hotels."),
    ("user", "I also want to see some famous landmarks."),
    ("assistant", "Tokyo Tower and Senso-ji temple are popular choices."),
    ("user", "What about food?"),
    ("assistant", "Try sushi and ramen, and tell every restaurant about your allergy."),
]


def estimate_tokens(text):
    """A rough rule: 1 token is about 4 characters of English text."""
    return len(text) // 4


running_context = ""
for turn_number, (role, text) in enumerate(TURNS, start=1):
    running_context += f"{role}: {text}\n"
    print(f"After turn {turn_number:2d}: the AI must re-read about {estimate_tokens(running_context):4d} tokens")

print("\nThe size only ever goes UP. Imagine 500 turns...")
print("That costs more money, adds waiting time, and one day exceeds the model's limit.")
print("\nSteps 11 and 12 show two ways to keep it small. Step 13 remembers things across chats.")
