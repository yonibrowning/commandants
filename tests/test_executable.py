"""Binary resolution order: explicit ants_path > $ANTSPATH > $PATH."""

from __future__ import annotations

import pytest

from commandants.core import executable
from commandants.core.exceptions import AntsNotFoundError


@pytest.fixture(autouse=True)
def _clear_cache():
    executable.clear_cache()
    yield
    executable.clear_cache()


def _fake_which_factory(mapping):
    """Return a fake shutil.which that resolves based on the ``path`` argument."""

    def fake_which(name, path=None):
        return mapping.get(path)

    return fake_which


def test_explicit_ants_path_wins(monkeypatch):
    mapping = {
        "/explicit": "/explicit/antsRegistration",
        "/envpath": "/envpath/antsRegistration",
        None: "/usr/bin/antsRegistration",
    }
    monkeypatch.setattr(executable.shutil, "which", _fake_which_factory(mapping))
    monkeypatch.setenv("ANTSPATH", "/envpath")

    got = executable.resolve_binary("antsRegistration", ants_path="/explicit")
    assert got == "/explicit/antsRegistration"


def test_antspath_used_when_no_explicit(monkeypatch):
    mapping = {
        "/envpath": "/envpath/antsRegistration",
        None: "/usr/bin/antsRegistration",
    }
    monkeypatch.setattr(executable.shutil, "which", _fake_which_factory(mapping))
    monkeypatch.setenv("ANTSPATH", "/envpath")

    got = executable.resolve_binary("antsRegistration")
    assert got == "/envpath/antsRegistration"


def test_path_used_when_neither(monkeypatch):
    mapping = {None: "/usr/bin/antsRegistration"}
    monkeypatch.setattr(executable.shutil, "which", _fake_which_factory(mapping))
    monkeypatch.delenv("ANTSPATH", raising=False)

    got = executable.resolve_binary("antsRegistration")
    assert got == "/usr/bin/antsRegistration"


def test_not_found_raises(monkeypatch):
    monkeypatch.setattr(executable.shutil, "which", _fake_which_factory({}))
    monkeypatch.delenv("ANTSPATH", raising=False)

    with pytest.raises(AntsNotFoundError) as exc:
        executable.resolve_binary("antsRegistration")
    # The message should be actionable.
    assert "antsRegistration" in str(exc.value)
    assert "PATH" in str(exc.value)


def test_is_available_does_not_raise(monkeypatch):
    monkeypatch.setattr(executable.shutil, "which", _fake_which_factory({}))
    monkeypatch.delenv("ANTSPATH", raising=False)
    assert executable.is_available("antsRegistration") is False
