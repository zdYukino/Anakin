# Design

- Fix the camera API boundary inside viewer callbacks, using existing `MUJOCO_VERSION` and the official 3.11.0 signature boundary. Keep `mjv_movePerturb` scene arguments intact.
- Inspect other mouse API calls against installed bindings; limit changes to confirmed compatibility failures.
- Double-click selection is another confirmed failure: convert the one-element `mjv_select` skin output with `.item()` before assigning the integer `MjvPerturb.skinselect` property.
- Extend the existing viewer patch rather than changing the submodule revision. Validate against a temporary copy of the pinned revision without resetting the working submodule.
- Pin `mujoco==3.16.0` in `requirements.txt`, the root dynamic dependency source consumed by uv. Regenerate the lockfile and sync simulation dependencies while retaining the installed optional robot binding.
- Add headless regression tests under `tests/`, mocking GLFW input queries only and calling real MuJoCo camera/selection/perturbation APIs. Record desktop verification limits.
- Preserve unrelated root edits and the applied visualization patch. Rollback consists of reverting this task's hunks and dependency pin.
