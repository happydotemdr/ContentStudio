"""IterationRecord enforces the 2-attempts-per-track budget and records the
settings/metrics diff between attempts, per the design's iteration/proof
harness. .compare() states directional consistency, not causal proof --
neither ElevenLabs nor Eleven Music generation is fully deterministic
run-to-run, so a contradicted direction is reported as a finding, never
silently retried past the hard 2-attempt cap."""

from __future__ import annotations

from dataclasses import dataclass, field

from native_pipeline.errors import IterationBudgetExceededError

MAX_ATTEMPTS = 2


@dataclass
class Attempt:
    settings: dict
    metrics: dict


@dataclass
class IterationRecord:
    track: str
    attempts: list[Attempt] = field(default_factory=list)

    def record(self, settings: dict, metrics: dict) -> None:
        if len(self.attempts) >= MAX_ATTEMPTS:
            raise IterationBudgetExceededError(f"{self.track}: attempt budget of {MAX_ATTEMPTS} already spent")
        self.attempts.append(Attempt(settings=settings, metrics=metrics))

    def compare(self, metric_key: str, expected_direction: str) -> dict:
        if len(self.attempts) < 2:
            raise ValueError(f"{self.track}: need 2 attempts to compare, have {len(self.attempts)}")

        first, second = self.attempts[0], self.attempts[1]
        settings_diff = {
            key: (first.settings.get(key), second.settings.get(key))
            for key in set(first.settings) | set(second.settings)
            if first.settings.get(key) != second.settings.get(key)
        }
        delta = second.metrics[metric_key] - first.metrics[metric_key]
        directionally_consistent = delta > 0 if expected_direction == "up" else delta < 0

        return {
            "track": self.track,
            "settings_diff": settings_diff,
            "metric_key": metric_key,
            "delta": delta,
            "expected_direction": expected_direction,
            "directionally_consistent": directionally_consistent,
        }
