# Patches for third party packages

`unitree_cpp.patch` updates the deprecated `cmake.minimum-version` setting to
`cmake.version`, allowing the pinned binding to build with current
scikit-build-core releases. Apply it once after initializing the submodule;
`submodule_cfg.yaml` also registers it for the legacy installer.
