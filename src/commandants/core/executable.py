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


def _auto_install_enabled(explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    return os.environ.get("COMMANDANTS_AUTO_INSTALL", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def resolve_binary(
    name: str,
    ants_path: str | os.PathLike[str] | None = None,
    auto_install: bool | None = None,
) -> str:
    """Resolve the absolute path to an ANTs binary named ``name``.

    Search order (first hit wins): explicit ``ants_path`` -> ``$ANTSPATH`` ->
    system ``PATH`` -> commandants-managed install (see
    :mod:`commandants.install`).

    Parameters
    ----------
    name:
        Binary name, e.g. ``"antsRegistration"``.
    ants_path:
        Optional explicit directory to look in first.
    auto_install:
        If the binary is not found anywhere and this is True (or the
        ``COMMANDANTS_AUTO_INSTALL`` environment variable is set), download the
        managed ANTs binaries and retry. Defaults to the env var.

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

    # 4. commandants-managed install
    from ..install import managed_bin_dir  # local import avoids an import cycle

    managed = managed_bin_dir()
    if managed:
        hit = _candidate_in_dir(managed, name)
        tried.append(f"managed={managed}")
        if hit:
            _RESOLVE_CACHE[key] = hit
            return hit

    # Opt-in: download the managed binaries and try once more.
    if _auto_install_enabled(auto_install):
        from ..install import install_ants

        bindir = install_ants()
        hit = _candidate_in_dir(bindir, name)
        if hit:
            _RESOLVE_CACHE[key] = hit
            return hit

    raise AntsNotFoundError(
        f"Could not find ANTs binary {name!r}. Searched: {', '.join(tried)}.\n"
        "Fix it by any of:\n"
        "  * run `commandants install-ants` to download prebuilt ANTs binaries,\n"
        "  * add ANTs to your PATH, or set ANTSPATH to its bin directory,\n"
        "  * pass ants_path=... to the command,\n"
        "  * or set COMMANDANTS_AUTO_INSTALL=1 to download automatically."
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
