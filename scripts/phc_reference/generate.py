"""Regenerate deployment fixtures with the pinned, patched upstream PHC code.

This developer-only script never imports the internal motion implementation.
External sources remain in a separate temporary reference tree. See README.md.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.abc
import json
import shutil
import subprocess
import sys
import tempfile
import types
import xml.etree.ElementTree as ET
from pathlib import Path

PHC_COMMIT = "f8e75fb94918140e85db9744abf1f3b7667428a1"
PROJECT_BASELINE = "3d01ec21f7e3ea590dc97159458eec951431d4d3"
REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILES = (
    "LICENSE",
    "phc/utils/motion_lib_real.py",
    "phc/utils/motion_lib_base.py",
    "phc/utils/torch_humanoid_batch.py",
    "phc/utils/torch_utils.py",
    "phc/utils/pytorch3d_transforms.py",
    "phc/utils/rotation_conversions.py",
    "phc/utils/flags.py",
    "poselib/poselib/core/rotation3d.py",
)
SAMPLES = (
    (
        "g1_23",
        "unitree_g1_23dof_KungfuBot.yaml",
        "assets/motions/g1/phc/kungfubot/Horse-stance_pose.pkl",
    ),
    (
        "g1_29",
        "unitree_g1_29dof.yaml",
        "assets/motions/g1/phc_29/singles/0-KIT_6_WalkInCounterClockwiseCircle05_1_poses.pkl",
    ),
    (
        "h1",
        "unitree_h1.yaml",
        "assets/motions/h1/phc/singles/0-KIT_572_punch_right01_poses.pkl",
    ),
)
GLUE = [
    "Only the worker process adds the temporary reference tree to sys.path; project imports are blocked.",
    "Empty package initializers avoid unrelated package startup code.",
    "Unused SkeletonMotion/SkeletonState imports are raising shims; skeleton metadata is MJCF body preorder.",
    "Hydra's unused CLI main decorator is an identity decorator; DictConfig is an unused dict annotation.",
    "Unavailable lxml is replaced only for initial XML joint/motor enumeration by ElementTree with getchildren().",
    "The unused Manager queue in multi_thread=False is a raising sentinel; no multiprocessing service is started.",
    "The repository's complete phc.patch is applied unchanged; all subsequent numerical source stays unchanged.",
    "The upstream Tensor.numpy patches and torch thread mutation execute only inside the worker process.",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_record(source: Path, target: Path, identity: str, records: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    records[identity] = sha256(source)


def prepare_reference(args) -> None:
    """Copy only reference sources/resources, then apply the historical patch."""
    import yaml

    source_root = args.source_root.resolve()
    reference_root = args.reference_root.resolve()
    if reference_root.exists():
        raise FileExistsError(f"Use a fresh reference directory: {reference_root}")
    records = {}
    for name in SOURCE_FILES:
        source = source_root / name
        if name == "phc/utils/motion_lib_real.py" and args.motion_lib_real is not None:
            source = args.motion_lib_real
        copy_record(source, reference_root / name, name, records)

    resource_records = {}
    for _, config, _ in SAMPLES:
        relative = Path("phc/data/cfg/robot") / config
        root = args.addon_root if config.startswith("unitree_g1") else source_root
        copy_record(root / relative, reference_root / relative, str(relative), resource_records)
        data = yaml.safe_load((root / relative).read_text())
        xml = Path(data["asset"]["assetFileName"])
        copy_record(root / xml, reference_root / xml, str(xml), resource_records)

    subprocess.run(
        ["patch", "--batch", "--forward", "-p1", "--input", str(args.patch.resolve())],
        cwd=reference_root,
        check=True,
    )
    for name in (
        "phc",
        "phc/utils",
        "poselib",
        "poselib/poselib",
        "poselib/poselib/core",
        "poselib/poselib/skeleton",
    ):
        package = reference_root / name
        package.mkdir(parents=True, exist_ok=True)
        (package / "__init__.py").touch()

    metadata = {
        "phc_commit": PHC_COMMIT,
        "source_url_prefix": f"https://raw.githubusercontent.com/ZhengyiLuo/PHC/{PHC_COMMIT}/",
        "original_source_sha256": records,
        "effective_source_sha256": {name: sha256(reference_root / name) for name in SOURCE_FILES},
        "resource_sha256": resource_records,
        "project_baseline": PROJECT_BASELINE,
        "patch_path_at_baseline": "third_party/patches/phc.patch",
        "patch_sha256": sha256(args.patch),
        "addon_path_at_baseline": "third_party/patches/phc_addon_g1",
        "compatibility_glue": GLUE,
    }
    checked_in = REPO_ROOT / "tests/fixtures/phc/provenance.json"
    if checked_in.is_file():
        expected = json.loads(checked_in.read_text())
        for field in ("original_source_sha256", "effective_source_sha256", "resource_sha256", "patch_sha256"):
            if metadata[field] != expected[field]:
                raise ValueError(f"The supplied reference differs from the pinned baseline: {field}")
    (reference_root / "reference_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")


class BlockProjectImports(importlib.abc.MetaPathFinder):
    """The reference must not accidentally calculate using the code under test."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "robojudo" or fullname.startswith("robojudo."):
            raise ImportError(f"Project package is forbidden in the PHC reference: {fullname}")
        return None


def install_import_glue() -> None:
    """Supply only unreachable training imports and non-numerical setup APIs."""

    def add_module(name, **attrs):
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        sys.modules[name] = module
        return module

    class UnusedSkeleton:
        def __init__(self, *args, **kwargs):
            raise AssertionError("The reference must not use a training skeleton class")

    add_module(
        "poselib.poselib.skeleton.skeleton3d",
        SkeletonMotion=UnusedSkeleton,
        SkeletonState=UnusedSkeleton,
    )
    add_module("hydra", main=lambda **kwargs: lambda function: function)
    add_module("omegaconf", DictConfig=dict)

    class LegacyElement(ET.Element):
        def getchildren(self):
            return list(self)

    def xml_parser(**kwargs):
        return ET.XMLParser(target=ET.TreeBuilder(element_factory=LegacyElement))

    etree = add_module(
        "lxml.etree",
        XMLParser=xml_parser,
        parse=ET.parse,
        ElementTree=ET.ElementTree,
        Element=LegacyElement,
        SubElement=ET.SubElement,
    )
    add_module("lxml", etree=etree)

    import torch.multiprocessing as mp

    class UnusedQueue:
        def get(self, *args, **kwargs):
            raise AssertionError("The deterministic reference must not use the worker queue")

        put = get

    mp.Manager = lambda: types.SimpleNamespace(Queue=UnusedQueue)


def derive_clips(original):
    """Keep the original and derive a shorter, translated second clip."""
    import copy

    import numpy as np
    import torch

    cropped = copy.deepcopy(original)
    frame_count = len(original["pose_aa"])
    for key, value in cropped.items():
        if isinstance(value, np.ndarray | torch.Tensor) and value.ndim > 0 and len(value) == frame_count:
            cropped[key] = value[11:72].copy() if isinstance(value, np.ndarray) else value[11:72].clone()
    delta = [0.7, -0.2, 0.15]
    if torch.is_tensor(cropped["root_trans_offset"]):
        cropped["root_trans_offset"] += cropped["root_trans_offset"].new_tensor(delta)
    else:
        cropped["root_trans_offset"] += np.asarray(delta, dtype=cropped["root_trans_offset"].dtype)
    return {"original": original, "cropped_translated": cropped}


def generate(args) -> None:
    import joblib
    import numpy as np
    import scipy
    import torch
    import yaml
    from box import Box
    from scipy.spatial.transform import Rotation

    sys.meta_path.insert(0, BlockProjectImports())
    sys.path.insert(0, str(args.reference_root))
    install_import_glue()
    from phc.utils.motion_lib_base import FixHeightMode
    from phc.utils.motion_lib_real import MotionLibReal

    metadata = json.loads((args.reference_root / "reference_metadata.json").read_text())
    metadata.update(
        schema_version=1,
        generator_sha256=sha256(Path(__file__)),
        python=sys.version,
        versions={"numpy": np.__version__, "scipy": scipy.__version__, "torch": torch.__version__},
        tolerance={
            "pose": {"atol": 3e-5, "rtol": 3e-5},
            "velocity": {"atol": 2e-4, "rtol": 2e-4},
            "reason": (
                "Float32 FK/interpolation; velocity differentiation amplifies rounding. Quaternion signs are compared."
            ),
        },
        derived_clips={"crop": [11, 72], "translation": [0.7, -0.2, 0.15]},
        metadata_normalization="Singleton curr_motion_keys scalars are serialized as one-element lists.",
        samples=[],
    )
    args.output_root.mkdir(parents=True, exist_ok=True)
    headings = {
        "identity": [0.0, 0.0, 0.0, 1.0],
        "unaligned": None,
        "yaw_0_7": Rotation.from_euler("z", 0.7).as_quat().tolist(),
    }
    for name, config, motion_path in SAMPLES:
        source_path = REPO_ROOT / motion_path
        source = joblib.load(source_path)
        assert len(source) == 1
        clip_key, original = next(iter(source.items()))
        robot = yaml.safe_load((args.reference_root / "phc/data/cfg/robot" / config).read_text())
        robot["asset"]["assetFileName"] = str(args.reference_root / robot["asset"]["assetFileName"])
        robot["has_upright_start"] = False
        xml = ET.parse(robot["asset"]["assetFileName"])
        nodes = [node.attrib["name"] for node in xml.getroot().find("worldbody/body").iter("body")]
        skeleton = types.SimpleNamespace(node_names=nodes)
        library_cfg = Box(
            {
                "motion_file": str(source_path),
                "fix_height": FixHeightMode.no_fix,
                "min_length": -1,
                "max_length": -1,
                "im_eval": False,
                "multi_thread": False,
                "smpl_type": robot["humanoid_type"],
                "randomrize_heading": False,
                "device": "cpu",
                "robot": robot,
            }
        )
        library = MotionLibReal(library_cfg)
        arrays = {}
        sample = {
            "name": name,
            "config": f"robot/{config}",
            "motion_path": motion_path,
            "motion_sha256": sha256(source_path),
            "clip_key": clip_key,
            "input_shapes": {key: list(original[key].shape) for key in ("pose_aa", "root_trans_offset", "dof")},
            "fps": int(original["fps"]),
            "node_names": nodes,
            "extended_node_names": library.mesh_parsers.body_names_augment,
            "loads": [],
        }

        def load_and_record(
            library,
            label,
            heading,
            start_idx=0,
            count=1,
            mixed=False,
            skeleton=skeleton,
            sample=sample,
            arrays=arrays,
            fps=original["fps"],
        ):
            library.load_motions(
                skeleton_trees=[skeleton] * count,
                gender_betas=[torch.zeros(17)] * count,
                limb_weights=[np.zeros(10)] * count,
                random_sample=False,
                start_idx=start_idx,
                target_heading=heading,
            )
            load = {
                "label": label,
                "heading": heading,
                "start_idx": start_idx,
                "count": count,
                "derived": mixed,
                "clip_keys": np.atleast_1d(library.curr_motion_keys).tolist(),
                "lengths": library._motion_lengths.tolist(),
                "num_frames": library._motion_num_frames.tolist(),
                "cases": [],
            }

            def record_case(case_name, ids, times, offset=None):
                prefix = f"{label}__{case_name}__"
                ids = torch.as_tensor(ids, dtype=torch.long)
                times = torch.as_tensor(times, dtype=torch.float32)
                offset = None if offset is None else torch.as_tensor(offset, dtype=torch.float32)
                output = library.get_motion_state(ids, times, offset=offset)
                root = library.get_root_pos_smpl(ids, times)["root_pos"]
                arrays[prefix + "query_ids"] = ids.numpy().copy()
                arrays[prefix + "query_times"] = times.numpy().copy()
                if offset is not None:
                    arrays[prefix + "query_offset"] = offset.numpy().copy()
                arrays[prefix + "root_query"] = root.numpy().copy()
                for key, value in output.items():
                    arrays[prefix + key] = value.numpy().copy()
                assert all(np.isfinite(arrays[prefix + key]).all() for key in output)
                load["cases"].append(
                    {
                        "name": case_name,
                        "prefix": prefix,
                        "has_offset": offset is not None,
                        "fields": {key: list(value.shape) for key, value in output.items()},
                    }
                )

            length = library._motion_lengths[0].item()
            if count == 1:
                times = [-0.2, 0.0, 3 / fps, 3.5 / fps, length - 0.5 / fps, length, length + 0.2]
                record_case("boundaries", [0] * len(times), times)
                offsets = [[0.3 + i * 0.01, -0.4 - i * 0.02, 0.2] for i in range(len(times))]
                record_case("offsets", [0] * len(times), times, offsets)
                if not mixed:
                    future_times = 0.25 + torch.linspace(1, 95, 20).long().float() * 0.02
                    record_case("future", [0] * len(future_times), future_times)
            else:
                ids = [0, 1, 0, 1, 1, 0]
                times = [-0.1, 0.0, 3.5 / fps, 11.5 / fps, library._motion_lengths[1].item() + 0.2, length]
                offsets = [[0.3, -0.4, 0.2], [0.1, 0.2, -0.1]] * 3
                record_case("mixed_ids", ids, times, offsets)
            sample["loads"].append(load)

        for heading_name, heading in headings.items():
            load_and_record(library, heading_name, heading)

        with tempfile.TemporaryDirectory(prefix="phc-clips-") as motion_dir:
            derived_path = Path(motion_dir) / "two_clips.pkl"
            joblib.dump(derive_clips(original), derived_path)
            library_cfg.motion_file = str(derived_path)
            library = MotionLibReal(library_cfg)
            load_and_record(library, "two_clips", headings["yaw_0_7"], count=2, mixed=True)
            for index in (1, 0, 3):
                load_and_record(library, f"switch_{index}", headings["identity"], start_idx=index, mixed=True)

        output = args.output_root / f"{name}.npz"
        np.savez_compressed(output, **arrays)
        sample["fixture"] = output.name
        sample["fixture_sha256"] = sha256(output)
        sample["array_count"] = len(arrays)
        metadata["samples"].append(sample)

    (args.output_root / "provenance.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Saved independent PHC fixtures in {args.output_root}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--motion-lib-real", type=Path)
    parser.add_argument("--patch", type=Path, default=REPO_ROOT / "third_party/patches/phc.patch")
    parser.add_argument("--addon-root", type=Path, default=REPO_ROOT / "third_party/patches/phc_addon_g1")
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=REPO_ROOT / "tests/fixtures/phc")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.reference_root = args.reference_root.resolve()
    args.output_root = args.output_root.resolve()
    if args.worker:
        generate(args)
    else:
        if args.source_root is None:
            parser.error("--source-root is required for generation")
        prepare_reference(args)
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                "--reference-root",
                str(args.reference_root),
                "--output-root",
                str(args.output_root),
            ],
            cwd=args.reference_root,
            check=True,
        )


if __name__ == "__main__":
    main()
