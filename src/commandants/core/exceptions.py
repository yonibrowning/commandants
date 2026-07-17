"""Exceptions raised by commandants."""

from __future__ import annotations

from typing import Sequence


class CommandantsError(Exception):
    """Base class for all commandants errors."""


class AntsNotFoundError(CommandantsError):
    """Raised when an ANTs binary cannot be located.

    The message includes the search order that was tried so the user knows
    exactly how to fix it (install ANTs, set ``ANTSPATH``, or pass ``ants_path``).
    """


class AntsRuntimeError(CommandantsError):
    """Raised when an ANTs binary exits with a non-zero return code.

    Carries the full ``argv`` and captured ``stderr``/``stdout`` so failures are
    debuggable without re-running the command.
    """

    def __init__(
        self,
        argv: Sequence[str],
        returncode: int,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> None:
        self.argv = list(argv)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

        binary = self.argv[0] if self.argv else "<unknown>"
        detail = (stderr or stdout or "").strip()
        message = f"{binary} exited with code {returncode}."
        if detail:
            # Keep the tail; ANTs can be verbose and the error is usually last.
            tail = "\n".join(detail.splitlines()[-20:])
            message += f"\n--- stderr (tail) ---\n{tail}"
        message += "\n--- command ---\n" + " ".join(self.argv)
        super().__init__(message)
