"""Connection lifecycle and reconnect policy.

This module currently exposes only :class:`ReconnectPolicy`; the
:class:`Connection` class itself (with its lifecycle methods, hooks, and
factory constructors) lands in Phase 3 (US1) per the implementation
plan. See ``contracts/python-api.md`` for the full target surface.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReconnectPolicy:
    """Exponential-backoff parameters for opt-in auto-reconnect.

    Per FR-007a, auto-reconnect is opt-in via ``Connection.offline(...,
    auto_reconnect=True, reconnect_policy=...)``. The default policy
    here is intentionally conservative: a few quick retries, capped delay.

    Fields:

    - ``max_attempts`` — number of retries before giving up and raising
      ``ProtocolError``. ``0`` disables retries even when
      ``auto_reconnect=True``.
    - ``initial_delay`` — seconds before the first retry.
    - ``max_delay`` — cap per-retry delay.
    - ``multiplier`` — exponential factor between retries.
    - ``jitter`` — fractional random jitter applied to each delay
      (``0`` means deterministic; ``0.25`` means ±25 %).
    """

    max_attempts: int = 5
    initial_delay: float = 1.0
    max_delay: float = 30.0
    multiplier: float = 2.0
    jitter: float = 0.25

    def __post_init__(self) -> None:
        if self.max_attempts < 0:
            raise ValueError(f"max_attempts must be >= 0 (got {self.max_attempts})")
        if self.initial_delay <= 0:
            raise ValueError(f"initial_delay must be > 0 (got {self.initial_delay})")
        if self.max_delay < self.initial_delay:
            raise ValueError(
                f"max_delay ({self.max_delay}) must be >= initial_delay ({self.initial_delay})"
            )
        if self.multiplier < 1.0:
            raise ValueError(f"multiplier must be >= 1.0 (got {self.multiplier})")
        if not 0.0 <= self.jitter < 1.0:
            raise ValueError(f"jitter must be in [0, 1) (got {self.jitter})")


__all__ = ["ReconnectPolicy"]
