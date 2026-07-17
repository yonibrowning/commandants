"""Registration: the ``antsRegistration`` builder, metrics, transforms, and apply tools."""

from __future__ import annotations

from .ants_registration import AntsRegistration
from .apply import AntsApplyTransforms, AntsApplyTransformsToPoints
from .metrics import (
    CC,
    GC,
    ICP,
    JHCT,
    MI,
    PSE,
    Demons,
    Mattes,
    MeanSquares,
    Metric,
    is_point_set_metric,
)
from .stage import Convergence, Stage
from .transforms import (
    Affine,
    BSpline,
    BSplineSyN,
    CompositeAffine,
    Exponential,
    GaussianDisplacementField,
    RawTransform,
    Rigid,
    Similarity,
    SyN,
    TimeVaryingVelocityField,
    Transform,
    Translation,
)

__all__ = [
    # command builders
    "AntsRegistration",
    "AntsApplyTransforms",
    "AntsApplyTransformsToPoints",
    # stage building blocks
    "Stage",
    "Convergence",
    # metrics
    "Metric",
    "MI",
    "Mattes",
    "CC",
    "MeanSquares",
    "Demons",
    "GC",
    "PSE",
    "ICP",
    "JHCT",
    "is_point_set_metric",
    # transforms
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
