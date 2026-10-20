# Evidence and boundaries

- CodeGraph confirms both camera calls pass the removed scene argument; perturbation is a separate API that still takes scene.
- Runtime MuJoCo is 3.16.0; `mjv_moveCamera.__doc__` accepts `(model, action, reldx, reldy, camera)`.
- Official latest release: https://github.com/google-deepmind/mujoco/releases/tag/3.16.0.
- Removal boundary is 3.11.0: https://mujoco.readthedocs.io/en/stable/changelog.html#version-3-11-0-july-27-2026.
- Installed `mjv_select` and `mjv_initPerturb` signatures match existing calls.
- Real-binding regression additionally confirms double-click selection fails at `self.pert.skinselect = selskin`: the current integer setter rejects the `(1, 1)` ndarray. Convert the single output using `selskin.item()`.
- Root `requirements.txt` is the existing dynamic dependency source. Pin there, then regenerate the lock with uv.
- Implementation verified plain `uv lock` reused old dynamic root metadata. Use `uv lock --refresh-package robojudo` and `uv sync --extra sim --extra unitree --inexact --reinstall-package robojudo`; inspect both lock `requires-dist` and installed root metadata to confirm the exact constraint.
- Existing viewer changes are in `mujoco_viewer/mujoco_viewer.py`; preserve them. Dirty submodules are ignored, so the tracked patch must contain the fix.
- Pre-existing root changes: `.gitignore`, `README.md`, `pyproject.toml`, `submodule_cfg.yaml`, `third_party/patches/README.md`, `.gitattributes`, `third_party/patches/unitree_cpp.patch`, `uv.lock`. Preserve them and do not commit wholesale.
