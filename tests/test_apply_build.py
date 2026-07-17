"""Command-construction tests for the apply-transforms wrappers."""

from __future__ import annotations

from commandants import AntsApplyTransforms, AntsApplyTransformsToPoints


def test_apply_transforms_with_inversion_and_order():
    apply = AntsApplyTransforms(
        3, "moving.nii.gz", "fixed.nii.gz", "resampled.nii.gz",
        interpolation="BSpline[3]",
        default_value=0,
    )
    apply.add_transform("out_1Warp.nii.gz")
    apply.add_transform("out_0GenericAffine.mat", invert=True)

    argv = apply.build_command()
    assert argv == [
        "antsApplyTransforms",
        "--dimensionality", "3",
        "--input", "moving.nii.gz",
        "--reference-image", "fixed.nii.gz",
        "--output", "resampled.nii.gz",
        "--interpolation", "BSpline[3]",
        "--default-value", "0",
        "--transform", "out_1Warp.nii.gz",
        "--transform", "[out_0GenericAffine.mat,1]",
        "--verbose", "0",
    ]


def test_apply_transforms_image_type_name():
    apply = AntsApplyTransforms(
        4, "ts.nii.gz", "ref.nii.gz", "out.nii.gz", image_type="time-series"
    )
    argv = apply.build_command()
    assert "--input-image-type" in argv
    assert argv[argv.index("--input-image-type") + 1] == "3"


def test_apply_transforms_to_points():
    ap = AntsApplyTransformsToPoints(2, "pts_in.csv", "pts_out.csv", precision=0)
    ap.add_transform("out_0GenericAffine.mat", invert=True)
    argv = ap.build_command()
    assert argv == [
        "antsApplyTransformsToPoints",
        "--dimensionality", "2",
        "--input", "pts_in.csv",
        "--output", "pts_out.csv",
        "--transform", "[out_0GenericAffine.mat,1]",
        "--precision", "0",
    ]


def test_declared_output():
    apply = AntsApplyTransforms(3, "m.nii", "f.nii", "o.nii")
    assert apply.declared_outputs() == {"output": "o.nii"}
