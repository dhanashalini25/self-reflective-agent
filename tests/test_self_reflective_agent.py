import pytest

from src import agent
from src.agent import (
    MAX_REVISIONS, PLATEAU_DELTA, RUBRIC, Attempt, Judgement, Session, judge, refine,
)


@pytest.fixture(autouse=True)
def metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "METRICS", tmp_path / "metrics.jsonl")


def judgement(score: float, constraints=None) -> str:
    body = ", ".join(f'"{k}": {score}' for k in RUBRIC)
    cons = constraints or ["Add a concrete example."]
    return '{"scores": {%s}, "critique": "c", "constraints": %s}' % (
        body, str(cons).replace("'", '"')
    )


def test_overall_is_mean_of_rubric():
    j = Judgement(scores={"correctness": 1.0, "clarity": 0.0})
    assert j.overall == 0.5


def test_best_picks_highest_score():
    s = Session(task="t", attempts=[
        Attempt("low", Judgement(scores={"a": 0.2})),
        Attempt("high", Judgement(scores={"a": 0.9})),
    ])
    assert s.best().output == "high"


def test_judge_parses_scores(monkeypatch):
    monkeypatch.setattr(agent, "complete", lambda m, **k: judgement(0.8))
    j = judge("task", "answer")
    assert j.overall == pytest.approx(0.8)
    assert j.constraints


def test_judge_survives_garbage(monkeypatch):
    monkeypatch.setattr(agent, "complete", lambda m, **k: "looks fine to me")
    j = judge("task", "answer")
    assert set(j.scores) == set(RUBRIC)


def test_constraints_reach_the_regenerator(monkeypatch):
    seen = []
    scores = iter([0.4, 0.9, 0.9])

    def fake(messages, **kwargs):
        content = messages[-1]["content"]
        if content.startswith("Score the answer"):
            return judgement(next(scores), ["Name a specific failure case."])
        seen.append(content)
        return "an answer"

    monkeypatch.setattr(agent, "complete", fake)
    refine("explain dead letter queues")
    assert any("Name a specific failure case." in s for s in seen)


def test_improvement_is_measured(monkeypatch):
    scores = iter([0.4, 0.9, 0.9])

    def fake(messages, **kwargs):
        if messages[-1]["content"].startswith("Score the answer"):
            return judgement(next(scores))
        return "an answer"

    monkeypatch.setattr(agent, "complete", fake)
    s = refine("task")
    assert s.improvement() == pytest.approx(0.5)


def test_plateau_stops_the_loop(monkeypatch):
    monkeypatch.setattr(agent, "complete", lambda m, **k: (
        judgement(0.7) if m[-1]["content"].startswith("Score the answer") else "same answer"
    ))
    s = refine("task")
    assert s.stopped_because == "plateau"
    assert len(s.attempts) < MAX_REVISIONS + 1


def test_regression_is_discarded(monkeypatch):
    scores = iter([0.9, 0.2])

    def fake(messages, **kwargs):
        if messages[-1]["content"].startswith("Score the answer"):
            return judgement(next(scores))
        return "answer " + str(len(list()))

    monkeypatch.setattr(agent, "complete", fake)
    s = refine("task")
    assert s.stopped_because == "regression"
    assert s.best().score == pytest.approx(0.9)


def test_revision_cap_is_respected(monkeypatch):
    n = {"i": 0}

    def climbing(messages, **kwargs):
        if messages[-1]["content"].startswith("Score the answer"):
            n["i"] += 1
            return judgement(min(0.1 * n["i"], 1.0))
        return "answer"

    monkeypatch.setattr(agent, "complete", climbing)
    s = refine("task", max_revisions=2)
    assert len(s.attempts) == 3


def test_metrics_are_written(monkeypatch):
    monkeypatch.setattr(agent, "complete", lambda m, **k: (
        judgement(0.7) if m[-1]["content"].startswith("Score the answer") else "answer"
    ))
    refine("task")
    assert agent.METRICS.exists() and agent.METRICS.read_text(encoding="utf-8").strip()


def test_plateau_delta_is_sane():
    assert 0 < PLATEAU_DELTA < 1
