# Parent Commit Plan — Completed

The user approved publishing submodule improvements with the implementation
plan. Those pushes are already complete:

- Viewer: `a16a7997b4e9c340e4e25a504208fef9997a9fe2` on the fork's
  `anakin-improvements` branch.
- Unitree: `6f995d601be08e72528117f5cc13bd666e7d145e` on the fork's
  `anakin-improvements` branch.

## Parent commit

`6a77265 build: use forked submodules with integrated fixes`

The user approved with `更新并提交主工程 子模块拉取来源`. The six paths below
were verified and committed on `release`. Staged URLs, published gitlink targets
and clean submodules were checked before commit. No parent push was performed.

- `.gitmodules`: persistent SSH URLs for both forks.
- `third_party/mujoco_viewer`: gitlink to the published viewer improvement commit.
- `packages/unitree_cpp`: gitlink to the published build-fix commit.
- `submodule_cfg.yaml`: remove duplicate active patch application for both modules.
- `README.md`: initialize the current project's pinned forks directly.
- `third_party/patches/README.md`: document historical patch bases and current setup.

## Excluded dirty path

- `.gitattributes`: pre-existing unrelated Trellis journal configuration; leave untracked.
- `.archify/`: appeared during this task from other work; leave untracked and untouched.

## Scope

One local parent commit on the current `release` branch; no parent push, no
upstream pushes, no forced updates and no changes to other submodules. Local
`.trellis/` task/spec/journal files remain ignored and will not be force-added.
