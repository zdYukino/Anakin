"""Small MJCF metadata reader; independent of the external poselib package."""

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


@dataclass(frozen=True)
class SkeletonTree:
    """Body names in MJCF traversal order, as required by motion playback.

    This is deliberately only metadata. The motion runtime owns its own FK;
    this class does not implement the broader poselib skeleton API.
    """

    node_names: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.node_names)

    @classmethod
    def from_mjcf(cls, path: str | Path) -> "SkeletonTree":
        root = ElementTree.parse(path).getroot().find("worldbody/body")
        if root is None:
            raise ValueError(f"MJCF {path} has no root body under worldbody")
        bodies = tuple(body.get("name") for body in root.iter("body"))
        if not bodies or any(not name for name in bodies) or len(set(bodies)) != len(bodies):
            raise ValueError(f"MJCF {path} must give each body a unique name")
        return cls(node_names=bodies)
