"""Provision official prebuilt ANTs binaries on demand.

ANTsPyX bundles compiled ANTs into per-platform wheels. That model doesn't fit a
CLI wrapper: the official prebuilt ANTs command-line archives are 400-750 MB per
platform, far over PyPI's file-size limit. Instead, this module downloads the
official prebuilt binaries for the current platform from the ANTsX/ANTs GitHub
releases, unpacks them into a managed per-user directory, and records where the
``bin`` directory landed. :func:`commandants.core.executable.resolve_binary`
then discovers that directory automatically (as a fallback after PATH).

Nothing downloads implicitly unless you opt in (``auto_install=True`` or the
``COMMANDANTS_AUTO_INSTALL`` environment variable); normally you run it once via
``commandants install-ants`` or :func:`install_ants`.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from typing import Dict, List, Optional

from .core.exceptions import CommandantsError

#: Pinned default ANTs version (override with version=... / --version / "latest").
DEFAULT_VERSION = "2.6.5"

_API = "https://api.github.com/repos/ANTsX/ANTs/releases"
# Preferred Linux distro archives, best first (x86_64 only).
_LINUX_PREFERENCE = [
    "ubuntu-22.04",
    "ubuntu-24.04",
    "ubuntu20.04",
    "ubuntu18.04",
    "almalinux9",
    "almalinux8",
    "centos7",
]


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
def user_data_dir() -> str:
    """Return the per-user data directory commandants writes into."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    elif system == "Darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "commandants")


def _ants_root() -> str:
    return os.path.join(user_data_dir(), "ants")


def _marker_path(version_dir: str) -> str:
    return os.path.join(version_dir, "BIN_PATH.txt")


def _read_marker(marker: str) -> Optional[str]:
    if not os.path.isfile(marker):
        return None
    with open(marker) as fh:
        path = fh.read().strip()
    return path if path and os.path.isdir(path) else None


def _version_key(v: str):
    parts = []
    for chunk in v.lstrip("v").split("."):
        parts.append(int(chunk) if chunk.isdigit() else 0)
    return tuple(parts)


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #
def installed_versions() -> Dict[str, str]:
    """Return ``{version: bin_dir}`` for every managed ANTs install."""
    root = _ants_root()
    found: Dict[str, str] = {}
    if not os.path.isdir(root):
        return found
    for name in os.listdir(root):
        bindir = _read_marker(_marker_path(os.path.join(root, name)))
        if bindir:
            found[name] = bindir
    return found


def managed_bin_dir(version: Optional[str] = None) -> Optional[str]:
    """Return the ``bin`` dir of a managed ANTs install, or ``None``.

    With ``version`` unset, returns the newest installed version.
    """
    installs = installed_versions()
    if not installs:
        return None
    if version is not None:
        return installs.get(version.lstrip("v"))
    newest = sorted(installs, key=_version_key)[-1]
    return installs[newest]


# --------------------------------------------------------------------------- #
# Asset selection
# --------------------------------------------------------------------------- #
def select_asset(
    names: List[str],
    system: Optional[str] = None,
    machine: Optional[str] = None,
) -> str:
    """Pick the best release asset name for a platform.

    Raises :class:`CommandantsError` if no suitable asset exists (e.g. Linux
    ARM, for which ANTs publishes no prebuilt binary) -- pass an explicit asset
    name in that case.
    """
    system = (system or platform.system()).lower()
    machine = (machine or platform.machine()).lower()

    if system == "windows":
        cands = [n for n in names if "windows" in n.lower()]
    elif system == "darwin":
        if machine in ("arm64", "aarch64"):
            cands = [n for n in names if "macos" in n.lower() and "arm64" in n.lower()]
        else:
            cands = [
                n
                for n in names
                if "macos" in n.lower() and ("intel" in n.lower() or "x64" in n.lower())
            ]
    else:  # linux and friends
        if machine not in ("x86_64", "amd64", "x64"):
            raise CommandantsError(
                f"No prebuilt ANTs binary is published for {system}/{machine}. "
                "Build ANTs from source or pass an explicit asset= name."
            )
        linux = [
            n
            for n in names
            if any(k in n.lower() for k in ("ubuntu", "almalinux", "centos"))
        ]
        cands = []
        for pref in _LINUX_PREFERENCE:
            cands = [n for n in linux if pref in n.lower()]
            if cands:
                break
        if not cands:
            cands = linux

    zips = [n for n in cands if n.lower().endswith(".zip")]
    chosen = zips or cands
    if not chosen:
        raise CommandantsError(
            f"Could not match a prebuilt ANTs asset for {system}/{machine} among "
            f"{names}. Pass asset= explicitly."
        )
    return chosen[0]


# --------------------------------------------------------------------------- #
# Network + extraction
# --------------------------------------------------------------------------- #
def _fetch_release(version: Optional[str]) -> dict:
    if version in (None, "latest"):
        url = f"{_API}/latest"
    else:
        url = f"{_API}/tags/v{version.lstrip('v')}"
    req = urllib.request.Request(url, headers={"User-Agent": "commandants", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310 (trusted host)
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - network dependent
        raise CommandantsError(f"Failed to query ANTs release {version!r}: {exc}") from exc


def _download(url: str, dest: str, quiet: bool = False) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "commandants"})
    with urllib.request.urlopen(req) as resp:  # noqa: S310 (trusted host)
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        chunk = 1024 * 256
        with open(dest, "wb") as fh:
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                fh.write(buf)
                done += len(buf)
                if not quiet and total:
                    pct = 100 * done / total
                    print(
                        f"\r  downloading ANTs: {pct:5.1f}% ({done >> 20}/{total >> 20} MiB)",
                        end="",
                        file=sys.stderr,
                        flush=True,
                    )
        if not quiet and total:
            print(file=sys.stderr)


def _safe_extract(zip_path: str, dest: str) -> None:
    """Extract a zip, guarding against path traversal and restoring exec bits.

    Python's zipfile does not preserve Unix permissions, so binaries lose their
    executable bit; we restore it from each member's stored mode.
    """
    dest_abs = os.path.abspath(dest)
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            target = os.path.abspath(os.path.join(dest, member.filename))
            if not target.startswith(dest_abs + os.sep) and target != dest_abs:
                raise CommandantsError(f"Unsafe path in archive: {member.filename!r}")
            zf.extract(member, dest)
            mode = member.external_attr >> 16
            if mode:
                try:
                    os.chmod(os.path.join(dest, member.filename), mode)
                except OSError:  # pragma: no cover - platform dependent
                    pass


def _find_bin_dir(root: str) -> str:
    """Locate the directory containing antsRegistration inside an extracted tree."""
    exe_names = {"antsRegistration", "antsRegistration.exe"}
    for dirpath, _dirs, files in os.walk(root):
        if exe_names & set(files):
            return dirpath
    raise CommandantsError(
        f"Extracted ANTs archive under {root!r} but found no antsRegistration binary."
    )


# --------------------------------------------------------------------------- #
# Public install / uninstall
# --------------------------------------------------------------------------- #
def install_ants(
    version: str = DEFAULT_VERSION,
    dest: Optional[str] = None,
    asset: Optional[str] = None,
    force: bool = False,
    quiet: bool = False,
) -> str:
    """Download and unpack prebuilt ANTs binaries; return the ``bin`` directory.

    Parameters
    ----------
    version:
        ANTs version (e.g. ``"2.6.5"``) or ``"latest"``.
    dest:
        Root directory to install under (defaults to the managed user data dir).
    asset:
        Explicit release asset name to override platform auto-selection.
    force:
        Re-download/extract even if this version is already installed.
    quiet:
        Suppress progress output.
    """
    release = _fetch_release(version)
    tag = release.get("tag_name", "")
    resolved_version = tag.lstrip("v") or (version if version != "latest" else "unknown")
    assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
    if not assets:
        raise CommandantsError(f"ANTs release {tag or version!r} has no downloadable assets.")

    name = asset or select_asset(list(assets))
    if name not in assets:
        raise CommandantsError(
            f"Asset {name!r} not found in release {tag!r}. Available: {sorted(assets)}"
        )

    root = dest or _ants_root()
    version_dir = os.path.join(root, resolved_version)
    marker = _marker_path(version_dir)

    existing = _read_marker(marker)
    if existing and not force:
        if not quiet:
            print(f"ANTs {resolved_version} already installed at {existing}", file=sys.stderr)
        return existing

    if os.path.isdir(version_dir) and force:
        shutil.rmtree(version_dir, ignore_errors=True)
    os.makedirs(version_dir, exist_ok=True)

    if not quiet:
        print(f"Installing ANTs {resolved_version} ({name})", file=sys.stderr)

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, name)
        _download(assets[name], zip_path, quiet=quiet)
        _safe_extract(zip_path, version_dir)

    bindir = _find_bin_dir(version_dir)
    with open(marker, "w") as fh:
        fh.write(bindir)
    if not quiet:
        print(f"ANTs {resolved_version} ready. bin: {bindir}", file=sys.stderr)
    return bindir


def uninstall_ants(version: Optional[str] = None) -> List[str]:
    """Remove managed ANTs install(s); return the version dirs removed."""
    root = _ants_root()
    removed: List[str] = []
    if not os.path.isdir(root):
        return removed
    targets = [version.lstrip("v")] if version else list(installed_versions())
    for ver in targets:
        vdir = os.path.join(root, ver)
        if os.path.isdir(vdir):
            shutil.rmtree(vdir, ignore_errors=True)
            removed.append(vdir)
    return removed


__all__ = [
    "DEFAULT_VERSION",
    "install_ants",
    "uninstall_ants",
    "managed_bin_dir",
    "installed_versions",
    "select_asset",
    "user_data_dir",
]
