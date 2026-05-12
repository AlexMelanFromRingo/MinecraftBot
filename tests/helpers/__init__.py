"""Shared helpers for the parametrised test suite (milestone 003).

The ``tests.helpers.backend`` submodule resolves the active backend
(``minecraft_bot`` or ``minecraft_bot_accel``) from the
``--backend`` pytest CLI option and re-exports the symbols every test
file commonly needs (``Bot``, ``Connection``, ``Reader``, ``Writer``,
``WireLog``, ``errors``). Tests should ``from tests.helpers.backend
import Bot`` rather than hard-coding ``minecraft_bot``.
"""
