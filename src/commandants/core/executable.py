"""Locating ANTs binaries on the system.

Resolution order (first hit wins):

1. an explicit ``ants_path`` directory passed by the caller,
2. the ``ANTSPATH`` environment variable (a directory),
3. the system ``PATH`` (via :func:`shutil.which`).

Nothing is cached implicitly beyond a small lookup memo, so changing
``ANTSPATH`` mid-session is respected on the next call once the memo is cleared
with :func:`clear_cache`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .exceptions import AntsNotFoundError

# Memoize resolved absolute paths keyed by (name, ants_path) to avoid repeated
# filesystem probing within a session.
_RESOLVE_CACHE: dict[tuple[str, str | None], str] = {}


def _candidate_in_dir(directory: str | os.PathLike[str], name: str) -> str | None:
    """Return an executable path for ``name`` inside ``directory`` if present."""
    # shutil.which handles platform-specific extensions (.exe on Windows).
    found = shutil.which(name, path=str(directory))
    return found


def resolve_binary(name: str, ants_path: str | os.PathLike[str] | None = None) -> str:
    """Resolve the absolute path to an ANTs binary named ``name``.

    Parameters
    ----------
    name:
        Binary name, e.g. ``"antsRegistration"``.
    ants_path:
        Optional explicit directory to look in first. Overrides ``ANTSPATH``
        and ``PATH``.

    Raises
    ------
    AntsNotFoundError
        If the binary cannot be found through any of the search locations.
    """
    key = (name, str(ants_path) if ants_path is not None else None)
    if key in _RESOLVE_CACHE:
        return _RESOLVE_CACHE[key]

    tried: list[str] = []

    # 1. explicit directory
    if ants_path is not None:
        hit = _candidate_in_dir(ants_path, name)
        tried.append(f"ants_path={ants_path}")
        if hit:
            _RESOLVE_CACHE[key] = hit
            return hit

    # 2. ANTSPATH env var
    env_path = os.environ.get("ANTSPATH")
    if env_path:
        hit = _candidate_in_dir(env_path, name)
        tried.append(f"$ANTSPATH={env_path}")
        if hit:
            _RESOLVE_CACHE[key] = hit
            return hit

    # 3. system PATH
    hit = shutil.which(name)
    tried.append("$PATH")
    if hit:
        _RESOLVE_CACHE[key] = hit
        return hit

    raise AntsNotFoundError(
        f"Could not find ANTs binary {name!r}. Searched: {', '.join(tried)}.\n"
        "Fix by installing ANTs and either adding it to your PATH, setting the "
        "ANTSPATH environment variable to the directory containing the binaries, "
        "or passing ants_path=... to the command."
    )


def is_available(name: str = "antsRegistration", ants_path: str | os.PathLike[str] | None = None) -> bool:
    """Return True if ``name`` can be resolved (does not raise)."""
    try:
        resolve_binary(name, ants_path=ants_path)
        return True
    except AntsNotFoundError:
        return False


def version(
    binary: str = "antsRegistration",
    ants_path: str | os.PathLike[str] | None = None,
) -> str:
    """Return the ``--version`` string reported by an ANTs binary."""
    exe = resolve_binary(binary, ants_path=ants_path)
    proc = subprocess.run(
        [exe, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    return (proc.stdout or proc.stderr).strip()


def clear_cache() -> None:
    """Clear the binary-resolution memo (e.g. after changing ANTSPATH)."""
    _RESOLVE_CACHE.clear()
