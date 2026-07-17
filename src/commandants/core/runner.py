"""The subprocess core: the base command builder and its result object.

Every typed tool wrapper in commandants subclasses :class:`AntsCommand`. The base
class owns argv assembly, the ``extra_args`` escape hatch, dry-run inspection, and
execution via :mod:`subprocess`. Subclasses only implement :meth:`_build_args`,
which returns the tool-specific arguments (without the binary itself).
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .exceptions import AntsRuntimeError
from .executable import resolve_binary


@dataclass
class CompletedAnts:
    """Result of running an ANTs command.

    Attributes
    ----------
    argv:
        The exact argument vector that was executed.
    returncode:
        Process exit status.
    stdout, stderr:
        Captured output (``None`` if ``capture=False`` was used).
    outputs:
        Mapping of logical name -> output file path that the command *declared*
        it would write (e.g. ``{"warped": "out_Warped.nii.gz"}``). Populated by
        the tool wrapper; useful for chaining and for :meth:`load`.
    """

    argv: list[str]
    returncode: int
    stdout: str | None = None
    stderr: str | None = None
    outputs: dict[str, str] = field(default_factory=dict)

    def load(self, key: str = "output"):
        """Load a declared output image into memory (requires the ``[io]`` extra).

        Lazily imports nibabel so the core package has zero hard dependencies.
        """
        if key not in self.outputs:
            raise KeyError(
                f"No declared output named {key!r}. Available: {sorted(self.outputs)}"
            )
        path = self.outputs[key]
        try:
            import nibabel as nib  # noqa: PLC0415 (intentional lazy import)
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ImportError(
                "Loading images requires the optional [io] extra. "
                "Install it with: pip install 'commandants[io]'"
            ) from exc
        return nib.load(path)

    def output_path(self, key: str = "output") -> str:
        """Return the path of a declared output without loading it."""
        return self.outputs[key]


class AntsCommand:
    """Base class for all ANTs command wrappers.

    Parameters
    ----------
    binary:
        Name of the ANTs binary to invoke (e.g. ``"antsRegistration"``).
    ants_path:
        Optional explicit directory containing the binary; forwarded to
        :func:`resolve_binary`.
    """

    #: Default binary name; subclasses may override.
    binary_name: str = ""

    def __init__(
        self,
        binary: str | None = None,
        ants_path: str | os.PathLike[str] | None = None,
    ) -> None:
        self.binary = binary or self.binary_name
        if not self.binary:
            raise ValueError("An ANTs binary name must be provided.")
        self.ants_path = ants_path
        self._extra_args: list[str] = []

    # -- escape hatch ---------------------------------------------------------
    def extra_args(self, *args: Any) -> "AntsCommand":
        """Append arbitrary raw arguments, bypassing the typed API entirely.

        This is the guarantee that *nothing is hidden*: any flag the underlying
        binary supports -- now or in a future ANTs release -- can be reached.
        Accepts either individual tokens or a single iterable of tokens. Returns
        ``self`` for chaining.
        """
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            tokens: Sequence[Any] = args[0]
        else:
            tokens = args
        self._extra_args.extend(_stringify(t) for t in tokens)
        return self

    # -- subclass hook --------------------------------------------------------
    def _build_args(self) -> list[str]:
        """Return the tool-specific argument tokens (excluding the binary).

        Subclasses must implement this.
        """
        raise NotImplementedError

    # -- command assembly & execution ----------------------------------------
    def build_command(self, resolve: bool = False) -> list[str]:
        """Return the full argv for this command.

        By default the binary appears by name (e.g. ``antsRegistration``), which
        is what you want for printing/testing. Pass ``resolve=True`` to expand it
        to the resolved absolute path (this touches the filesystem/PATH).
        """
        head = resolve_binary(self.binary, self.ants_path) if resolve else self.binary
        return [head, *self._build_args(), *self._extra_args]

    def declared_outputs(self) -> dict[str, str]:
        """Logical name -> path mapping of files this command will write.

        Subclasses override to populate the :attr:`CompletedAnts.outputs` map.
        """
        return {}

    def run(
        self,
        *,
        check: bool = True,
        capture: bool = True,
        cwd: str | os.PathLike[str] | None = None,
        env: Mapping[str, str] | None = None,
        dry_run: bool = False,
    ) -> CompletedAnts:
        """Execute the command.

        Parameters
        ----------
        check:
            Raise :class:`AntsRuntimeError` on non-zero exit (default True).
        capture:
            Capture stdout/stderr as text (default True). When False, output
            streams to the parent process's terminal.
        cwd, env:
            Forwarded to :func:`subprocess.run`.
        dry_run:
            If True, do not execute; return a :class:`CompletedAnts` with
            ``returncode=-1`` and the assembled argv. Handy for inspection.
        """
        argv = self.build_command(resolve=not dry_run)
        outputs = self.declared_outputs()

        if dry_run:
            return CompletedAnts(argv=argv, returncode=-1, outputs=outputs)

        proc = subprocess.run(
            argv,
            capture_output=capture,
            text=True,
            cwd=cwd,
            env=dict(env) if env is not None else None,
            check=False,
        )
        result = CompletedAnts(
            argv=argv,
            returncode=proc.returncode,
            stdout=proc.stdout if capture else None,
            stderr=proc.stderr if capture else None,
            outputs=outputs,
        )
        if check and proc.returncode != 0:
            raise AntsRuntimeError(
                argv=argv,
                returncode=proc.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        return result

    # -- previews -------------------------------------------------------------
    def to_shell(self) -> str:
        """Return a copy-pasteable, shell-quoted preview of the command."""
        return " ".join(shlex.quote(tok) for tok in self.build_command())

    def print_command(self) -> None:
        """Print the shell preview to stdout."""
        print(self.to_shell())

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.to_shell()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<{type(self).__name__} {self.binary!r}>"


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, Path):
        return str(value)
    return str(value)
