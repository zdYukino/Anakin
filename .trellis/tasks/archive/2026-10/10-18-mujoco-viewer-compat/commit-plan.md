# Commit Batch — Completed

The worktree already contained an uncommitted uv environment setup before this
task began. The refreshed `uv.lock` depends on that `pyproject.toml` configuration
(editable local packages, the explicit PyTorch index and optional extras). A
reproducible commit batch therefore needs the user's permission to include that
pre-existing setup alongside this fix. The user approved this batch with
`提交` on 2026-10-20. Both commits are complete on `release`; no push was made.

## Proposed commits, in order

1. `dde491d build: configure uv environment for simulation`
   - Pre-existing uv setup changes in `.gitignore`, `README.md`, `pyproject.toml`
     and `submodule_cfg.yaml`.
   - Pre-existing `third_party/patches/unitree_cpp.patch` and its documentation
     paragraph in `third_party/patches/README.md`.
2. `ec39201 fix: support MuJoCo 3.16 mouse callbacks and pin engine`
   - `requirements.txt`: exact engine pin.
   - `uv.lock`: resolved environment including that pin. This was already an
     untracked file before this task and will be included as a whole file.
   - `third_party/patches/mujoco_viewer.patch`: callback compatibility and skin ID
     conversion, preserving the existing visualization patch.
   - `tests/test_mujoco_viewer_callbacks.py`: six native-binding regressions.
   - This task's viewer and dependency documentation paragraph in
     `third_party/patches/README.md`.

## Other pre-existing dirty files, excluded

- `.gitattributes`: Trellis journal merge configuration, unrelated to this fix.

## Local records

`.trellis/` is intentionally ignored by the current repository configuration.
The task, verification notes and compatibility spec have been saved locally;
they will not be force-added. The working viewer's callback change is persisted
through the tracked patch, without committing a new submodule revision.

## Result

The approved batch was committed as listed. `.gitattributes` remains untouched
and untracked. Task records and journal stay local without bookkeeping commits,
honoring the repository's ignored `.trellis/` configuration.
