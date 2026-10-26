"""Compare the internal runtime with independently generated upstream PHC data."""

from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.abc
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np
import torch
from box import Box

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures/phc"
EXTERNAL_MODULES = {"phc", "poselib", "smpl_sim", "isaacgym", "open3d", "stl", "lxml", "hydra", "omegaconf"}


class BlockExternalMotionImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in EXTERNAL_MODULES:
            raise AssertionError(f"The internal motion runtime imported an excluded dependency: {fullname}")
        return None


@contextmanager
def isolated_runtime():
    """Fail immediately if runtime code imports PHC or creates a manager."""
    blocker = BlockExternalMotionImports()
    sys.meta_path.insert(0, blocker)
    try:
        with patch("torch.multiprocessing.Manager", side_effect=AssertionError("Motion loading started a manager")):
            yield
    finally:
        sys.meta_path.remove(blocker)


def derived_motion(original: dict, recipe: dict) -> dict:
    """Recreate the recorded two-clip input from the checked-in sample."""
    second = copy.deepcopy(original)
    frame_count = len(original["pose_aa"])
    start, stop = recipe["crop"]
    for key, value in second.items():
        if isinstance(value, np.ndarray | torch.Tensor) and value.ndim and len(value) == frame_count:
            second[key] = value[start:stop].clone() if torch.is_tensor(value) else value[start:stop].copy()
    translation = second["root_trans_offset"]
    if torch.is_tensor(translation):
        translation += translation.new_tensor(recipe["translation"])
    else:
        translation += np.asarray(recipe["translation"], dtype=translation.dtype)
    return {"original": original, "cropped_translated": second}


class TestPhcReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provenance = json.loads((FIXTURES / "provenance.json").read_text())
        cls.numpy_method = torch.Tensor.numpy
        cls.thread_count = torch.get_num_threads()
        with isolated_runtime():
            cls.runtime = importlib.import_module("robojudo.motion")

    def make_library(self, sample, motion_path):
        robot = self.runtime.load_robot_config(sample["config"])
        robot["has_upright_start"] = False
        skeleton = self.runtime.SkeletonTree.from_mjcf(robot["asset"]["assetFileName"])
        self.assertEqual(list(skeleton.node_names), sample["node_names"])
        library = self.runtime.MotionLibReal(
            Box(
                {
                    "motion_file": str(motion_path),
                    "fix_height": self.runtime.FixHeightMode.no_fix,
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
        )
        self.assertEqual(library.mesh_parsers.body_names_augment, sample["extended_node_names"])
        return library, skeleton

    def assert_array(self, actual, expected, name, velocity=False):
        self.assertIsInstance(actual, torch.Tensor, name)
        self.assertEqual(actual.dtype, torch.float32, name)
        self.assertEqual(tuple(actual.shape), expected.shape, name)
        self.assertTrue(torch.isfinite(actual).all().item(), name)
        tolerance = self.provenance["tolerance"]["velocity" if velocity else "pose"]
        np.testing.assert_allclose(actual.detach().cpu().numpy(), expected, err_msg=name, **tolerance)

    def compare_load(self, sample, load, fixture, library, skeleton):
        count = load["count"]
        library.load_motions(
            skeleton_trees=[skeleton] * count,
            gender_betas=[torch.zeros(17)] * count,
            limb_weights=[np.zeros(10)] * count,
            random_sample=False,
            start_idx=load["start_idx"],
            target_heading=None if load["heading"] is None else np.asarray(load["heading"]),
        )
        self.assertEqual(list(library.curr_motion_keys), load["clip_keys"])
        self.assertEqual(library._motion_num_frames.tolist(), load["num_frames"])
        np.testing.assert_allclose(library._motion_lengths.cpu().numpy(), load["lengths"], atol=1e-7)
        for case in load["cases"]:
            with self.subTest(robot=sample["name"], load=load["label"], case=case["name"]):
                prefix = case["prefix"]
                ids = torch.from_numpy(fixture[prefix + "query_ids"])
                times = torch.from_numpy(fixture[prefix + "query_times"])
                offset = torch.from_numpy(fixture[prefix + "query_offset"]) if case["has_offset"] else None
                actual = library.get_motion_state(ids, times, offset=offset)
                self.assertEqual(set(actual), set(case["fields"]))
                for field, shape in case["fields"].items():
                    expected = fixture[prefix + field]
                    self.assertEqual(list(expected.shape), shape)
                    self.assert_array(
                        actual[field],
                        expected,
                        f"{prefix}{field}",
                        velocity="vel" in field,
                    )
                root = library.get_root_pos_smpl(ids, times)["root_pos"]
                self.assert_array(root, fixture[prefix + "root_query"], prefix + "root_query")

    def test_samples_and_fixtures_match_recorded_hashes(self):
        self.assertEqual(self.provenance["phc_commit"], "f8e75fb94918140e85db9744abf1f3b7667428a1")
        self.assertEqual({sample["name"] for sample in self.provenance["samples"]}, {"g1_23", "g1_29", "h1"})
        for sample in self.provenance["samples"]:
            with self.subTest(robot=sample["name"]):
                motion_path = ROOT / sample["motion_path"]
                self.assertEqual(hashlib.sha256(motion_path.read_bytes()).hexdigest(), sample["motion_sha256"])
                fixture_path = FIXTURES / sample["fixture"]
                self.assertEqual(hashlib.sha256(fixture_path.read_bytes()).hexdigest(), sample["fixture_sha256"])
                source = joblib.load(motion_path)
                self.assertEqual(list(source), [sample["clip_key"]])
                for key, shape in sample["input_shapes"].items():
                    self.assertEqual(list(source[sample["clip_key"]][key].shape), shape)
                with np.load(fixture_path, allow_pickle=False) as fixture:
                    self.assertEqual(len(fixture.files), sample["array_count"])

    def test_all_upstream_states_and_clip_switches(self):
        for sample in self.provenance["samples"]:
            motion_path = ROOT / sample["motion_path"]
            original = joblib.load(motion_path)[sample["clip_key"]]
            with (
                tempfile.TemporaryDirectory(prefix="phc-test-clips-") as motion_dir,
                np.load(FIXTURES / sample["fixture"], allow_pickle=False) as fixture,
                isolated_runtime(),
            ):
                derived_path = Path(motion_dir) / "two_clips.pkl"
                joblib.dump(derived_motion(original, self.provenance["derived_clips"]), derived_path)
                libraries = {
                    False: self.make_library(sample, motion_path),
                    True: self.make_library(sample, derived_path),
                }
                for load in sample["loads"]:
                    library, skeleton = libraries[load["derived"]]
                    self.compare_load(sample, load, fixture, library, skeleton)
        self.assertIs(torch.Tensor.numpy, type(self).numpy_method)
        self.assertEqual(torch.get_num_threads(), self.thread_count)

    def test_reference_is_not_an_execution_dependency(self):
        self.assertFalse(EXTERNAL_MODULES.intersection(sys.modules))
        self.assertFalse(any("anakin-phc-reference" in str(entry) for entry in sys.path))
        self.assertIs(torch.Tensor.numpy, type(self).numpy_method)
        self.assertEqual(torch.get_num_threads(), self.thread_count)
        self.assertEqual(self.provenance["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
