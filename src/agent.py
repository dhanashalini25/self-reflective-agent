"""Self-Reflective Agent - generate, judge, critique, regenerate, and measure.

An LLM-as-judge scores the output against an explicit rubric and returns
concrete constraints rather than "do better". The loop stops on a plateau or a
cap, a revision that scores worse is discarded, and every attempt is logged so
"it improved" is a number rather than a claim.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from .llm import complete
from .logging_setup import log

METRICS = Path("reflection_metrics.jsonl")
MAX_REVISIONS = 3
PLATEAU_DELTA = 0.05
RUBRIC = ["correctness", "completeness", "clarity", "grounding"]
DEMO = "Explain what a dead-letter queue is to a junior engineer, in one paragraph."


class Judgement(BaseModel):
    scores: dict[str, float] = Field(default_factory=dict)
    critique: str = ""
    constraints: list[str] = Field(default_factory=list)

    @property
    def overall(self) -> float:
        return sum(self.scores.values()) / len(self.scores) if self.scores else 0.0


@dataclass
class Attempt:
    output: str
    judgement: Judgement

    @property
    def score(self) -> float:
        return self.judgement.overall


@dataclass
class Session:
    task: str
    attempts: list[Attempt] = field(default_factory=list)
    stopped_because: str = "revision_cap"

    def best(self) -> Attempt:
        return max(self.attempts, key=lambda a: a.score)

    def improvement(self) -> float:
        if len(self.attempts) < 2:
            return 0.0
        return round(self.best().score - self.attempts[0].score, 3)


JUDGE = (
    "Score the answer from 0 to 1 on " + ", ".join(RUBRIC) + ". "
    "Then give a short critique and up to three CONCRETE constraints the rewrite must satisfy "
    "(each an imperative sentence).\n"
    'Reply with ONE JSON object: {"scores": {...}, "critique": "...", "constraints": ["..."]}\n\n'
    "Task: {task}\n\nAnswer:\n{output}"
)


def generate(task: str, constraints: list[str]) -> str:
    if constraints:
        rules = "\n".join(f"- {c}" for c in constraints)
        task = f"{task}\n\nYour previous attempt was inadequate. Satisfy every constraint:\n{rules}"
    return complete([{"role": "user", "content": task}]).strip()


def judge(task: str, output: str) -> Judgement:
    raw = complete([{
        "role": "user",
        "content": JUDGE.replace("{task}", task).replace("{output}", output),
    }])
    match = re.search(r"\{.*\}", raw, re.S)
    try:
        j = Judgement.model_validate_json(match.group(0) if match else raw)
    except (ValidationError, ValueError, AttributeError) as err:
        log.warning("judge_unparseable", extra={"error": str(err)[:200]})
        return Judgement(scores={k: 0.5 for k in RUBRIC}, critique="judge output unparseable")

    j.scores = {k: float(j.scores.get(k, 0.5)) for k in RUBRIC}
    return j


def refine(task: str, max_revisions: int = MAX_REVISIONS) -> Session:
    session = Session(task=task)
    constraints: list[str] = []

    for i in range(max_revisions + 1):
        output = generate(task, constraints)
        judgement = judge(task, output)
        session.attempts.append(Attempt(output, judgement))

        log.info("attempt_scored", extra={"attempt": i, "score": round(judgement.overall, 3)})
        with METRICS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "task": task[:60], "attempt": i, "score": round(judgement.overall, 4),
            }) + "\n")

        if i:
            delta = judgement.overall - session.attempts[-2].score
            if delta < 0:
                session.stopped_because = "regression"
                log.info("regression_discarded", extra={"delta": round(delta, 3)})
                break
            if delta < PLATEAU_DELTA:
                session.stopped_because = "plateau"
                break

        constraints = judgement.constraints

    return session


def run(prompt: str) -> str:
    s = refine(prompt)
    best = s.best()
    return (
        f"{best.output}\n\n"
        f"[best of {len(s.attempts)} attempts | score {best.score:.2f} "
        f"| improvement {s.improvement():+.2f} | stopped: {s.stopped_because}]"
    )
