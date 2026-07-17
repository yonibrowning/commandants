"""``antsRegistration`` wrapper -- the centerpiece of commandants.

Unlike ANTsPyX's ``ants.registration()`` (which expands a curated parameter set
into a fixed, canned sequence of stages), :class:`AntsRegistration` models the
real command grammar: a list of stages, each with its own transform, one or more
metrics, and multi-resolution schedule. That is what makes multivariate and
point-constrained registration possible.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Sequence, Union

from ..core.params import bracket, xjoin
from ..core.runner import AntsCommand
from .metrics import Metric
from .stage import Convergence, Stage
from .transforms import Transform

PathLike = Union[str, Path]

# initializationFeature codes for image-based initial transforms.
_INIT_FEATURES = {"geometric": 0, "center-of-mass": 1, "com": 1, "origin": 2}


class AntsRegistration(AntsCommand):
    """Builder for a full ``antsRegistration`` invocation.

    Parameters
    ----------
    dimensionality:
        Image dimensionality (2, 3, or 4).
    output:
        Output transform prefix (the ANTs ``outputTransformPrefix``).
    warped_output, inverse_warped_output:
        Optional warped-image outputs; when either is given the ``--output``
        flag is emitted in its bracketed ``[prefix,warped,inverse]`` form.
    interpolation:
        Final-resampling interpolator (e.g. ``"Linear"``, ``"BSpline"``).
    winsorize:
        ``(lower_quantile, upper_quantile)`` for intensity winsorization.
    use_histogram_matching:
        Match moving-to-fixed histograms before registration.
    collapse_output_transforms:
        Collapse the transform stack (ANTs default is on).
    write_composite_transform:
        Also write ``{prefix}Composite.h5`` / ``{prefix}InverseComposite.h5``.
    use_float:
        Use single-precision computation.
    random_seed:
        Deterministic seed.
    restrict_deformation:
        Per-dimension deformation weights, e.g. ``[1, 1, 0]`` to forbid motion
        along the 3rd axis.
    write_interval_volumes:
        Write intermediate volumes every N iterations (debugging).
    verbose:
        Verbose ANTs output.
    ants_path:
        Explicit directory containing the ANTs binaries.
    """

    binary_name = "antsRegistration"

    def __init__(
        self,
        dimensionality: int,
        output: Optional[PathLike] = None,
        *,
        warped_output: Optional[PathLike] = None,
        inverse_warped_output: Optional[PathLike] = None,
        interpolation: Optional[str] = None,
        winsorize: Optional[Sequence[float]] = None,
        use_histogram_matching: Optional[bool] = None,
        collapse_output_transforms: Optional[bool] = None,
        write_composite_transform: bool = False,
        use_float: Optional[bool] = None,
        random_seed: Optional[int] = None,
        restrict_deformation: Optional[Sequence[float]] = None,
        write_interval_volumes: Optional[int] = None,
        verbose: bool = False,
        ants_path: Optional[PathLike] = None,
    ) -> None:
        super().__init__(ants_path=ants_path)
        self.dimensionality = dimensionality
        self.output = output
        self.warped_output = warped_output
        self.inverse_warped_output = inverse_warped_output
        self.interpolation = interpolation
        self.winsorize = winsorize
        self.use_histogram_matching = use_histogram_matching
        self.collapse_output_transforms = collapse_output_transforms
        self.write_composite_transform = write_composite_transform
        self.use_float = use_float
        self.random_seed = random_seed
        self.restrict_deformation = restrict_deformation
        self.write_interval_volumes = write_interval_volumes
        self.verbose = verbose

        self._initial_transforms: List[str] = []
        self._fixed_mask: Optional[PathLike] = None
        self._moving_mask: Optional[PathLike] = None
        self.stages: List[Stage] = []

    # -- initial transforms ---------------------------------------------------
    def initialize_from_images(
        self,
        fixed: PathLike,
        moving: PathLike,
        init: Union[str, int] = "center-of-mass",
    ) -> "AntsRegistration":
        """Add an image-based initial moving transform.

        ``init`` selects the ANTs initialization feature: ``"geometric"`` (0),
        ``"center-of-mass"`` (1, the default), or ``"origin"`` (2). An integer is
        passed through unchanged.
        """
        if isinstance(init, str):
            if init not in _INIT_FEATURES:
                raise ValueError(
                    f"init must be one of {sorted(_INIT_FEATURES)} or an int; got {init!r}"
                )
            feature = _INIT_FEATURES[init]
        else:
            feature = int(init)
        self._initial_transforms.append(bracket(fixed, moving, feature))
        return self

    def add_initial_moving_transform(
        self, transform: PathLike, use_inverse: bool = False
    ) -> "AntsRegistration":
        """Prepend an existing transform file as the initial moving transform."""
        if use_inverse:
            self._initial_transforms.append(bracket(transform, True))
        else:
            self._initial_transforms.append(str(transform))
        return self

    # -- masks ----------------------------------------------------------------
    def set_masks(
        self,
        fixed_mask: Optional[PathLike] = None,
        moving_mask: Optional[PathLike] = None,
    ) -> "AntsRegistration":
        """Set the fixed and/or moving metric masks (applied to all stages)."""
        self._fixed_mask = fixed_mask
        self._moving_mask = moving_mask
        return self

    # -- stages ---------------------------------------------------------------
    def add_stage(
        self,
        transform: Transform,
        metrics: Union[Metric, Sequence[Metric]],
        convergence: Convergence,
        shrink_factors: Sequence[int],
        smoothing_sigmas: Sequence[float],
        smoothing_units: Optional[str] = "vox",
    ) -> "AntsRegistration":
        """Append a registration stage. ``metrics`` may be one metric or many."""
        metric_list = [metrics] if isinstance(metrics, Metric) else list(metrics)
        stage = Stage(
            transform=transform,
            metrics=metric_list,
            convergence=convergence,
            shrink_factors=shrink_factors,
            smoothing_sigmas=smoothing_sigmas,
            smoothing_units=smoothing_units,
        )
        self.stages.append(stage)
        return self

    def add(self, stage: Stage) -> "AntsRegistration":
        """Append a pre-built :class:`Stage`."""
        self.stages.append(stage)
        return self

    # -- argv assembly --------------------------------------------------------
    def _output_arg(self) -> str:
        if self.warped_output is not None or self.inverse_warped_output is not None:
            return bracket(self.output, self.warped_output, self.inverse_warped_output)
        return str(self.output)

    def _build_args(self) -> List[str]:
        if not self.stages:
            raise ValueError("At least one stage must be added before running.")
        if self.output is None:
            raise ValueError("An output prefix must be set.")

        args: List[str] = ["--dimensionality", str(self.dimensionality)]

        if self.use_float is not None:
            args += ["--float", "1" if self.use_float else "0"]

        args += ["--output", self._output_arg()]

        if self.interpolation is not None:
            args += ["--interpolation", self.interpolation]

        if self.use_histogram_matching is not None:
            args += [
                "--use-histogram-matching",
                "1" if self.use_histogram_matching else "0",
            ]

        if self.winsorize is not None:
            args += ["--winsorize-image-intensities", bracket(*self.winsorize)]

        if self.write_composite_transform:
            args += ["--write-composite-transform", "1"]

        if self.collapse_output_transforms is not None:
            args += [
                "--collapse-output-transforms",
                "1" if self.collapse_output_transforms else "0",
            ]

        if self.restrict_deformation is not None:
            args += ["--restrict-deformation", xjoin(self.restrict_deformation)]

        if self.random_seed is not None:
            args += ["--random-seed", str(self.random_seed)]

        if self.write_interval_volumes is not None:
            args += ["--write-interval-volumes", str(self.write_interval_volumes)]

        for tx in self._initial_transforms:
            args += ["--initial-moving-transform", tx]

        if self._fixed_mask is not None or self._moving_mask is not None:
            args += ["--masks", bracket(self._fixed_mask, self._moving_mask)]

        for stage in self.stages:
            args += stage.to_args()

        args += ["--verbose", "1" if self.verbose else "0"]
        return args

    def declared_outputs(self) -> dict:
        """Predictable, user-named outputs (warped images and composites).

        The numbered per-transform files (e.g. ``{prefix}0GenericAffine.mat``,
        ``{prefix}1Warp.nii.gz``) depend on the exact stage stack and are not
        declared here; inspect the output directory or the ANTs log for those.
        """
        outputs: dict[str, str] = {}
        if self.warped_output is not None:
            outputs["warped"] = str(self.warped_output)
        if self.inverse_warped_output is not None:
            outputs["inverse_warped"] = str(self.inverse_warped_output)
        if self.write_composite_transform and self.output is not None:
            outputs["composite"] = f"{self.output}Composite.h5"
            outputs["inverse_composite"] = f"{self.output}InverseComposite.h5"
        return outputs


__all__ = ["AntsRegistration"]
