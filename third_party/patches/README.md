# Patches for third party packages

## Viewer and Unitree fork commits

The parent repository now pins commits from the
[viewer fork](https://github.com/zdYukino/mujoco-python-viewer) and
[Unitree fork](https://github.com/zdYukino/unitree_cpp), published on their
`anakin-improvements` branches. Both commits include the former local patches.
Initialize the submodules with `git submodule update --init` and install them
directly; neither the uv setup nor `submodule_cfg.yaml` reapplies these patches.
Do not apply `mujoco_viewer.patch` or `unitree_cpp.patch` to the fork commits.

These two patch files remain as historical references against the original
upstream baselines:

| Patch | Original upstream base |
| --- | --- |
| `mujoco_viewer.patch` | [rohanpsingh/mujoco-python-viewer@31af945](https://github.com/rohanpsingh/mujoco-python-viewer/commit/31af945ef640d276a3bafe5e9b858d80c46c8509) |
| `unitree_cpp.patch` | [HansZ8/unitree_cpp@222028c](https://github.com/HansZ8/unitree_cpp/commit/222028cdaa79cdd7c7cda6645ebd2b02d201be0c) |

The viewer patch preserves RoboJuDo's visualization changes and adapts
camera dragging and scrolling to MuJoCo 3.11+ (which removed the scene argument
from `mjv_moveCamera`), retaining the earlier signature for older MuJoCo versions.
It also converts the selected skin ID to an integer for double-click selection.

The Unitree patch updates the deprecated `cmake.minimum-version` setting to
`cmake.version`, allowing the original binding to build with current
scikit-build-core releases.

When inspecting a historical baseline, preserve any custom submodule edits before
changing its checkout or applying a patch. Apply each complete patch only once
to its original upstream base; an already modified checkout may contain the same
changes.

## MuJoCo dependency maintenance

The root `requirements.txt` pins the validated engine to `mujoco==3.16.0` and
`uv.lock` records its resolved artifacts. After changing that pin, refresh uv's
cached root metadata and run the viewer callback regression tests:

```bash
uv lock --refresh-package robojudo
uv sync --locked --extra sim --inexact --reinstall-package robojudo
uv run --locked --extra sim --inexact python -m unittest discover -s tests -p 'test_mujoco_viewer_callbacks.py'
```

The explicit refresh is needed because the root dependencies are read dynamically
from `requirements.txt`; a plain `uv lock` can reuse old project metadata. Keep
any other extras normally used by the environment on subsequent sync commands.
