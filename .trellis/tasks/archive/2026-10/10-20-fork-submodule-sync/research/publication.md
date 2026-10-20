# Published Fork Improvements

User approved the final plan with `实现`. Published without force on 2026-10-20:

| Repository | Branch | Published commit | Parent baseline |
| --- | --- | --- | --- |
| git@github.com:zdYukino/mujoco-python-viewer.git | anakin-improvements | a16a7997b4e9c340e4e25a504208fef9997a9fe2 | 31af945ef640d276a3bafe5e9b858d80c46c8509 |
| git@github.com:zdYukino/unitree_cpp.git | anakin-improvements | 6f995d601be08e72528117f5cc13bd666e7d145e | 222028cdaa79cdd7c7cda6645ebd2b02d201be0c |

Both pushes succeeded and set tracking to origin/anakin-improvements. Original
origins were renamed upstream; provided SSH forks are the new origins. Parent
local URL configuration was synchronized via `git submodule sync` after the
implementation agent updated `.gitmodules`.

Before commits, source SHA256s and complete binary diffs matched the migration
snapshot exactly. No source implementation was changed during migration.
Six real-binding viewer tests passed; native Unitree import, TOML build option,
MuJoCo 3.16.0 runtime and installed root dependency constraint checks passed.

Parent gitlinks and config/docs were committed as `6a77265` after the separate
Phase 3.4 confirmation. The parent repository was not pushed in this task.

Snapshot for byte checks (saved in `/tmp/anakin-fork-before.json`):

- callbacks.py: 9f0b946c08e4893bcb957771291f9f0e1b6a6ba46c16cb9be456aa7f2a7f4af7
- mujoco_viewer.py: 256dd0f5f60d2783c9445390ca4ce2ef138b8ee53c4eeee3e383c103fba9667f
- Unitree pyproject.toml: 2945d9dc12f27670915e7ccb4035958a145af17377cd27993f59f84cfe8e1da4
