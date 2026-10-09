# AI-written by OpenAI Codex, for issue #21.
"""Optional aggregate timings of actual scans; no feature explanations or caches."""
from collections.abc import Callable
from time import perf_counter_ns
from typing import Any, TypeVar

T = TypeVar('T')


class EvaluationProfile:
    def __init__(self, every: int) -> None:
        self.every = every
        self.sampled_calls = 0
        self.families: dict[str, dict[str, int]] = {}
        self.instrumentation_bookkeeping_ns = 0

    def measure(self, name: str, operation: Callable[[], T]) -> T:
        overhead_start = perf_counter_ns()
        record = self.families.setdefault(name, {'calls': 0, 'completed': 0,
                                                'incomplete': 0, 'elapsed_ns': 0})
        record['calls'] += 1
        start = perf_counter_ns()
        self.instrumentation_bookkeeping_ns += start - overhead_start
        completed = False
        try:
            value = operation()
            completed = True
            return value
        finally:
            end = perf_counter_ns()
            record['elapsed_ns'] += end - start
            record['completed' if completed else 'incomplete'] += 1
            self.instrumentation_bookkeeping_ns += perf_counter_ns() - end

    def snapshot(self) -> dict[str, Any]:
        return {'every': self.every, 'sampled_calls': self.sampled_calls,
                'families': {name: dict(values) for name, values in self.families.items()},
                'instrumentation_bookkeeping_ns': self.instrumentation_bookkeeping_ns,
                'overhead_scope': 'measured bookkeeping only; timer/call dispatch excluded; '
                                  'use paired uninstrumented runs for total overhead'}
