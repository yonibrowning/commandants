"""The subprocess core: the base command builder and its result object.

Every typed tool wrapper in commandants subclasses :class:`AntsCommand`. The base
class owns argv assembly, the ``extra_args`` escape hatch, dry-run inspection,
execution via :mod:`subprocess`, and the resolver that turns image inputs into
paths -- including materializing in-memory ``SimpleITK.Image`` objects to temp
files. Subclasses implement :meth:`_build_args` and call :meth:`_resolve` on any
argument that may be a path *or* an in-memory image.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from ..io.materialize import TempWorkspace, is_sitk_image
from .exceptions import AntsRuntimeError
from .executable import resolve_binary
from .params import str_resolve

Resolver = Callable[[Any, Optional[str]], str]


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
        it would write (e.g. ``{"warped": "out_Warped.nii.gz"}``).
    workspace:
        The :class:`~commandants.io.materialize.TempWorkspace` that holds any
        in-memory inputs written to disk for this run, or ``None`` if no
        materialization was needed.
    """

    argv: list[str]
    returncode: int
    stdout: str | None = None
    stderr: str | None = None
    outputs: dict[str, str] = field(default_factory=dict)
    workspace: Optional[TempWorkspace] = None

    @property
    def temp_dir(self) -> str | None:
        """Directory holding materialized temp inputs, or ``None``."""
        return self.workspace.dir if self.workspace is not None else None

    def load(self, key: str = "output"):
        """Load a declared output image as a ``SimpleITK.Image`` (needs ``[io]``)."""
        if key not in self.outputs:
            raise KeyError(
                f"No declared output named {key!r}. Available: {sorted(self.outputs)}"
            )
        from ..io.materialize import require_sitk

        return require_sitk().ReadImage(self.outputs[key])

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

        # In-memory image materialization state.
        self._workspace: Optional[TempWorkspace] = None
        self._ws_base: Optional[str] = None
        self._ws_keep: bool = True
        self._active_resolver: Resolver = str_resolve

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

    # -- in-memory image support ---------------------------------------------
    @property
    def workspace(self) -> Optional[TempWorkspace]:
        """The temp workspace created for in-memory inputs (if any)."""
        return self._workspace

    def set_workspace(self, workspace: TempWorkspace) -> "AntsCommand":
        """Use a specific :class:`TempWorkspace` for materializing images."""
        self._workspace = workspace
        return self

    def _ensure_workspace(self) -> TempWorkspace:
        if self._workspace is None:
            self._workspace = TempWorkspace(base=self._ws_base, keep=self._ws_keep)
        return self._workspace

    def _resolver_for(self, materialize: bool) -> Resolver:
        def resolve(value: Any, name: Optional[str] = None) -> str:
            if is_sitk_image(value):
                if not materialize:
                    # Preview mode: don't write files, show a readable placeholder.
                    return f"<sitk:{name or 'image'}>"
                return self._ensure_workspace().materialize(value, name=name)
            return str(value)

        return resolve

    def _resolve(self, value: Any, name: str | None = None) -> str:
        """Resolve an argument that may be a path or an in-memory image.

        Subclasses call this inside :meth:`_build_args` for every image-bearing
        argument. During assembly the active resolver either materializes
        SimpleITK images to temp files or emits a preview placeholder.
        """
        return self._active_resolver(value, name)

    # -- subclass hook --------------------------------------------------------
    def _build_args(self) -> list[str]:
        """Return the tool-specific argument tokens (excluding the binary)."""
        raise NotImplementedError

    # -- command assembly & execution ----------------------------------------
    def build_command(self, resolve: bool = False, materialize: bool = False) -> list[str]:
        """Return the full argv for this command.

        Parameters
        ----------
        resolve:
            If True, expand the binary to its resolved absolute path (touches the
            filesystem/PATH). Default False emits the binary by name.
        materialize:
            If True, write any in-memory SimpleITK image inputs to temp files and
            use their paths. Default False emits ``<sitk:...>`` placeholders for
            images so previews never write to disk.
        """
        head = resolve_binary(self.binary, self.ants_path) if resolve else self.binary
        self._active_resolver = self._resolver_for(materialize)
        try:
            body = [*self._build_args(), *self._extra_args]
        finally:
            self._active_resolver = str_resolve
        return [head, *body]

    def declared_outputs(self) -> dict[str, str]:
        """Logical name -> path mapping of files this command will write."""
        return {}

    def run(
        self,
        *,
        check: bool = True,
        capture: bool = True,
        cwd: str | os.PathLike[str] | None = None,
        env: Mapping[str, str] | None = None,
        dry_run: bool = False,
        workspace: Optional[TempWorkspace] = None,
        temp_dir: str | os.PathLike[str] | None = None,
        keep_temp: bool = True,
    ) -> CompletedAnts:
        """Execute the command.

        Parameters
        ----------
        check:
            Raise :class:`AntsRuntimeError` on non-zero exit (default True).
        capture:
            Capture stdout/stderr as text (default True).
        cwd, env:
            Forwarded to :func:`subprocess.run`.
        dry_run:
            If True, do not execute or write temp files; return a
            :class:`CompletedAnts` with ``returncode=-1`` and the assembled argv
            (in-memory images shown as placeholders).
        workspace:
            Explicit :class:`TempWorkspace` to materialize in-memory images into.
        temp_dir:
            Parent directory for the auto-created temp workspace (ignored if
            ``workspace`` is given).
        keep_temp:
            Keep materialized temp files after the run (default True) so they can
            be inspected via ``result.temp_dir`` / ``result.workspace``.
        """
        if workspace is not None:
            self._workspace = workspace
        if temp_dir is not None:
            self._ws_base = str(temp_dir)
        self._ws_keep = keep_temp

        argv = self.build_command(resolve=not dry_run, materialize=not dry_run)
        outputs = self.declared_outputs()

        if dry_run:
            return CompletedAnts(
                argv=argv, returncode=-1, outputs=outputs, workspace=self._workspace
            )

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
            workspace=self._workspace,
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
        """Return a copy-pasteable, shell-quoted preview of the command.

        In-memory image inputs appear as ``<sitk:...>`` placeholders; no temp
        files are written by previewing.
        """
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
