# Implementation and Validation Results

Validated on 2026-10-20 on `feat/internalize-phc-runtime`, against parent baseline `3d01ec2` and pinned PHC `f8e75fb94918140e85db9744abf1f3b7667428a1` plus the existing local patch.

## Delivered behavior

- `robojudo/motion/` contains the bounded PHC-format loader, deterministic clip selection, FK, reference interpolation, minimal skeleton metadata, and resource resolver.
- Existing `MotionCtrl`, H2H, KungfuBot, and TWIST controllers use this internal facade. Their public config names, motion paths, and supported payloads are preserved.
- G1 23/29-DOF and H1 YAML/MJCF resources are included without graphics mesh requirements. Full XML structural comparison confirmed only documented mesh declarations/geoms and meshdir were removed.
- Required source/license notices are included. No poselib source is distributed; source/resource hashes and local model/helper changes are documented in `robojudo/motion/SOURCE.md`.
- The PHC gitlink, `.gitmodules` stanza, installer entry, and empty checkout directory are removed. Trellis now maps the internal `robojudo` package to real backend specs. The other three gitlinks retain their original hashes.
- `pyproject.toml` discovers the internal subpackages and includes YAML/XML/notices. Existing requirements and `uv.lock` required no dependency change: neither contained an original-PHC requirement.
- Historical PHC patch/addon files remain solely as reproducible source/reference and external fitting research inputs, not active installation/runtime links.
- Installation/controller/policy docs are updated. Pre-existing Chinese translations in four documentation files remain in the worktree and are excluded from the proposed work commit.

## Independent numerical compatibility

The reference generator runs the pinned original PHC numerical code with the complete existing local patch in a separate process. Its documented shims only satisfy unused imports/setup and do not replace numerical code with the new runtime.

| Measurement | Result |
| --- | --- |
| Robot variants | G1 23-DOF, G1 29-DOF, H1 19-DOF |
| Query batches / states | 48 / 450 |
| Arrays / compared fields | 864 / 18 (17 state fields plus root query) |
| Maximum absolute difference | **0.0 for every compared field; bitwise equal** |
| Cases | Identity/absent/nonidentity heading; offsets; exact/intermediate/start/end/out-of-range times; future references; mixed two-clip slots and clip switching |
| Reproduction | Regenerated fixture files are byte-identical; generator/source/resource hashes recorded in provenance |

Normal tests use committed fixtures only: no network, PHC checkout, external poselib, or temporary reference source is required.

Near-zero angular velocities initially differed because a generic vector reduction changed float32 addition order before `acos`. Preserving standard Hamilton component evaluation order restored exact parity without relaxing tolerances. The final review also corrected empty/malformed input errors and the original directory key rule (`first.v1.pkl` uses key `first`).

## Checks run

| Check | Result |
| --- | --- |
| `python -m unittest discover -s tests -p 'test_phc*.py'` | **25 passed**: 15 runtime/validation, 7 controller, 3 reference tests |
| `python -m unittest discover -s tests -p 'test_mujoco_viewer_callbacks.py'` | **6 passed** |
| Ruff 0.12.7 lint / format | **Passed**, 13 scoped Python files |
| Scoped compile checks | **Passed**; the root project has no standalone configured type-checker |
| `uv lock --check --offline` | **Passed**, 69 packages resolved |
| `uv sync --locked --extra sim --extra unitree --offline` | **Passed**, root editable package rebuilt, no new dependencies |
| Final wheel build | **Passed** using offline cached build requirements |
| Final wheel verification | All **18** runtime/resource/notice files match final source bytes; all three packaged models load in MuJoCo and return finite correctly shaped references, with external runtime imports explicitly blocked and PHC checkout absent |
| `git diff --check`, staged diff check | **Passed** |
| Trellis context manifests / package mapping | **Passed**, 5 valid entries per manifest, internal package/spec visible |
| Remaining submodule pins | **Unchanged** for viewer, unitree_cpp, and zed_proxy |

The final wheel is a verification artifact at `/tmp/anakin-phc-wheel-final/`; it is not required by normal source installation.

The final staged-file check additionally removed inherited trailing whitespace from the three bundled YAML files and PHC license. Parsed YAML values and the license's non-whitespace text were verified identical; no executable code or reference math changed.

## Existing environment limitations

The broad `test_full_imports.py` ran five tests: three passed, two registry groups failed because of these unchanged optional/environment requirements:

- `KeyboardCtrl`: no available X connection in the test environment.
- `TwistRedisCtrl`: optional `redis` package is not installed.
- `UnitreeEnv`: optional `unitree_sdk2py` package is not installed; the installed C++ backend `UnitreeCppEnv` imports successfully.

All four PHC-backed controller classes, all configs, policies, and pipelines import successfully. These optional-module issues were not hidden or expanded into this task.

The old H2H `extra_motion_data=True` frequency/phase hook was absent from original MotionLibReal; this migration preserves the default supported path rather than adding that separate feature. Training/SMPL/height-fitting services and new GPU guarantees remain outside the approved scope.

## Workflow state

Implementation, independent review, specs, and acceptance checks are complete. The user approved the concrete work commit and task archive on 2026-10-20. The work commit is `0ff914f74ec9489c53320f40f4352dc1f543071d`. The authorized finish workflow archives this task and records the session journal after that work commit. No push is part of this work.
