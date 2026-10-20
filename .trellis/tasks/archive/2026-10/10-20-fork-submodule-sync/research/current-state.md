# Current State (2026-10-20)

## Repositories and authentication

SSH `git ls-remote --symref <fork> HEAD` succeeded for both user-specified forks.

| Submodule | Current pinned commit | Original origin | Fork | Fork default |
| --- | --- | --- | --- | --- |
| third_party/mujoco_viewer | 31af945ef640d276a3bafe5e9b858d80c46c8509 | https://github.com/rohanpsingh/mujoco-python-viewer | git@github.com:zdYukino/mujoco-python-viewer.git | main at 31af945ef640d276a3bafe5e9b858d80c46c8509 |
| packages/unitree_cpp | 222028cdaa79cdd7c7cda6645ebd2b02d201be0c | https://github.com/HansZ8/unitree_cpp | git@github.com:zdYukino/unitree_cpp.git | master at ecb5aa3b336987234fb4bda7521991daeca4f027 |

Both working submodules have detached HEADs. Preserve the current source baselines;
Unitree's fork default includes two additional upstream commits affecting 22 files
(torso IMU and dummy SDK support), which are outside this migration's scope.

## Existing improvements

- Viewer: modified `mujoco_viewer/callbacks.py` and `mujoco_viewer/mujoco_viewer.py`,
  75 insertions / 23 deletions; visualization additions plus MuJoCo 3.11+ camera
  signature compatibility and scalar skin selection. Existing six native-binding
  regressions live in the parent repository.
- Unitree: `pyproject.toml` replaces `cmake.minimum-version = "3.15"` with
  `cmake.version = ">=3.15"` for current scikit-build-core.
- Both submodule source whitespace checks pass. Parent `release` is at ec39201;
  the only unrelated dirty path is untracked `.gitattributes`.

## Integration contract

`submodule_install.py:35` reads optional patches; lines 49-53 apply them after
initializing the pinned commit. Therefore remove the viewer/Unitree active patch
entries once their source fixes live in published fork commits. The original
patch files can remain as historical references with documentation clarifying
that fork-based checkouts must not reapply them.

`README.md:183-189` currently instructs applying both patches manually and needs
to use fork commits directly. `.gitmodules` holds persistent clone URLs; local
submodule Git config must be synchronized too.

MuJoCo is pinned to 3.16.0 through dynamic `requirements.txt`; uv is configured
to use local submodule paths. Source baselines and package versions need not change.

## Network and permissions

Sandbox SSH attempts failed DNS; escalated read-only SSH calls succeeded. Use
escalation for required GitHub access and writes to protected Git metadata.
The user explicitly requested syncing improvements to these forks, authorizing
pushes there after planning approval. Do not force push or publish to upstream.
