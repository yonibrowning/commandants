"""Tests for the exit-code explainer."""

from __future__ import annotations

from commandants import CompletedAnts, explain_exit_code
from commandants.core.exceptions import AntsRuntimeError


def test_success():
    e = explain_exit_code(0)
    assert e.category == "success"
    assert "Success" in e.summary


def test_sigkill_negative_is_oom():
    e = explain_exit_code(-9)
    assert e.name == "SIGKILL"
    assert e.category == "signal"
    text = e.text().lower()
    assert "memory" in text  # the OOM steer
    assert "estimate_resources" in text


def test_sigkill_shell_128_plus_9():
    e = explain_exit_code(137)
    assert e.name == "SIGKILL"
    assert "128+9" in e.summary


def test_segfault_and_abort():
    assert explain_exit_code(-11).name == "SIGSEGV"
    assert explain_exit_code(139).name == "SIGSEGV"  # 128+11
    abrt = explain_exit_code(-6)
    assert abrt.name == "SIGABRT"
    assert "memory" in abrt.text().lower()  # bad_alloc steer


def test_sigill_mentions_cpu():
    e = explain_exit_code(-4)
    assert e.name == "SIGILL"
    assert "instruction" in e.summary.lower()


def test_generic_failure_and_usage():
    assert explain_exit_code(1).category == "failure"
    assert explain_exit_code(2).category == "usage"


def test_windows_access_violation():
    e = explain_exit_code(3221225477)  # 0xC0000005
    assert e.category == "windows-exception"
    assert "ACCESS_VIOLATION" in e.name
    # Also recognizable in its signed form.
    assert explain_exit_code(-1073741819).category == "windows-exception"


def test_unknown_code():
    e = explain_exit_code(42)
    assert e.category == "unknown"


def test_completed_ants_explain():
    result = CompletedAnts(argv=["antsRegistration"], returncode=-9)
    assert result.explain().name == "SIGKILL"


def test_runtime_error_message_includes_explanation():
    err = AntsRuntimeError(["antsRegistration", "-d", "3"], returncode=-9, stderr="")
    assert "SIGKILL" in str(err)
    assert err.explanation is not None and err.explanation.name == "SIGKILL"
