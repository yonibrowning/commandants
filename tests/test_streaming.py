"""Tests for live output streaming in run(stream=...) / run(on_line=...).

Uses the Python interpreter as a stand-in subprocess so no ANTs is needed.
"""

from __future__ import annotations

import sys

from commandants.core.runner import AntsCommand


class _PyCommand(AntsCommand):
    """Runs the current Python interpreter; args supplied via extra_args."""

    binary_name = sys.executable

    def _build_args(self):
        return []


def test_stream_captures_and_echoes(capsys):
    cmd = _PyCommand()
    cmd.extra_args("-c", "print('iter 1'); print('iter 2')")
    result = cmd.run(stream=True)
    assert result.returncode == 0
    # Captured for later use...
    assert "iter 1" in result.stdout and "iter 2" in result.stdout
    # ...and echoed live to stdout.
    assert "iter 1" in capsys.readouterr().out


def test_on_line_callback_receives_lines():
    cmd = _PyCommand()
    cmd.extra_args("-c", "print('a'); print('b'); print('c')")
    lines: list[str] = []
    result = cmd.run(on_line=lines.append)  # implies streaming
    assert result.returncode == 0
    joined = "".join(lines)
    assert "a" in joined and "b" in joined and "c" in joined


def test_stream_merges_stderr_into_stdout():
    cmd = _PyCommand()
    cmd.extra_args("-c", "import sys; print('out'); print('err', file=sys.stderr)")
    result = cmd.run(stream=True)
    assert "out" in result.stdout and "err" in result.stdout
    assert result.stderr is None  # merged into stdout when streaming


def test_bad_callback_does_not_kill_run():
    cmd = _PyCommand()
    cmd.extra_args("-c", "print('x')")

    def boom(_line):
        raise RuntimeError("callback error")

    result = cmd.run(on_line=boom)
    assert result.returncode == 0
