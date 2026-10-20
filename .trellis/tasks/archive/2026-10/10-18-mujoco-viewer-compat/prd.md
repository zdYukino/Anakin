# MuJoCo viewer compatibility and dependency pin

## Goal

Restore mouse interaction in `uv run scripts/run_pipeline.py` with the latest stable MuJoCo and make dependency resolution reproducible.

## Background

- Installed and locked MuJoCo is 3.16.0, also the latest official release as of 2026-10-18: https://github.com/google-deepmind/mujoco/releases/tag/3.16.0.
- MuJoCo 3.11.0 removed the scene argument from `mjv_moveCamera`: https://mujoco.readthedocs.io/en/stable/changelog.html#version-3-11-0-july-27-2026.
- `third_party/mujoco_viewer/mujoco_viewer/callbacks.py:183` and `:321` still pass that argument, causing an uncaught TypeError when dragging or scrolling.
- `requirements.txt:13` declares unbounded `mujoco`; the root project imports this file as its dynamic dependencies.
- The viewer is a pinned submodule with existing visualization changes represented by `third_party/patches/mujoco_viewer.patch`. Preserve those changes and all pre-existing root work.

## Requirements

1. Mouse rotation, translation, zoom, selection and perturbation must work with MuJoCo 3.16.0 without the reported callback TypeError.
2. Keep existing support for older camera-call signatures through the viewer's existing version convention.
3. Preserve the fix in the tracked viewer patch so a fresh submodule checkout receives the same behavior.
4. Pin MuJoCo to exactly 3.16.0 in the authoritative dependency declaration and regenerate `uv.lock` with uv.
5. Add meaningful regression checks using real MuJoCo bindings and document the patch/version contract.

## Acceptance Criteria

- Camera drag and scroll regression tests pass against installed 3.16.0 bindings and fail on the original callback implementation.
- Selection/perturbation call paths are checked for API compatibility; existing visualization changes remain intact.
- The tracked patch applies cleanly to the pinned submodule revision and reproduces the working source changes.
- `uv lock --check` succeeds and an installed-version check reports 3.16.0 after sync.
- Relevant lint/checks pass; any inability to exercise a real desktop window is recorded explicitly.

## Out of Scope

- Changing robot control, policy behavior, joystick threading or general process shutdown.
- Upgrading the viewer submodule revision or unrelated dependencies.
- Committing unrelated pre-existing work.

## Planning Status

Task creation and final planning summary approved by the user. Implementation authorized with `实施`.
