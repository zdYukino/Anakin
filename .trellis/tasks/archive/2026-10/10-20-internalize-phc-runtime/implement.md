# Implementation Plan

## Activation prerequisites

- [x] Task creation/scope authorized; current state researched and recorded.
- [x] Final PRD convergence pass; scope, exclusions, acceptance, design, and context manifests prepared.
- [x] Present the final planning summary and receive explicit approval in a subsequent user message (2026-10-20: user said “开始实现”).
- [x] Run `task.py start` only after that approval.

Use Trellis implement/check agents for Phase 2 per this project's Codex auto-dispatch setting. Dispatch prompts begin with the active task path. Give each worker explicit file ownership and shared-worktree instructions. Keep dependent baseline/runtime/controller/removal stages sequential; do not parallelize source removal with consumers still being migrated.

## 1. Establish compatibility evidence

- [x] Load applicable project guidelines; existing PHC specs are placeholders, so use curated research/shared guides and record actual new contracts as part of finish-work.
- [x] Retrieve the remaining fixed-version source and H1 YAML/XML resource closure in temporary storage; do not initialize the old PHC gitlink.
- [x] Confirm per-file/function/asset provenance and notices; avoid transplanting unclear poselib code.
- [x] Reproduce the local `phc.patch` behavior on the reference path. Include only numerical-neutral import/setup glue needed for current Python, and record it exactly.
- [x] Run the isolated reference harness on all three checked-in samples. Record frame/joint/body shapes, heading/offset/time cases, and compact output fixtures with source hashes and numerical tolerances.
- [x] Identify all fields and metadata used by all four controllers; include a multi-clip derived case and preserve actual supported optional behavior.

## 2. Add internal runtime and resources

- [x] Add bounded loader, kinematics, rotation helper subset, metadata, and source notices under `robojudo/motion/`.
- [x] Integrate effective G1 addon resources and H1 resources. Validate any attempted reuse of existing simulation XML against the reference tree before choosing it.
- [x] Preserve axis-angle loading, extra-node handling, quaternion conventions, smoothed velocities, temporal interpolation, and heading/offset behavior.
- [x] Add meaningful numerical tests; compare with baseline and independent small analytical cases.
- [x] Verify that imports/load/query do not mutate `torch.Tensor.numpy`, initialize multiprocessing managers, or require excluded training/mesh packages.

## 3. Migrate consumers and environment

- [x] Redirect `MotionCtrl` imports and `MotionCtrlCfg.PhcCfg` resource resolution. Preserve caller-facing config fields, YAML names, motion paths, and controller payloads.
- [x] Check `MotionH2HCtrl`, `MotionKungfuBotCtrl`, `MotionTwistCtrl`, G1/H1 config variants, and the kinematics diagnostic consumer.
- [x] Add headless load/query/controller coverage using current G1/H1 sample motions; provide the FK-enabled environment required by H2H.
- [x] Check targeted package discovery/resource inclusion. Declare any truly required missing dependency instead of importing the old PHC package.
- [x] Refresh uv metadata/lock only when needed; validate locked sync using the existing sim/unitree extras. Keep their pins unchanged.

## 4. Remove the old dependency after compatibility passes

- [x] Inspect PHC checkout status before deleting any link or file; preserve user local work.
- [x] Remove the tracked `third_party/phc` gitlink and its `.gitmodules` registration.
- [x] Remove PHC/poselib from `submodule_cfg.yaml`, and retire active PHC patch/addon installation after preserving runtime resources/notices. Unrelated submodules remain unchanged.
- [x] Remove obsolete PHC package registration from `.trellis/config.yaml`; load `trellis-meta` for that configuration edit. Keep historical tasks/journals as history rather than rewriting them.
- [x] Update README and controller/policy docs, including fitting-related links and supported motion locations. Keep PHC attribution and format folder names.
- [x] Confirm root requirements, uv sources/extras, lock, and install scripts contain no external-PHC requirement.

## 5. Verify and finish

Candidate commands below are run after the associated files exist; these are plans, not completed checks:

```bash
uv sync --locked --extra sim --extra unitree
uv run --locked --extra sim --extra unitree --inexact python -m unittest discover -s tests -p 'test_phc*.py'
uv run --locked --extra sim --extra unitree --inexact python -m unittest discover -s tests -p 'test_mujoco_viewer_callbacks.py'
git diff --check
git submodule status
git ls-files --stage third_party/phc
rg -n 'third_party/phc|from phc|import phc|from poselib|import poselib' robojudo .gitmodules submodule_cfg.yaml pyproject.toml requirements.txt uv.lock README.md docs
```

- [x] Run the pinned Ruff 0.12.7 check/format checks on changed runtime/controller/test files using the project's established tooling. Do not exclude new numerical runtime code from lint just because legacy config excludes `controller/motion_lib`.
- [x] Ensure tests explicitly block PHC/poselib imports and run without reference source on `sys.path`. Assert shapes, values, finite outputs, error behavior, and no global side effects.
- [x] Inspect targeted registry imports. The broad existing `test_full_imports.py` expects other optional modules; report unrelated optional-module failures separately rather than changing them to hide failures.
- [x] Run the final Trellis check agent, capture useful contracts in specs, and update task evidence.
- [x] Present and obtain approval for the concrete commit plan (2026-10-20: user said “提交并归档”).
- [x] Create the approved work commit (`0ff914f74ec9489c53320f40f4352dc1f543071d`); archive and session recording proceed through the authorized `trellis-finish-work` handoff. Implementation and validation are complete.

## Rollback points and sensitive files

- Preserve the original pinned+patched reference before numerical extraction.
- Keep runtime addition, consumer redirection, and old dependency removal logically separate.
- Sensitive boundaries: `ctrl_cfgs.py`, `motion_ctrl.py`, robot XML/YAML, `.gitmodules`/gitlink, `submodule_cfg.yaml`, `.trellis/config.yaml`, packaging metadata, and `uv.lock`.
- Do not use an unqualified `submodule_install.py`: it resets/cleans selected initialized submodules and is unnecessary for the new runtime.
- Do not perform GUI or real-robot execution as part of this task's default validation.
