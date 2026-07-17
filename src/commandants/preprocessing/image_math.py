"""``ImageMath`` wrapper (positional-argument tool).

ANTs usage::

    ImageMath Dim out.nii <operation> input1 <input2OrFloat> ...

Examples
--------
Morphological dilation by 2 voxels::

    ImageMathOp("MD", mask, 2)  # -> ImageMath D out MD mask 2

Multiply two images::

    ImageMathOp("m", a, b)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Union

from ..core.runner import AntsCommand

PathLike = Union[str, Path]


class ImageMath(AntsCommand):
    """Run an ``ImageMath`` operation with arbitrary operands.

    Parameters
    ----------
    dimensionality:
        Image dimensionality.
    output_image:
        Output path.
    operation:
        The ImageMath operation name, e.g. ``"MD"``, ``"ME"``, ``"m"``, ``"+"``,
        ``"Normalize"``, ``"PadImage"``.
    operands:
        Zero or more operands (image paths or numeric parameters), passed through
        in order exactly as ANTs expects.
    """

    binary_name = "ImageMath"

    def __init__(
        self,
        dimensionality: int,
        output_image: PathLike,
        operation: str,
        *operands: Any,
        ants_path: Optional[PathLike] = None,
    ) -> None:
        super().__init__(ants_path=ants_path)
        self.dimensionality = dimensionality
        self.output_image = output_image
        self.operation = operation
        self.operands = list(operands)

    def _build_args(self) -> List[str]:
        args = [
            str(self.dimensionality),
            str(self.output_image),
            str(self.operation),
        ]
        # Operands may be image paths, in-memory images, or numeric parameters.
        args += [self._resolve(op, f"operand{i}") for i, op in enumerate(self.operands)]
        return args

    def declared_outputs(self) -> dict:
        return {"output": str(self.output_image)}


__all__ = ["ImageMath"]
