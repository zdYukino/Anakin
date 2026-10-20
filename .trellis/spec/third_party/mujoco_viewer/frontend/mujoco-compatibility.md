# MuJoCo Mouse Callback Compatibility

## 1. Scope / Trigger

Use this contract when changing viewer mouse callbacks or upgrading MuJoCo.
The application reaches these callbacks through `MujocoEnv.step()` →
`MujocoViewer.render()` → `glfw.poll_events()`. An exception in a callback is
re-raised by GLFW and exits the unguarded pipeline loop.

## 2. Signatures

MuJoCo < 3.11.0:

```python
mujoco.mjv_moveCamera(model, action, reldx, reldy, scene, camera)
```

MuJoCo >= 3.11.0:

```python
mujoco.mjv_moveCamera(model, action, reldx, reldy, camera)
```

Both versions continue to use scene for perturbation:

```python
mujoco.mjv_movePerturb(model, data, action, reldx, reldy, scene, perturb)
mujoco.mjv_initPerturb(model, data, scene, perturb)
```

The removal is documented in the [official 3.11.0 changelog](https://mujoco.readthedocs.io/en/stable/changelog.html#version-3-11-0-july-27-2026).

## 3. Contracts

- Apply the existing `MUJOCO_VERSION` tuple convention at the camera API boundary.
- Both cursor drag and scroll paths must dispatch the supported camera signature.
- `mjv_select` writes the skin ID into a one-element NumPy array. Assign
  `selskin.item()` to the integer `MjvPerturb.skinselect` property; assigning
  the array directly raises TypeError with the current bindings.
- `requirements.txt` is the authoritative root dependency source through
  `tool.setuptools.dynamic.dependencies`. The validated version is `mujoco==3.16.0`.
- Regenerate `uv.lock` with `uv lock --refresh-package robojudo` after changing
  the dependency declaration. Because dependencies come from a dynamic file, a
  plain `uv lock` can reuse stale root metadata. Check the root `requires-dist`
  specifier as well as the locked package version; sync with
  `--reinstall-package robojudo` to refresh installed project metadata.
- The viewer is pinned to a published commit from
  `git@github.com:zdYukino/mujoco-python-viewer.git`, on the fork's
  `anakin-improvements` branch. The original repository is the local `upstream`
  remote. Persist new source improvements as fork commits and update the parent
  gitlink only after the commit is available remotely.
- The current fork commit includes the visualization and mouse fixes. Do not
  reapply `third_party/patches/mujoco_viewer.patch` from setup commands or
  `submodule_cfg.yaml`. That file remains a historical patch against upstream
  `31af945ef640d276a3bafe5e9b858d80c46c8509`.
- Never reset local submodule edits to inspect or verify an old patch; use a
  temporary checkout. Keep the validated base when publishing unrelated fixes.

## 4. Validation & Error Matrix

| Condition | Required outcome |
| --- | --- |
| Camera drag or scroll on 3.16.0 | Native camera state updates without TypeError |
| Older camera API | Scene argument remains present |
| Active body perturbation | Scene passed to perturbation API; camera path bypassed |
| Double-click selects a body | Native skin ID array converted to an integer before assignment |
| Six camera arguments on 3.11+ | TypeError propagated from GLFW; regression must detect this |
| Fresh pinned fork checkout, no patch | Same fixed source as working submodule |
| Historical patch applied to fork commit | Duplicate change; setup must not attempt this |
| Dependency pin changes | Refresh root metadata, then verify the exact lock `requires-dist` constraint and installed metadata |

## 5. Good / Base / Bad Cases

- Good: rotate, translate and zoom using real 3.16.0 bindings in headless tests;
  retain the legacy argument contract in a focused compatibility test.
- Base: no button pressed leaves camera and cursor state untouched.
- Bad: remove scene from every MuJoCo API call, or fix cursor dragging while
  leaving the scroll callback on the removed signature.

## 6. Tests Required

```bash
uv run --locked --extra sim --inexact python -m unittest discover -s tests -p 'test_mujoco_viewer_callbacks.py'
uv lock --check
```

Use real model/data/camera/scene objects for current-version checks. Mock GLFW
input queries so tests do not require a desktop. Assert observable camera or
perturbation state changes, and exercise selection/perturbation with the native
bindings. Confirm the original camera calls fail to establish regression value.
Headless tests do not replace an interactive desktop smoke test; record whether
the latter was performed.

For fork publication, verify the remote branch SHA and parent gitlink target,
then compare a temporary clean checkout with the modified source bytes. Do not
run the legacy installer as a validation command: it resets and cleans existing
submodule worktrees.

## 7. Wrong vs Correct

Wrong on 3.11+:

```python
mujoco.mjv_moveCamera(model, action, dx, dy, scene, camera)
```

Correct on 3.11+:

```python
mujoco.mjv_moveCamera(model, action, dx, dy, camera)
```

Keep the six-argument call only in the legacy version branch. Do not catch and
silence the TypeError, which would disable camera controls and hide API drift.
