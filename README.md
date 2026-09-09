# 10 - Self-Reflective Agent with Auto-Eval

> Answer, judge, critique, rewrite - and measure whether it improved.

**What it demonstrates:** Iterative self-improvement with bounds and evidence

**Status:** working implementation with passing tests. Built as a learning project to understand the pattern, not as a production service.

---

## Run it right now

No API key needed - every project ships with `MODEL=fake`, a deterministic
offline responder, so you can see the whole flow work before spending anything.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
python -m src.main
pytest -q
```

To use a real model, edit `.env`:

```
MODEL=gpt-4o-mini            # + OPENAI_API_KEY
MODEL=claude-3-5-haiku-latest  # + ANTHROPIC_API_KEY
MODEL=ollama/llama3.1        # free, runs locally
```

## How it works

An LLM-as-judge scores each answer on a four-dimension rubric and returns not just a critique but a list of **concrete constraints** - imperative sentences the rewrite must satisfy. Those constraints are injected into the next generation, which is what turns vague self-criticism into a specific edit.

The loop is bounded three ways: a revision cap, a plateau check (improvement below `PLATEAU_DELTA` stops it), and a regression check (a worse revision stops it immediately and the original is kept, because `best()` selects by score rather than recency).

Every attempt is appended to `reflection_metrics.jsonl`, so 'it got better' is a number you can plot rather than an impression.

## What "done" means here

- The judge returns structured rubric scores and survives garbage output
- Critique becomes concrete constraints, and those constraints reach the rewrite
- Improvement is measured per attempt and persisted to disk
- A plateau stops the loop instead of burning tokens
- A worse revision is discarded and the better original returned
- The revision cap is enforced

Every one of those lines has a test behind it in `tests/` - `pytest -q` is the
proof, not the README.

## Layout

```
src/llm.py             provider-agnostic completion, plus offline fake mode
src/fake.py            the canned responses that make MODEL=fake work
src/logging_setup.py   structured JSON logging
src/agent.py           the pattern itself
src/main.py            CLI entrypoint
tests/                 11 tests, all passing
```

## Next steps

- Use a different model as judge than as generator and see whether scores change
- Keep a lesson store so past critiques inform the first attempt next time
- Check the judge against human ratings before trusting the numbers

## Reference

https://github.com/noahshinn/reflexion

---

Part of a 12-project agentic AI series - [github.com/dhanashalini25](https://github.com/dhanashalini25?tab=repositories)
