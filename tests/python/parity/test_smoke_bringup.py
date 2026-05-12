"""T021 — Phase 2 smoke gate.

Imports both backends, verifies their identity attributes, and asserts
they advertise compatible Python-reference versions.
"""

from __future__ import annotations

import re

import pytest


def test_both_backends_importable() -> None:
    """Both backends must be importable in the same process."""
    import minecraft_bot  # noqa: F401
    import minecraft_bot_accel  # noqa: F401


def test_python_backend_implementation() -> None:
    """The Python reference advertises itself as ``implementation="python"``.

    If this attribute is missing on the Python side, we skip rather than
    fail — the Python reference does not yet expose it; this test is a
    forward-looking compatibility hint.
    """
    import minecraft_bot

    impl = getattr(minecraft_bot, "implementation", None)
    if impl is None:
        pytest.skip("minecraft_bot does not yet expose `implementation`")
    assert impl == "python"


def test_accel_backend_implementation() -> None:
    """The native package advertises itself as ``implementation="rust"``."""
    import minecraft_bot_accel

    assert minecraft_bot_accel.implementation == "rust"


def test_accel_version_attribute_format() -> None:
    """``__version__`` is semver-shaped."""
    import minecraft_bot_accel

    assert re.match(
        r"^\d+\.\d+\.\d+", minecraft_bot_accel.__version__
    ), f"unexpected accel version: {minecraft_bot_accel.__version__!r}"


def test_accel_python_compat_format() -> None:
    """``python_compat`` is a semver-shaped compatibility line (e.g., ``0.1.x``)."""
    import minecraft_bot_accel

    pat = re.compile(r"^\d+\.\d+\.(x|\d+)$")
    assert pat.match(
        minecraft_bot_accel.python_compat
    ), f"unexpected accel python_compat: {minecraft_bot_accel.python_compat!r}"


def test_accel_python_compat_matches_python_reference() -> None:
    """``python_compat`` MUST cover the installed ``minecraft_bot`` version.

    The compat line is of the form ``MAJOR.MINOR.x`` (or fully pinned);
    the installed Python reference's MAJOR.MINOR must match. Constitution
    Principle I + research.md R-010.
    """
    import minecraft_bot
    import minecraft_bot_accel

    py_ver = getattr(minecraft_bot, "__version__", None)
    if py_ver is None:
        pytest.skip("minecraft_bot does not expose __version__")

    m = re.match(r"^(\d+)\.(\d+)", py_ver)
    assert m, f"python __version__ not semver-shaped: {py_ver!r}"
    py_major, py_minor = m.group(1), m.group(2)

    compat = minecraft_bot_accel.python_compat
    m2 = re.match(r"^(\d+)\.(\d+)\.", compat)
    assert m2, f"accel python_compat not semver-shaped: {compat!r}"
    accel_major, accel_minor = m2.group(1), m2.group(2)

    assert (accel_major, accel_minor) == (py_major, py_minor), (
        f"accel python_compat {compat!r} does not cover installed "
        f"minecraft_bot {py_ver!r}"
    )


def test_accel_errors_submodule_classes() -> None:
    """Every exception name from python/minecraft_bot/errors.py is
    present on minecraft_bot_accel.errors with the matching class hierarchy."""
    from minecraft_bot_accel import errors as accel_errors

    # Just a few representative classes — full surface is checked in T043.
    assert issubclass(accel_errors.DecodeError, accel_errors.ProtocolError)
    assert issubclass(accel_errors.OversizedVarInt, accel_errors.DecodeError)
    assert issubclass(accel_errors.KickedByServer, accel_errors.Disconnected)
    assert issubclass(accel_errors.Disconnected, accel_errors.ProtocolError)


def test_accel_codec_smoke() -> None:
    """varint round-trip via the native codec."""
    from minecraft_bot_accel.codec import Reader, Writer
    from minecraft_bot_accel.codec import varint

    w = Writer()
    varint.write(300, w)
    encoded = w.bytes()
    assert encoded == b"\xac\x02"

    r = Reader(encoded)
    assert varint.read(r) == 300
    assert r.remaining() == 0


def test_accel_framer_smoke() -> None:
    """Framer round-trip via the native framer."""
    from minecraft_bot_accel.framer import Framer

    f = Framer(compression_threshold=-1)
    encoded = f.encode(b"\x01\x02\x03")
    f.feed(encoded)
    body = f.try_extract()
    assert body == b"\x01\x02\x03"
