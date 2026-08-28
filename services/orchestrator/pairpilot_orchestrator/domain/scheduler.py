"""Bounded scheduler primitive that cannot replay a semantic demo sequence."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class SchedulerResult:
    turns: int
    retries: int
    termination_reason: str


class BoundedScheduler:
    def __init__(self, *, max_turns: int = 12, max_retries: int = 2) -> None:
        self.max_turns = max_turns
        self.max_retries = max_retries

    def run(self, runnable_turn: Callable[[], bool | None]) -> SchedulerResult:
        turns = 0
        retries = 0
        while turns < self.max_turns:
            result = runnable_turn()
            turns += 1
            if result is True:
                return SchedulerResult(turns, retries, "terminal_state")
            if result is None:
                retries += 1
                if retries > self.max_retries:
                    return SchedulerResult(turns, retries, "agent_nonresponsive")
            else:
                retries = 0
        return SchedulerResult(turns, retries, "bounded_no_match")

