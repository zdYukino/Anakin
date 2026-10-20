# Approved Work Commit

Implementation is verified. The user approved this concrete Phase 3.4 commit and archive plan on 2026-10-20 with “提交并归档”.

## One coherent commit

`feat: internalize PHC motion runtime and remove submodule`

Include:

- `robojudo/motion/` — runtime, three robot resource variants, source/license notices.
- `robojudo/controller/motion_ctrl.py` and `robojudo/controller/ctrl_cfgs.py` — internal imports and resource resolution.
- `tests/test_phc_motionlib.py`, `tests/test_phc_controllers.py`, `tests/test_phc_reference.py`, `tests/fixtures/phc/`, and `scripts/phc_reference/` — numerical/controller regressions and independent reproducible baseline.
- `pyproject.toml` — package discovery and internal resource/notice distribution.
- `.gitmodules`, deletion of `third_party/phc` gitlink, and `submodule_cfg.yaml` — remove the original PHC installation link.
- `README.md` and `third_party/patches/README.md` — installation and historical provenance guidance.
- **Only PHC-specific edits** to `docs/controller.md` and `docs/policy.md`, using [task-only patch record](./docs-task-only.json) against their existing HEAD versions.
- `.trellis/config.yaml`, `.trellis/spec/robojudo/`, and this task's files — internal package mapping, executable contracts, planning and validation evidence.

`requirements.txt` and `uv.lock` are unchanged because no dependency change was needed. Other submodule code/pins and historical PHC patch/addon files are unchanged.

## Existing parallel work excluded

These files had Chinese-translation edits before implementation:

- `docs/controller.md`
- `docs/policy.md`
- `docs/environment.md`
- `docs/unitree_setup.md`

Do not stage the full working versions of the first two files. The reviewed task-only patch applies equivalent PHC documentation changes to their original English HEAD content. Apply that patch to the Git index only after approval, leaving the translated working copies untouched. The resulting remaining worktree differences are the user's existing translations, not missing runtime migration work.

The latter two files were not edited by this task and are excluded entirely. Do not include unrelated bootstrap task files or any other unexpected concurrent changes.

## Staging and finish safeguards

- `.gitmodules` and the PHC gitlink deletion are already staged because Git required coherent submodule metadata for removal; no commit exists.
- Stage the above task paths explicitly, not `git add .`.
- Materialize the exact `patch` text from `docs-task-only.json`, verify its recorded SHA-256, apply it only to the index, and verify the staged documentation diffs contain no unrelated translation.
- Verify staged/unstaged path classification and whitespace once more before committing.
- After the approved work commit, archive only this task and record the session with that work-commit hash. Do not push or merge.

The task-only patch was successfully applied to temporary HEAD document copies before this plan was prepared. Its SHA-256 is `9b48de9e13d85ce12f8f7eb8ef6e20adfcd3d1530ec2608cdbc37470a9cf49e2`.

The exact patch is stored as escaped JSON text to preserve unified-diff context whitespace without introducing trailing-whitespace errors into task artifacts. A readable materialized copy is available at `/tmp/anakin-phc-docs-before/task-only-head.patch`.

## Execution

The approved work commit is `0ff914f74ec9489c53320f40f4352dc1f543071d`. Staged documentation bytes matched the reviewed patch; all four existing translated working files remained byte-identical.
