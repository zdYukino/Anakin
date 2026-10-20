# Patches for third party packages

`mujoco_viewer.patch` preserves RoboJuDo's visualization changes and adapts
camera dragging and scrolling to MuJoCo 3.11+ (which removed the scene argument
from `mjv_moveCamera`), retaining the earlier signature for older MuJoCo versions.
It also converts the selected skin ID to an integer for double-click selection.
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

On a fresh checkout, apply the complete patch once after initializing the pinned
viewer submodule:

```bash
git -C third_party/mujoco_viewer apply ../patches/mujoco_viewer.patch
```

For a checkout where an earlier visualization-only patch was already applied,
first inspect `git -C third_party/mujoco_viewer diff` and preserve any custom
changes. Reverse the exact earlier patch, then apply the updated patch; do not
reset the submodule or apply the complete updated patch twice.

`unitree_cpp.patch` updates the deprecated `cmake.minimum-version` setting to
`cmake.version`, allowing the pinned binding to build with current
scikit-build-core releases. Apply it once after initializing the submodule;
`submodule_cfg.yaml` also registers it for the legacy installer.
