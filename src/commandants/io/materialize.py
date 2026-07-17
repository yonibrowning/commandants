"""Optional in-memory image support via SimpleITK.

ANTs binaries only read/write files, so an in-memory ``SimpleITK.Image`` passed to
a command is transparently written to a temp NIfTI before ANTs runs. SimpleITK is
used because it carries full spatial metadata (origin, spacing, direction), so the
round-trip through disk is lossless -- unlike a bare NumPy array, which would drop
orientation and spacing.

The temp files are **not hidden**: a :class:`TempWorkspace` exposes its directory
(:attr:`TempWorkspace.dir`), every file it wrote (:attr:`TempWorkspace.files`), and
a name→path map of the materialized inputs (:attr:`TempWorkspace.inputs`). By
default temp files are kept so you can inspect them; pass ``keep=False`` (or call
:meth:`TempWorkspace.cleanup`) to remove them.

SimpleITK ships with the optional ``[io]`` extra:  ``pip install 'commandants[io]'``.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional


def _try_import_sitk():
    try:
        import SimpleITK as sitk  # noqa: PLC0415 (intentional lazy import)

        return sitk
    except ImportError:
        return None


def is_sitk_image(obj: Any) -> bool:
    """Return True if ``obj`` is a ``SimpleITK.Image`` (and SimpleITK is installed)."""
    sitk = _try_import_sitk()
    return sitk is not None and isinstance(obj, sitk.Image)


def require_sitk():
    """Return the SimpleITK module or raise an actionable ImportError."""
    sitk = _try_import_sitk()
    if sitk is None:
        raise ImportError(
            "Passing/loading in-memory images requires SimpleITK. Install the [io] "
            "extra: pip install 'commandants[io]'."
        )
    return sitk


class TempWorkspace:
    """A discoverable temp directory for materialized in-memory image inputs.

    Parameters
    ----------
    base:
        Parent directory for the temp folder (defaults to the system temp dir).
    keep:
        If True (default), files are left on disk after use so you can inspect
        them. If False, use as a context manager (or call :meth:`cleanup`) to
        delete them on exit.
    prefix:
        Prefix for the created temp directory name.
    """

    def __init__(
        self,
        base: Optional[str] = None,
        keep: bool = True,
        prefix: str = "commandants_",
    ) -> None:
        self.dir: str = tempfile.mkdtemp(prefix=prefix, dir=str(base) if base else None)
        self.keep: bool = keep
        self.files: List[str] = []
        self.inputs: Dict[str, str] = {}
        self._cache: Dict[int, str] = {}

    def materialize(self, image: Any, name: Optional[str] = None, suffix: str = ".nii.gz") -> str:
        """Write a SimpleITK image to a temp file and return its path.

        The same image object (by identity) is written only once and its path
        reused, so passing one image to several arguments produces one file.
        """
        key = id(image)
        if key in self._cache:
            return self._cache[key]

        sitk = require_sitk()
        idx = len(self._cache)
        base = name or f"input{idx}"
        # Avoid clobbering when two distinct images share a role name.
        candidate = f"{base}{suffix}"
        path = os.path.join(self.dir, candidate)
        n = 1
        while path in self.files:
            path = os.path.join(self.dir, f"{base}_{n}{suffix}")
            n += 1

        sitk.WriteImage(image, path)
        self._cache[key] = path
        self.files.append(path)
        if name:
            self.inputs[name] = path
        return path

    def cleanup(self) -> None:
        """Delete the temp directory and everything in it."""
        shutil.rmtree(self.dir, ignore_errors=True)
        self.files.clear()
        self.inputs.clear()
        self._cache.clear()

    def __enter__(self) -> "TempWorkspace":
        return self

    def __exit__(self, *exc: Any) -> None:
        if not self.keep:
            self.cleanup()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<TempWorkspace dir={self.dir!r} files={len(self.files)} keep={self.keep}>"


__all__ = ["TempWorkspace", "is_sitk_image", "require_sitk"]
