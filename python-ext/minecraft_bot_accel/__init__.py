"""minecraft_bot_accel — native-speed alternative to ``minecraft_bot``.

The user-visible Python surface mirrors ``minecraft_bot`` one-for-one,
delegating each call into the PyO3-bound Rust crate.

Constitution VI: this package is a **separate distributable** from
``minecraft_bot``. It MUST NOT be imported by the Python reference.
"""

from __future__ import annotations

import sys as _sys

# Pull the cdylib symbols up to the package root.
from . import minecraft_bot_accel as _native  # noqa: F401

# Re-export identity attributes registered on the cdylib by
# ``python-ext/src/version.rs``.
__version__ = _native.__version__
python_compat = _native.python_compat
implementation = _native.implementation

# Re-export every top-level symbol (classes, submodules) registered on
# the cdylib root.
for _name in dir(_native):
    if _name.startswith("_") or _name == "minecraft_bot_accel":
        continue
    globals()[_name] = getattr(_native, _name)


# Register native submodules under their full dotted path so
# ``from minecraft_bot_accel.codec import Reader`` works.
for _sub in ("errors", "codec", "framer", "world", "pathfinding", "physics",
             "observation", "entities", "effects"):
    _mod = getattr(_native, _sub, None)
    if _mod is not None:
        _sys.modules[f"minecraft_bot_accel.{_sub}"] = _mod

# Sub-sub-modules under codec (varint, varlong, …) — same trick.
_codec_native = getattr(_native, "codec", None)
if _codec_native is not None:
    for _subname in ("varint", "varlong"):
        _sub = getattr(_codec_native, _subname, None)
        if _sub is not None:
            _sys.modules[f"minecraft_bot_accel.codec.{_subname}"] = _sub

del _sys, _name, _sub, _mod, _codec_native, _subname  # type: ignore[name-defined]  # noqa: F821
