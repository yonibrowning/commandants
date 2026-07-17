"""Transform models for ``antsRegistration``.

Each transform renders to the ``Name[params]`` string that follows a
``-t``/``--transform`` flag. Parameter order and names follow the ANTs
``antsRegistration --help`` output. Optional trailing parameters left as ``None``
are dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..core.params import bracket


class Transform:
    """Base class for all transforms."""

    name: str = ""

    def to_arg(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.to_arg()


# --------------------------------------------------------------------------- #
# Linear transforms -- a single gradient step parameter
# --------------------------------------------------------------------------- #
@dataclass
class _LinearTransform(Transform):
    gradient_step: float = 0.1

    def to_arg(self) -> str:
        return self.name + bracket(self.gradient_step)


@dataclass
class Translation(_LinearTransform):
    name: str = "Translation"


@dataclass
class Rigid(_LinearTransform):
    name: str = "Rigid"


@dataclass
class Similarity(_LinearTransform):
    name: str = "Similarity"


@dataclass
class Affine(_LinearTransform):
    name: str = "Affine"


@dataclass
class CompositeAffine(_LinearTransform):
    name: str = "CompositeAffine"


# --------------------------------------------------------------------------- #
# Deformable transforms
# --------------------------------------------------------------------------- #
@dataclass
class SyN(Transform):
    """Symmetric normalization.

    ``SyN[gradientStep,updateFieldVarianceInVoxelSpace,totalFieldVarianceInVoxelSpace]``
    """

    name: str = "SyN"

    def __init__(
        self,
        gradient_step: float = 0.1,
        update_field_variance: float = 3.0,
        total_field_variance: float = 0.0,
    ) -> None:
        self.gradient_step = gradient_step
        self.update_field_variance = update_field_variance
        self.total_field_variance = total_field_variance

    def to_arg(self) -> str:
        return self.name + bracket(
            self.gradient_step,
            self.update_field_variance,
            self.total_field_variance,
        )


@dataclass
class GaussianDisplacementField(Transform):
    """Gaussian-regularized displacement field (alias ``GD`` in ANTs docs).

    ``GaussianDisplacementField[gradientStep,updateFieldVarianceInVoxelSpace,totalFieldVarianceInVoxelSpace]``
    """

    name: str = "GaussianDisplacementField"

    def __init__(
        self,
        gradient_step: float = 0.1,
        update_field_variance: float = 3.0,
        total_field_variance: float = 0.0,
    ) -> None:
        self.gradient_step = gradient_step
        self.update_field_variance = update_field_variance
        self.total_field_variance = total_field_variance

    def to_arg(self) -> str:
        return self.name + bracket(
            self.gradient_step,
            self.update_field_variance,
            self.total_field_variance,
        )


@dataclass
class BSplineSyN(Transform):
    """B-spline SyN.

    ``BSplineSyN[gradientStep,updateFieldMeshSizeAtBaseLevel,<totalFieldMeshSizeAtBaseLevel=0>,<splineOrder=3>]``
    """

    name: str = "BSplineSyN"

    def __init__(
        self,
        gradient_step: float = 0.1,
        update_mesh_size: int = 26,
        total_mesh_size: Optional[int] = 0,
        spline_order: Optional[int] = None,
    ) -> None:
        self.gradient_step = gradient_step
        self.update_mesh_size = update_mesh_size
        self.total_mesh_size = total_mesh_size
        self.spline_order = spline_order

    def to_arg(self) -> str:
        return self.name + bracket(
            self.gradient_step,
            self.update_mesh_size,
            self.total_mesh_size,
            self.spline_order,
        )


@dataclass
class BSpline(Transform):
    """B-spline (elastic) transform.

    ``BSpline[gradientStep,meshSizeAtBaseLevel]``
    """

    name: str = "BSpline"

    def __init__(self, gradient_step: float = 0.1, mesh_size: int = 26) -> None:
        self.gradient_step = gradient_step
        self.mesh_size = mesh_size

    def to_arg(self) -> str:
        return self.name + bracket(self.gradient_step, self.mesh_size)


@dataclass
class TimeVaryingVelocityField(Transform):
    """Time-varying velocity field (unconstrained diffeomorphism).

    ``TimeVaryingVelocityField[gradientStep,numberOfTimeIndices,updateFieldVarianceInVoxelSpace,
    updateFieldTimeVariance,totalFieldVarianceInVoxelSpace,totalFieldTimeVariance]``
    """

    name: str = "TimeVaryingVelocityField"

    def __init__(
        self,
        gradient_step: float = 0.1,
        number_of_time_indices: int = 4,
        update_field_variance: float = 3.0,
        update_field_time_variance: float = 0.0,
        total_field_variance: float = 0.0,
        total_field_time_variance: float = 0.0,
    ) -> None:
        self.gradient_step = gradient_step
        self.number_of_time_indices = number_of_time_indices
        self.update_field_variance = update_field_variance
        self.update_field_time_variance = update_field_time_variance
        self.total_field_variance = total_field_variance
        self.total_field_time_variance = total_field_time_variance

    def to_arg(self) -> str:
        return self.name + bracket(
            self.gradient_step,
            self.number_of_time_indices,
            self.update_field_variance,
            self.update_field_time_variance,
            self.total_field_variance,
            self.total_field_time_variance,
        )


@dataclass
class Exponential(Transform):
    """Exponential (constant velocity field) transform.

    ``Exponential[gradientStep,updateFieldVarianceInVoxelSpace,velocityFieldVarianceInVoxelSpace,<numberOfIntegrationSteps>]``
    """

    name: str = "Exponential"

    def __init__(
        self,
        gradient_step: float = 0.1,
        update_field_variance: float = 3.0,
        velocity_field_variance: float = 0.0,
        integration_steps: Optional[int] = None,
    ) -> None:
        self.gradient_step = gradient_step
        self.update_field_variance = update_field_variance
        self.velocity_field_variance = velocity_field_variance
        self.integration_steps = integration_steps

    def to_arg(self) -> str:
        return self.name + bracket(
            self.gradient_step,
            self.update_field_variance,
            self.velocity_field_variance,
            self.integration_steps,
        )


@dataclass
class RawTransform(Transform):
    """Escape hatch: emit a transform string verbatim.

    Use when ANTs adds a transform this package doesn't yet model, e.g.
    ``RawTransform("BSplineExponential[0.1,26,0,4]")``.
    """

    spec: str = ""

    def to_arg(self) -> str:
        return self.spec


__all__ = [
    "Transform",
    "Translation",
    "Rigid",
    "Similarity",
    "Affine",
    "CompositeAffine",
    "SyN",
    "GaussianDisplacementField",
    "BSplineSyN",
    "BSpline",
    "TimeVaryingVelocityField",
    "Exponential",
    "RawTransform",
]
