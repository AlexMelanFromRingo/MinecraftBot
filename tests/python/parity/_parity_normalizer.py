"""T014 — packet-trace normalizer + comparator for the 004 parity gate.

Strips/zeroes non-deterministic fields (transaction-ids, wall-clock
timestamps) before comparing two WireLog traces, and applies the narrow
tolerance whitelist defined in spec.md Clarifications Q4.

Q4 contract:
* Strict byte equality is required for every packet *except* a tiny
  explicit whitelist of timing-derived completion packets.
* For whitelisted packets, tolerance is **field-scoped**: only the
  named timing field may differ, and by at most +/-1 tick.
* Packet kind and payload (other fields) must always match exactly.

Adding a key to TOLERANT_PACKETS requires a code-review-visible
justification comment on the same line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Whitelist of packets where one named field may drift by +/-1 tick.
# Each key MUST carry a one-line justification — review board enforces.
TOLERANT_PACKETS: dict[str, list[str]] = {
    # dig completion: finish_break tick offset can drift +/-1 because
    # break_time = ceil(hardness * factor * 20.0) is sensitive to f64
    # ULP variance between compilers (research.md R-4).
    "finish_break": ["tick"],
    # eat completion: EntityStatus(24) arrives off the server's own
    # tick clock; we cannot lock-step with that from the client.
    "entity_status_eat_complete": ["tick"],
    # cooldown-expiry: same shape as eat completion (mob attack
    # cooldowns, ender pearl cooldown).
    "cooldown_expiry": ["tick"],
}

# Fields that are NEVER compared regardless of packet kind.
_NEVER_COMPARED: set[str] = {
    "transaction_id",
    "wall_clock_ms",
    "_capture_timestamp",
    "_send_seq",
}


@dataclass
class NormalizedPacket:
    """One packet after normalisation."""

    kind: str
    payload: dict[str, Any]
    captured_tick: int | None


@dataclass
class NormalizedTrace:
    """Sequence of normalised packets from one backend."""

    backend: str
    packets: list[NormalizedPacket]


@dataclass
class ParityDiff:
    """Result of comparing two NormalizedTrace objects."""

    ok: bool
    summary: str = ""
    diffs: list[str] = field(default_factory=list)


def normalize_trace(packets: list[dict[str, Any]], *, backend: str) -> NormalizedTrace:
    """Convert a raw WireLog packet list into a normalised trace.

    `packets` is a list of dicts, each with at minimum `kind` and
    `payload` keys. `payload` is itself a dict. Optional `tick` key
    on each packet records the dispatch tick (used for whitelist
    tolerance).
    """
    out: list[NormalizedPacket] = []
    for p in packets:
        kind = str(p["kind"])
        raw_payload = dict(p.get("payload", {}))
        for ignore in _NEVER_COMPARED:
            raw_payload.pop(ignore, None)
        captured_tick = p.get("tick")
        out.append(
            NormalizedPacket(
                kind=kind, payload=raw_payload, captured_tick=captured_tick
            )
        )
    return NormalizedTrace(backend=backend, packets=out)


def compare(trace_a: NormalizedTrace, trace_b: NormalizedTrace) -> ParityDiff:
    """Diff two normalised traces. Returns ok=True only if every
    packet matches under Q4 rules."""
    diffs: list[str] = []

    if len(trace_a.packets) != len(trace_b.packets):
        diffs.append(
            f"packet count mismatch: {trace_a.backend}={len(trace_a.packets)}, "
            f"{trace_b.backend}={len(trace_b.packets)}"
        )
        return ParityDiff(ok=False, summary="length mismatch", diffs=diffs)

    for i, (pa, pb) in enumerate(zip(trace_a.packets, trace_b.packets, strict=True)):
        if pa.kind != pb.kind:
            diffs.append(f"#{i} kind: {pa.kind} vs {pb.kind}")
            continue

        tolerant_fields = TOLERANT_PACKETS.get(pa.kind, [])

        # Compare payloads minus the tolerant fields.
        strict_a = {k: v for k, v in pa.payload.items() if k not in tolerant_fields}
        strict_b = {k: v for k, v in pb.payload.items() if k not in tolerant_fields}
        if strict_a != strict_b:
            diffs.append(
                f"#{i} {pa.kind}: strict payload differs\n"
                f"      {trace_a.backend}: {strict_a}\n"
                f"      {trace_b.backend}: {strict_b}"
            )
            continue

        # Compare tolerant fields with +/-1 tolerance.
        for fld in tolerant_fields:
            va = pa.payload.get(fld)
            vb = pb.payload.get(fld)
            if va is None or vb is None:
                # If either side is missing the field, that's a bug.
                diffs.append(f"#{i} {pa.kind}: tolerant field {fld} missing")
                continue
            if abs(int(va) - int(vb)) > 1:
                diffs.append(
                    f"#{i} {pa.kind}: tolerant field {fld} differs by "
                    f"{abs(int(va) - int(vb))} (> 1 tick budget): "
                    f"{trace_a.backend}={va}, {trace_b.backend}={vb}"
                )

    return ParityDiff(
        ok=not diffs,
        summary="parity ok" if not diffs else f"{len(diffs)} diff(s)",
        diffs=diffs,
    )
