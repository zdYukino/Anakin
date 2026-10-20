# Migrate Viewer and Unitree Submodules to User Forks

## Goal

Make the user's forks the source for both submodules and publish the current
local improvements, so fresh clones reproduce the same behavior without local
patch application.

## Background

- User destinations: `git@github.com:zdYukino/mujoco-python-viewer.git` and
  `git@github.com:zdYukino/unitree_cpp.git`. SSH reads succeed for both.
- Viewer is pinned at `31af945ef640d276a3bafe5e9b858d80c46c8509` with visualization
  and mouse compatibility changes in two files.
- Unitree is pinned at `222028cdaa79cdd7c7cda6645ebd2b02d201be0c` with a build
  metadata fix. Its fork default is two newer upstream commits ahead; upgrading
  that baseline is a separate behavior change.
- `.gitmodules` points to upstream repositories. `submodule_cfg.yaml` and the
  root README still apply patches whose changes will move into fork commits.
- The only unrelated root change is untracked `.gitattributes`.

## Requirements

1. Persist the exact provided SSH clone URLs in the main project's submodule
   configuration and make each local submodule origin match. Preserve original
   upstream access under an `upstream` remote.
2. Publish existing source improvements on an `anakin-improvements` branch in
   each fork, based on each currently validated pinned commit. Keep source and
   package baselines unchanged beyond the existing improvements.
3. Update parent gitlinks to the published commits. Fresh initialization must
   obtain those commits directly from the user's forks.
4. Stop automatically and manually reapplying the now-integrated viewer and
   Unitree patches. Retain historical patch files with accurate documentation.
5. Preserve MuJoCo 3.16.0 and uv reproducibility; retain unrelated local changes.
6. Push only to the two specified forks, without force-pushing or changing
   upstream repositories. Main-project changes are prepared and verified locally;
   parent commit confirmation follows the repository workflow.

## Acceptance Criteria

- `.gitmodules` URLs and submodule origins equal the user-provided URLs; original
  origins remain available as upstream remotes.
- Both fork branch refs resolve to commits containing all current improvements;
  these commits are the parent gitlink targets and each submodule worktree is clean.
- A clean temporary checkout of each published commit contains the fixed files
  without applying a patch. Parent installation instructions/config do not apply
  those patches again.
- Six viewer native-binding regressions pass; Unitree's committed build metadata
  matches the already built/validated local fix. uv lock/metadata remain consistent.
- No unrelated edits, baseline upgrades or forced remote updates occur.

## Out of Scope

- Incorporating newer upstream Unitree features or changing robot control behavior.
- Force pushes, upstream publication, or pushing the parent repository.
- Changing MuJoCo versions, removing historical patch files, or staging `.gitattributes`.

## Planning Status

Task creation and final plan approved. User authorized implementation with `实现`,
including publication to both `anakin-improvements` branches while preserving
validated baselines.
