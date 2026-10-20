# Verification

## Implementation checks

- Six regression tests pass against real MuJoCo 3.16.0 bindings without opening a desktop window. Coverage includes four drag actions, bidirectional scroll, the 3.11.0 signature boundary, a legacy signature bridge, double-click body selection and Ctrl perturbation/release.
- Loading the original callback source into the same suite reproduces seven TypeError subtest errors. The modified callbacks pass all six tests.
- Ruff 0.12.7 passes for the new test module. Root configuration excludes vendored third-party source; native source whitespace checks pass.
- `uv lock --refresh-package robojudo` and `uv sync --extra sim --extra unitree --inexact --reinstall-package robojudo` succeed.
- `uv lock --check` passes. Lock `requires-dist`, installed `mujoco.__version__` and installed root dependency metadata all confirm `==3.16.0`.
- The tracked patch applies to pinned viewer revision `31af945ef640d276a3bafe5e9b858d80c46c8509`; both modified source files match the working submodule byte-for-byte. Existing visualization hunks are preserved.

## Commands

```bash
.venv/bin/python -m unittest discover -s tests -p test_mujoco_viewer_callbacks.py -v
/home/zdyukino/.local/bin/uvx --from ruff==0.12.7 ruff check tests/test_mujoco_viewer_callbacks.py
/home/zdyukino/.local/bin/uv lock --check
git diff --check -- requirements.txt tests/test_mujoco_viewer_callbacks.py third_party/patches/README.md
git -C third_party/mujoco_viewer diff --check
```

## Limits and review status

- No interactive desktop window was launched; desktop input and rendering integration have not been manually exercised.
- Default root `git diff --check` reports three required single-space context lines inside the newly added unified patch text. Actual Python source checks pass, and patch application/reproduction passes. No unrelated whitespace configuration was changed.
- Independent full-scope review: PASS. Ruff check and format check pass; both changed Python files compile. No type checker is configured. A contradictory local spec matrix row about cached dynamic dependencies was corrected; no unresolved code findings remain.
- Legacy compatibility was verified through an emulated six-argument boundary, not a separate older MuJoCo installation.
- Commit plan approved on 2026-10-20. Work committed as `dde491d` and `ec39201`; all six native regressions passed again immediately before commit. Unrelated `.gitattributes` remains untracked; no push was performed.
