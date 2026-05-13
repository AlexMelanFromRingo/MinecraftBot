"""Introspection-based method collector for the 004 parity tests.

Walks a `Bot` class (Python or accel) and produces a dict[name -> MethodSpec]
that the parity tests in test_bot_full_parity.py / test_method_signatures.py
diff against each other.

Filter rules:
* skip names starting with `_` (already private)
* skip names in `PYTHON_ONLY_METHODS`
* skip class-level helpers like `offline` (classmethod) — they don't need parity
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass

from minecraft_bot._parity_meta import PYTHON_ONLY_METHODS


@dataclass(frozen=True)
class MethodSpec:
    """Describes a public Bot method/property in a backend-agnostic shape."""

    name: str
    kind: str  # one of: "method", "async_method", "property"
    arity: int  # excluding self, including positional + keyword args
    param_names: tuple[str, ...]


def _classify(obj: object) -> str:
    """Return the kind label for one method/property descriptor."""
    if isinstance(obj, property) or _looks_like_getter(obj):
        return "property"
    if inspect.iscoroutinefunction(obj):
        return "async_method"
    return "method"


def _looks_like_getter(obj: object) -> bool:
    """pyo3 #[getter] descriptors are not `property` instances in CPython
    but they walk like one (no __call__, has __get__). Detect both."""
    if isinstance(obj, property):
        return True
    if hasattr(obj, "__get__") and not callable(obj):
        return True
    return False


def collect_public_methods(cls: type) -> dict[str, MethodSpec]:
    """Walk `cls.__dict__` collecting one MethodSpec per public symbol.

    Used by `tests/python/parity/test_bot_full_parity.py` (T012) to compare
    the Python reference's `Bot` against `minecraft_bot_accel.Bot`.
    """
    out: dict[str, MethodSpec] = {}
    # Walk MRO so inherited methods from mixins show up too. For pyo3
    # #[pyclass] the inheritance chain is shallow.
    seen: set[str] = set()
    for klass in cls.__mro__:
        for name, obj in vars(klass).items():
            if name in seen:
                continue
            if name.startswith("_"):
                continue
            if name in PYTHON_ONLY_METHODS:
                continue
            if isinstance(obj, (classmethod, staticmethod)):
                continue
            seen.add(name)
            kind = _classify(obj)
            arity, param_names = _signature_shape(obj, kind)
            out[name] = MethodSpec(
                name=name, kind=kind, arity=arity, param_names=param_names
            )
    return out


def _signature_shape(obj: object, kind: str) -> tuple[int, tuple[str, ...]]:
    """Best-effort signature introspection. pyo3 descriptors often don't
    expose `inspect.signature`, in which case we report (0, ())."""
    if kind == "property":
        return 0, ()
    try:
        sig = inspect.signature(obj)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0, ()
    params = [
        p for p in sig.parameters.values() if p.name not in ("self", "cls")
    ]
    return len(params), tuple(p.name for p in params)
