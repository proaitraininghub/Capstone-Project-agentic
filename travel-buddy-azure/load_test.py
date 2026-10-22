"""
load_test.py  --  "WILL IT HOLD UP FOR 500 USERS?"  Measure it instead of guessing.

   python load_test.py https://YOUR-APP-URL --users 100 --messages 3

What it does: starts N pretend users at the same time. Each user sends a few questions,
one after the other (like a real chat), waits for every answer, and records how long it took.
At the end it prints how many worked, how many were refused, and the speed.

READ THE RESULT LIKE THIS
   OK                 answers that came back
   Rate limited (429) refused by YOUR per-user limit (the protection is working)
   Failed             the model or worker had a problem  -> look at worker logs and model quota
   Cached             answered from Redis, with no model call  (free and instant)
   p50 / p95          half of the answers were faster than p50; 95 percent were faster than p95

HOW TO RAISE THE LOAD SLOWLY:  --users 10, then 50, then 100, then 250, then 500.
WATCH WHILE IT RUNS:  Container Apps -> your worker -> Replicas  (it should grow as the queue grows)
                      Foundry -> Deployments -> your model -> Metrics (watch for 429s)

COST WARNING: every uncached question calls the model and costs money. Start small.
Use different questions per user (the default) to bypass the cache, or --same-question to test it.

Needs:  pip install httpx
"""
import argparse
import asyncio
import random
import statistics
import time

import httpx

QUESTIONS = [
    "Best time to visit {}?", "What should I eat in {}?", "What currency is used in {}?",
    "Tell me about the {} landmark", "Is {} good for families?",
]
PLACES = ["Paris", "Tokyo", "Lisbon", "Rome", "Barcelona", "Kyoto", "Prague", "Vienna", "Sydney", "Cairo"]

results = []   # (outcome, seconds)


async def one_user(client, base, user_no, messages, same_question, think_time):
    headers = {"X-User-Id": f"load-user-{user_no}"}
    session_id = None
    for n in range(messages):
        if same_question:
            text = "Best time to visit Tokyo?"
        else:
            text = random.choice(QUESTIONS).format(random.choice(PLACES)) + f" (user {user_no}, q{n})"
        started = time.perf_counter()
        try:
            r = await client.post(f"{base}/chat", json={"message": text, "session_id": session_id}, headers=headers)
            if r.status_code == 429:
                results.append(("rate_limited", time.perf_counter() - started))
                await asyncio.sleep(int(r.headers.get("retry-after", "5")))
                continue
            r.raise_for_status()
            body = r.json()
            session_id = body["session_id"]
            outcome = "cached" if body.get("cached") else "ok"
            task_id = body["task_id"]
            while body["status"] not in ("done", "failed"):
                await asyncio.sleep(1)
                body = (await client.get(f"{base}/chat/{task_id}")).json()
                if time.perf_counter() - started > 120:
                    body["status"] = "failed"
            if body["status"] == "failed":
                outcome = "failed"
            results.append((outcome, time.perf_counter() - started))
        except Exception:
            results.append(("failed", time.perf_counter() - started))
        await asyncio.sleep(random.uniform(0, think_time))   # the person reads and types


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--users", type=int, default=20)
    p.add_argument("--messages", type=int, default=3)
    p.add_argument("--ramp", type=float, default=10, help="spread the user starts over this many seconds")
    p.add_argument("--think", type=float, default=5, help="max seconds a user waits between messages")
    p.add_argument("--same-question", action="store_true", help="everybody asks the same first question (tests the cache)")
    a = p.parse_args()
    base = a.url.rstrip("/")

    limits = httpx.Limits(max_connections=a.users + 10)
    async with httpx.AsyncClient(timeout=30, limits=limits) as client:
        started = time.perf_counter()

        async def delayed(i):
            await asyncio.sleep(random.uniform(0, a.ramp))
            await one_user(client, base, i, a.messages, a.same_question, a.think)

        await asyncio.gather(*(delayed(i) for i in range(a.users)))
        total = time.perf_counter() - started

    print(f"\n{a.users} users x {a.messages} messages in {total:.0f}s")
    for outcome in ("ok", "cached", "rate_limited", "failed"):
        times = sorted(t for o, t in results if o == outcome)
        if times:
            p50 = statistics.median(times)
            p95 = times[int(len(times) * 0.95) - 1] if len(times) > 1 else times[0]
            print(f"  {outcome:13} {len(times):5}   p50 {p50:6.1f}s   p95 {p95:6.1f}s")
    done = sum(1 for o, _ in results if o in ("ok", "cached"))
    print(f"  throughput: {done / total * 60:.0f} answered messages per minute")


asyncio.run(main())
