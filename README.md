# command**ANTs**

A thin, transparent Python wrapper for the [ANTs](https://github.com/ANTsX/ANTs)
command-line tools.

Unlike ANTsPyX — which mixes compiled bindings with opinionated defaults and
exposes only a curated slice of the CLI — `commandants` shells out to the ANTs
binaries directly and **hides nothing**:

- **Every option is reachable.** Typed builders cover the common flags; a
  `.extra_args(...)` escape hatch reaches anything else (present or future).
- **Every command is inspectable.** `.build_command()` / `.to_shell()` return the
  exact argv *without running anything* — so you can see, log, diff, and unit-test
  commands even on a machine with no ANTs installed.
- **The real `antsRegistration` grammar.** Compose arbitrary multi-stage
  pipelines, put **multiple metrics in one stage** (multivariate registration),
  and use **point-set metrics** (`PSE` / `ICP` / `JHCT`) to **constrain a warp
  with corresponding points** — the thing ANTsPyX won't let you do.

## Install

```bash
pip install commandants            # core, zero dependencies
pip install 'commandants[io]'      # + numpy/nibabel for result.load() and point CSVs
pip install 'commandants[dev]'     # + pytest
```

`commandants` calls the ANTs binaries, so you also need ANTs installed and either
on your `PATH`, pointed to by `$ANTSPATH`, or passed via `ants_path=...`.

## Quickstart

```python
from commandants import (
    AntsRegistration, Rigid, SyN, MI, CC, PSE, Convergence,
)

reg = AntsRegistration(
    dimensionality=3,
    output="out_",
    warped_output="out_Warped.nii.gz",
    write_composite_transform=True,
    verbose=True,
)

# center-of-mass initialization  ->  --initial-moving-transform [fixed,moving,1]
reg.initialize_from_images("fixed.nii.gz", "moving.nii.gz", init="center-of-mass")

# Stage 1: rigid, mutual information
reg.add_stage(
    transform=Rigid(gradient_step=0.1),
    metrics=MI("fixed.nii.gz", "moving.nii.gz", weight=1.0, bins=32,
               sampling="Regular", sampling_pct=0.25),
    convergence=Convergence([1000, 500, 250, 100], threshold=1e-6, window=10),
    shrink_factors=[8, 4, 2, 1],
    smoothing_sigmas=[3, 2, 1, 0],
)

# Stage 2: SyN, driven by CC *and* constrained by a point set
reg.add_stage(
    transform=SyN(gradient_step=0.1, update_field_variance=3, total_field_variance=0),
    metrics=[
        CC("fixed.nii.gz", "moving.nii.gz", weight=1.0, radius=4),
        PSE("fixed_points.csv", "moving_points.csv",   # <-- constrain the warp
            weight=0.5, point_set_sigma=1.0, sampling_pct=0.5),
    ],
    convergence=Convergence([100, 70, 50, 20]),
    shrink_factors=[8, 4, 2, 1],
    smoothing_sigmas=[3, 2, 1, 0],
)

print(reg.to_shell())     # inspect the exact command (no ANTs needed)
result = reg.run()        # execute; raises AntsRuntimeError on failure
warped = result.load("warped")   # needs the [io] extra
```

### Nothing is hidden

Reach any flag the typed API doesn't model yet:

```python
reg.extra_args("--use-estimate-learning-rate-once", "1")
```

### Apply transforms

```python
from commandants import AntsApplyTransforms

apply = AntsApplyTransforms(3, "moving.nii.gz", "fixed.nii.gz", "resampled.nii.gz",
                            interpolation="BSpline[3]")
apply.add_transform("out_1Warp.nii.gz")
apply.add_transform("out_0GenericAffine.mat")   # applied first (ANTs order)
apply.run()
```

### Preprocessing

```python
from commandants import N4BiasFieldCorrection

N4BiasFieldCorrection(3, "raw.nii.gz", "n4.nii.gz",
                      bias_output="bias.nii.gz",
                      shrink_factor=4,
                      convergence_iterations=[50, 50, 50, 50],
                      convergence_threshold=0.0,
                      bspline_distance=200).run()
```

## Design

```
commandants/
  core/           binary resolution, the AntsCommand base, result objects
  registration/   AntsRegistration, metrics (incl. PSE/ICP/JHCT), transforms, stages, apply
  preprocessing/  N4BiasFieldCorrection, ThresholdImage, ImageMath, ResampleImage
  io/             ANTs point-set CSV read/write
```

Every builder subclasses `AntsCommand`, so they all share `.build_command()`,
`.to_shell()`, `.run(...)`, `.extra_args(...)`, and a `CompletedAnts` result with
declared output paths and an optional lazy `.load()`.

## Status

v1 covers registration + core preprocessing. Segmentation (`Atropos`,
`KellyKapowski`) and motion correction (`antsMotionCorr`) are natural next
additions — the layered core makes them straightforward.

## License

MIT
