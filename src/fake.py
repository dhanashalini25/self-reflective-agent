"""Canned generator and judge for MODEL=fake: scores climb, then plateau."""
from __future__ import annotations

_state = {"gen": 0, "judge": 0}
SCORES = [0.55, 0.78, 0.80, 0.81]


def reset() -> None:
    _state.update(gen=0, judge=0)


def respond(messages: list[dict]) -> str:
    content = messages[-1]["content"]

    if content.startswith("Score the answer"):
        i = min(_state["judge"], len(SCORES) - 1)
        s = SCORES[i]
        _state["judge"] += 1
        return (
            '{"scores": {"correctness": %.2f, "completeness": %.2f, "clarity": %.2f, '
            '"grounding": %.2f}, "critique": "Needs a concrete example and a failure case.", '
            '"constraints": ["Name a specific failure that sends a message to the queue.", '
            '"Give one sentence on how messages are replayed."]}' % (s, s, s, s)
        )

    _state["gen"] += 1
    if _state["gen"] == 1:
        return "A dead-letter queue holds messages that failed."
    return (
        "A dead-letter queue holds messages your system could not process after every retry - "
        "say a webhook whose handler kept throwing because a downstream service was down. "
        "Instead of losing the event or retrying forever, it is parked with its payload and "
        "error history, and replayed once the bug is fixed."
    )
