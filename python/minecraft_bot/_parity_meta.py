"""Parity metadata — explicit allow-lists consumed by the 004 parity
test infrastructure (T011..T013).

These are intentionally Python-only; the Rust crate and accel facade
do not need a mirror.
"""

from __future__ import annotations

# Bot methods that are intentionally Python-only and must NOT exist on
# `minecraft_bot_accel.Bot`. The introspection test (T012) excludes
# them from the symmetric-difference check. Each entry needs a one-line
# justification in the comment above it, with a code-review trail.
#
# The LLM agent depends on external LLM API clients (anthropic, openai,
# etc.) which would violate Constitution VI if we re-exported them from
# the Rust crate. Keeping the loop and observation hooks Python-only is
# the intentional design.
PYTHON_ONLY_METHODS: frozenset[str] = frozenset({
    "_llm_chat_loop",
    "_llm_observe",
})

# Type-mapping rules consulted by `test_method_signatures.py` (T013).
# Maps a Python-side annotation to the set of accel-side annotations
# that are considered equivalent.
SIGNATURE_TYPE_EQUIVALENTS: dict[str, set[str]] = {
    "float": {"float", "f64", "f32"},
    "int": {"int", "i32", "i64", "u8", "u32", "u64"},
    "bool": {"bool"},
    "str": {"str", "String"},
    "bytes": {"bytes", "Vec<u8>"},
    "ItemSlot | None": {"ItemSlot | None", "Optional[ItemSlot]"},
    "tuple[float, float, float]": {"tuple[float, float, float]"},
}
