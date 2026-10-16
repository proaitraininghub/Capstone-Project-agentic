# Travel Buddy Capstone: Parts 2, 3 and 4 Added One Step at a Time

You built Travel Buddy: an agent with two tools (facts stored in code, and a Wikipedia search).
This repo keeps that agent and adds **one new idea per file**, in the same order as the course.

## How this repo is designed

1. **One step = one file = one new idea.** Each file starts with a short docstring saying what is new, which course part it comes from, and how to run it.
2. **Every file runs by itself.** Run any step on its own, in any order.
3. **The agent is always built the same way, right in the file:** load settings, create the `client`, create the `Agent` with instructions and tools, then ask a question. There are no hidden helper functions.
4. **The two tools live in `tools.py`.** They are unchanged from the project, and each new file imports them so it can focus on the new idea. Steps 1 to 3 keep the tools inline, as you first wrote them.
5. **Steps that need no AI model at all** (10 and 18) just print numbers, so you can show them anywhere.

## The steps

| Step | File | New idea | From |
|------|------|----------|------|
| 1 | `step1_tool_with_data.py` | Tool 1: data inside the code | Project |
| 2 | `step2_add_external_tool.py` | Tool 2: call a web API | Project |
| 3 | `step3_chat_app.py` | Chat loop that prints the messages | Project |
| 4 | `step4_cost_and_latency.py` | Measure time, tokens, cost; streaming | Part 2: Cost and Latency |
| 5 | `step5_retry_and_timeout.py` | Timeout and retry with backoff | Part 2: Reliability |
| 6 | `step6_tracing.py` | Write a trace of every call | Part 2: Observability |
| 7 | `step7_fallback_and_circuit_breaker.py` | Backup agent and circuit breaker | Part 2: Failure Handling |
| 8 | `step8_guardrails.py` | Check input before, output after | Part 2: Safety and Guardrails |
| 9 | `step9_parallel_specialists.py` | Three specialists in parallel | Part 2: Orchestration (Concurrent) |
| 10 | `step10_context_growth.py` | Why the prompt keeps growing (no Azure) | Part 3: Context Engineering |
| 11 | `step11_sliding_window.py` | Keep only the last few turns | Part 3: Compression |
| 12 | `step12_summary_buffer.py` | Summarize old turns, keep recent ones | Part 3: Compression |
| 13 | `step13_long_term_memory.py` | Remember facts across chats with a context provider | Part 3: Memory Types |
| 14 | `step14_nondeterminism.py` | Same question, different answers | Part 4: Why Evaluate |
| 15 | `step15_offline_eval.py` | Golden test cases: tool check + AI judge | Part 4: Offline Evaluation |
| 16 | `step16_regression_test.py` | Compare old and new instructions | Part 4: Regression Testing |
| 17 | `step17_online_sampling.py` | Judge a random sample of live traffic | Part 4: Online Evaluation |
| 18 | `step18_drift_detection.py` | Alert when weekly scores fall (no Azure) | Part 4: Drift Detection |

## Choose your AI provider: OpenAI or Azure

Every step that talks to an AI model has both options built in. You switch with ONE line in your `.env` file, and you do not edit any code:

| `.env` setting | Provider | What you need |
|----------------|----------|---------------|
| `USE_OPENAI=true` | **OpenAI** | `OPENAI_API_KEY` and `OPENAI_MODEL` (for example `gpt-4.1-mini`). No Azure, no `az login` |
| `USE_OPENAI=false` (or the line removed) | **Azure AI Foundry** | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_CHAT_DEPLOYMENT`, and `az login` |

In the code, each file has the same small block, so students can read both options:

```python
if USE_OPENAI:
    # OPTION B: OpenAI (uses your OPENAI_API_KEY)
    client = OpenAIChatClient(api_key=os.environ["OPENAI_API_KEY"], model=os.environ["OPENAI_MODEL"])
else:
    # OPTION A: Azure AI Foundry (uses az login)
    client = FoundryChatClient(project_endpoint=..., model=..., credential=AzureCliCredential())
```

Everything after that block, the tools, the agent, and the messages, is identical for both providers.

**Keep your key private.** Put it only in `.env` (already in `.gitignore`). Never paste it into a code file or commit it to GitHub.

## Setup (PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then fill in your values (set USE_OPENAI=true for OpenAI)
az login                    # only needed for the Azure option
python step3_chat_app.py
```

Optional in `.env`: a second model for step 7's backup agent (`OPENAI_FALLBACK_MODEL` or `AZURE_OPENAI_FALLBACK_DEPLOYMENT`). If you leave it out, the backup uses the same model.

## What to expect and what to point out

- **Step 4:** token numbers come from the model's usage report. If they show 0, your setup did not report usage. The prices in the file are examples; replace them with your model's real prices.
- **Step 5:** the first two attempts fail on purpose. You will see "Waiting 1s", then "Waiting 2s", then the answer.
- **Step 6:** open `traces.jsonl` afterwards. Each line is one record.
- **Step 7:** the main model is made to fail on purpose (`MAIN_MODEL_IS_DOWN = True`). The third failure opens the breaker, and later questions skip straight to the backup. Set the flag to `False` for normal behaviour.
- **Step 8:** the first question passes. The next two are blocked before the agent. The last line tests the output checkpoint directly.
- **Steps 11 and 12:** same question, same conversation. The sliding window forgets the allergy and budget; the summary buffer remembers them.
- **Step 13:** creates `memory_store.json`. The second chat is a brand new session, yet it knows the name and allergy.
- **Step 16:** the new instructions ("reply in 4 words or fewer") should score lower than the old ones. AI answers vary, so if both score the same on your run, make the new instructions stricter or add test cases.
- **Steps 15 to 17:** the judge is also an AI and can be wrong. This is why real test sets are much larger.

## Not covered here

The official Azure AI Evaluation SDK (Intent Resolution, Task Adherence, Tool Call Accuracy evaluators) from Part 4 section 2.2, and the Handoff, Group Chat and Magentic builders from Part 2. They are good next steps once the hand-built versions make sense.


Updates are made.. 