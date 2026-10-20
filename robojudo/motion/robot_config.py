"""Resolve the robot resources used by PHC-format motion playback."""

from pathlib import Path

import yaml

RESOURCE_DIR = Path(__file__).resolve().parent / "resources"


def load_robot_config(robot_config_file: str | Path) -> dict:
    """Read a bundled ``robot/*.yaml`` config or an explicit local YAML path.

    Bundled asset paths are relative to ``resources/``. For a custom config,
    relative assets are resolved against its optional assetRoot and the YAML
    directory. Every returned model path is absolute, so playback and the
    kinematics diagnostic work independently of the process working directory.
    """
    requested = Path(robot_config_file).expanduser()
    if requested.is_absolute() or requested.is_file():
        path = requested.resolve()
        base = path.parent
    else:
        path = RESOURCE_DIR / "config" / requested
        base = RESOURCE_DIR
    if not path.is_file():
        raise FileNotFoundError(
            f"Motion robot config {robot_config_file!s} was not found at {path}. "
            "Use a bundled robot/unitree_g1_29dof.yaml, "
            "robot/unitree_g1_23dof_KungfuBot.yaml, robot/unitree_h1.yaml, "
            "or an existing local YAML file."
        )
    with path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict) or not isinstance(config.get("asset"), dict):
        raise ValueError(f"Motion robot config {path} must contain an asset mapping")
    asset = config["asset"]
    if not asset.get("assetFileName"):
        raise ValueError(f"Motion robot config {path} must define asset.assetFileName")
    root = Path(asset.get("assetRoot", "."))
    root = root if root.is_absolute() else base / root
    model = Path(asset["assetFileName"])
    model = model if model.is_absolute() else root / model
    if not model.is_file():
        raise FileNotFoundError(f"Motion robot model {model} referenced by {path} does not exist")
    asset["assetRoot"] = root.resolve().as_posix()
    asset["assetFileName"] = model.resolve().as_posix()
    # Some retained configs use the MJCF as their fitting tool's URDF input.
    if asset.get("urdfFileName"):
        urdf = Path(asset["urdfFileName"])
        asset["urdfFileName"] = (urdf if urdf.is_absolute() else root / urdf).resolve().as_posix()
    for key in ("body_names", "extend_config", "humanoid_type"):
        if key not in config:
            raise ValueError(f"Motion robot config {path} must define {key}")
    return config
