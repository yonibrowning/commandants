"""Tests for the ANTs binary provisioner -- no real network downloads."""

from __future__ import annotations

import os
import zipfile

import pytest

from commandants import install
from commandants.core import executable
from commandants.core.exceptions import AntsNotFoundError, CommandantsError

# Representative asset list from a real ANTs release.
ASSETS = [
    "ants-2.6.5-almalinux9-X64-gcc.zip",
    "ants-2.6.5-centos7-X64-gcc.zip",
    "ants-2.6.5-ubuntu18.04-X64-gcc.zip",
    "ants-2.6.5-ubuntu-22.04-X64-gcc.zip",
    "ants-2.6.5-ubuntu-24.04-X64-gcc.zip",
    "ants-2.6.5-macos-14-ARM64-clang.zip",
    "ants-2.6.5-macos-15-intel-X64-clang.zip",
    "ants-2.6.5-windows-2022-X64-VS2019.zip",
]


@pytest.fixture(autouse=True)
def _clear_cache():
    executable.clear_cache()
    yield
    executable.clear_cache()


# -- asset selection -------------------------------------------------------- #
def test_select_asset_windows():
    assert "windows" in install.select_asset(ASSETS, "Windows", "AMD64").lower()


def test_select_asset_macos_arm_vs_intel():
    assert "arm64" in install.select_asset(ASSETS, "Darwin", "arm64").lower()
    intel = install.select_asset(ASSETS, "Darwin", "x86_64").lower()
    assert "intel" in intel or "x64" in intel


def test_select_asset_linux_prefers_ubuntu_2204():
    assert install.select_asset(ASSETS, "Linux", "x86_64") == "ants-2.6.5-ubuntu-22.04-X64-gcc.zip"


def test_select_asset_linux_arm_raises():
    with pytest.raises(CommandantsError):
        install.select_asset(ASSETS, "Linux", "aarch64")


# -- extraction ------------------------------------------------------------- #
def test_safe_extract_preserves_exec_bit_and_finds_bin(tmp_path):
    zip_path = tmp_path / "ants.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        info = zipfile.ZipInfo("ants-2.6.5/bin/antsRegistration")
        info.external_attr = 0o755 << 16
        zf.writestr(info, "#!/bin/sh\necho hi\n")
        zf.writestr("ants-2.6.5/lib/notes.txt", "libs here")

    dest = tmp_path / "out"
    install._safe_extract(str(zip_path), str(dest))
    bindir = install._find_bin_dir(str(dest))
    exe = os.path.join(bindir, "antsRegistration")
    assert os.path.exists(exe)
    if os.name != "nt":
        assert os.access(exe, os.X_OK)


def test_safe_extract_rejects_path_traversal(tmp_path):
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../escape.txt", "nope")
    with pytest.raises(CommandantsError):
        install._safe_extract(str(zip_path), str(tmp_path / "out"))


# -- discovery -------------------------------------------------------------- #
def test_managed_bin_dir_and_versions(tmp_path, monkeypatch):
    root = tmp_path / "commandants"
    monkeypatch.setattr(install, "user_data_dir", lambda: str(root))

    for ver in ("2.5.0", "2.6.5"):
        bindir = root / "ants" / ver / "install" / "bin"
        bindir.mkdir(parents=True)
        (bindir / "antsRegistration").write_text("x")
        (root / "ants" / ver / "BIN_PATH.txt").write_text(str(bindir))

    assert set(install.installed_versions()) == {"2.5.0", "2.6.5"}
    assert install.managed_bin_dir("2.5.0").endswith(os.path.join("2.5.0", "install", "bin"))
    # No version arg -> newest.
    assert "2.6.5" in install.managed_bin_dir()


# -- resolve_binary integration -------------------------------------------- #
def test_resolve_binary_managed_fallback(monkeypatch):
    monkeypatch.delenv("ANTSPATH", raising=False)
    monkeypatch.setattr(executable.shutil, "which", lambda n, path=None: None)
    monkeypatch.setattr(install, "managed_bin_dir", lambda version=None: "/managed/bin")
    monkeypatch.setattr(
        executable,
        "_candidate_in_dir",
        lambda d, n: f"{d}/{n}" if str(d) == "/managed/bin" else None,
    )
    assert executable.resolve_binary("antsRegistration") == "/managed/bin/antsRegistration"


def test_resolve_binary_auto_install_opt_in(monkeypatch):
    monkeypatch.delenv("ANTSPATH", raising=False)
    monkeypatch.setattr(executable.shutil, "which", lambda n, path=None: None)
    monkeypatch.setattr(install, "managed_bin_dir", lambda version=None: None)
    calls = {}

    def fake_install(*a, **k):
        calls["installed"] = True
        return "/dl/bin"

    monkeypatch.setattr(install, "install_ants", fake_install)
    monkeypatch.setattr(
        executable,
        "_candidate_in_dir",
        lambda d, n: f"{d}/{n}" if str(d) == "/dl/bin" else None,
    )
    got = executable.resolve_binary("antsRegistration", auto_install=True)
    assert got == "/dl/bin/antsRegistration"
    assert calls.get("installed") is True


def test_resolve_binary_not_found_message(monkeypatch):
    monkeypatch.delenv("ANTSPATH", raising=False)
    monkeypatch.delenv("COMMANDANTS_AUTO_INSTALL", raising=False)
    monkeypatch.setattr(executable.shutil, "which", lambda n, path=None: None)
    monkeypatch.setattr(install, "managed_bin_dir", lambda version=None: None)
    with pytest.raises(AntsNotFoundError) as exc:
        executable.resolve_binary("antsRegistration")
    assert "install-ants" in str(exc.value)
