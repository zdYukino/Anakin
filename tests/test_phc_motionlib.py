"""Analytical/runtime tests independent of the pinned PHC reference fixtures."""

import importlib.util
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import chdir
from pathlib import Path

import joblib
import numpy as np
import torch
from scipy.ndimage import gaussian_filter1d

from robojudo.motion import FixHeightMode, MotionLibReal, SkeletonTree, load_robot_config
from robojudo.motion._quaternion import slerp
from robojudo.motion.kinematics import HumanoidBatch

ROOT = Path(__file__).resolve().parents[1]
ROBOT_CONFIGS = (
    "robot/unitree_g1_29dof.yaml",
    "robot/unitree_g1_23dof_KungfuBot.yaml",
    "robot/unitree_h1.yaml",
)


class MotionPlaybackTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.xml = self.path / "robot.xml"
        self.xml.write_text(
            '<mujoco><worldbody><body name="root">'
            '<joint name="floating" type="free"/>'
            '<body name="hinge" pos="1 0 0" quat="0.7071067811865476 0 0 0.7071067811865476">'
            '<joint name="hinge" axis="0 0 1" range="-3 3"/>'
            '</body></body></worldbody><actuator><motor name="hinge" joint="hinge"/></actuator></mujoco>'
        )
        self.robot = {
            "humanoid_type": "analytical",
            "body_names": ["root", "hinge"],
            "asset": {"assetFileName": str(self.xml)},
            "extend_config": [{"joint_name": "tip", "parent_name": "hinge", "pos": [1, 0, 0], "rot": [1, 0, 0, 0]}],
        }
        self.tree = SkeletonTree.from_mjcf(self.xml)
        self.clip = {
            "pose_aa": np.zeros((5, 4, 3), dtype=np.float32),
            "root_trans_offset": np.column_stack([np.arange(5) / 10, np.zeros((5, 2))]),
            "fps": 10,
        }
        # The fourth fitted node must be truncated before FK.
        self.clip["pose_aa"][:, 3] = [1.2, -0.8, 0.3]

    def make_library(self, clips=None, **overrides):
        motion_file = self.path / "motions.pkl"
        joblib.dump({"first": self.clip} if clips is None else clips, motion_file)
        config = {
            "motion_file": str(motion_file),
            "robot": self.robot,
            "fix_height": FixHeightMode.no_fix,
            "device": "cpu",
            **overrides,
        }
        return MotionLibReal(config)

    def load(self, library, count=1, start_idx=0, **kwargs):
        return library.load_motions(
            [self.tree] * count,
            [torch.zeros(17)] * count,
            [np.zeros(10)] * count,
            random_sample=False,
            start_idx=start_idx,
            **kwargs,
        )

    def test_fk_extensions_interpolation_offsets_and_clipped_endpoints(self):
        library = self.make_library()
        self.load(library)
        times = torch.tensor([-1, 0, 0.15, 0.4, 1])
        state = library.get_motion_state([0] * 5, times, offset=[0.3, -0.4, 0.2])
        root_x = np.array([0, 0, 0.15, 0.4, 0.4]) + 0.3
        expected_root = np.column_stack([root_x, np.full(5, -0.4), np.full(5, 0.2)])
        np.testing.assert_allclose(state["root_pos"], expected_root, atol=1e-6)
        np.testing.assert_allclose(state["rg_pos_t"][:, 1], expected_root + [1, 0, 0], atol=1e-6)
        np.testing.assert_allclose(state["rg_pos_t"][:, 2], expected_root + [1, 1, 0], atol=1e-6)
        np.testing.assert_allclose(state["root_vel"], np.tile([1, 0, 0], (5, 1)), atol=1e-6)
        np.testing.assert_allclose(state["dof_pos"], np.zeros((5, 1)), atol=1e-7)
        self.assertEqual(state["rg_pos"].shape, (5, 2, 3))
        self.assertEqual(state["motion_aa"].shape, (5, 6))
        self.assertEqual(state["motion_bodies"].shape, (5, 17))
        self.assertEqual(state["motion_limb_weights"].shape, (5, 10))
        self.assertTrue(all(value.dtype == torch.float32 for value in state.values()))
        self.assertTrue(all(torch.isfinite(value).all() for value in state.values()))
        reset = library.get_root_pos_smpl([0], torch.tensor([0]))["root_pos"]
        np.testing.assert_allclose(reset, [[0, 0, 0]])

    def test_per_query_offsets_only_change_positions(self):
        library = self.make_library()
        self.load(library)
        ids, times = [0, 0], [0.05, 0.25]
        base = library.get_motion_state(ids, times)
        offsets = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)
        shifted = library.get_motion_state(ids, times, offsets)
        for field, value in base.items():
            if field == "root_pos":
                expected = value.numpy() + offsets
            elif field in ("rg_pos", "rg_pos_t"):
                expected = value.numpy() + offsets[:, None]
            else:
                expected = value.numpy()
            np.testing.assert_array_equal(shifted[field].numpy(), expected, err_msg=field)
        broadcast = library.get_motion_state(ids, times, offsets[:1])
        scalar_offset = library.get_motion_state(ids, times, offsets[0])
        for field in base:
            np.testing.assert_array_equal(broadcast[field], scalar_offset[field], err_msg=field)

    def test_two_clip_selection_and_wrapping(self):
        second = {
            **self.clip,
            "pose_aa": self.clip["pose_aa"][:3],
            "root_trans_offset": self.clip["root_trans_offset"][:3] + [2, 3, 4],
        }
        library = self.make_library({"first": self.clip, "second": second})
        self.load(library, count=2, start_idx=1)
        self.assertEqual(library.curr_motion_keys.tolist(), ["second", "first"])
        self.assertEqual(library.num_motions(), 2)
        np.testing.assert_allclose(library._motion_lengths, [0.2, 0.4], atol=1e-7)
        state = library.get_motion_state([0, 1, 0], [0, 0.1, 1])
        np.testing.assert_allclose(state["root_pos"], [[2, 3, 4], [0.1, 0, 0], [2.2, 3, 4]], atol=1e-6)
        self.load(library, start_idx=2)
        self.assertEqual(library.curr_motion_keys.tolist(), ["first"])

    def test_directory_loading_uses_legacy_filename_keys(self):
        for filename in ("first.pkl", "first.v1.pkl"):
            with self.subTest(filename=filename):
                directory = self.path / filename
                directory.mkdir()
                motion_file = directory / filename
                joblib.dump({"first": self.clip}, motion_file)
                library = self.make_library(motion_file=str(directory))
                self.load(library)
                self.assertEqual(library.curr_motion_keys.tolist(), [str(motion_file)])
                state = library.get_motion_state([0], [0.15])
                np.testing.assert_allclose(state["root_pos"], [[0.15, 0, 0]], atol=1e-6)

                joblib.dump({"other": self.clip}, motion_file)
                with self.assertRaisesRegex(ValueError, "filename key 'first'"):
                    self.load(library)

    def test_dof_terminal_difference_keeps_existing_semantics(self):
        self.clip["pose_aa"][:, 1, 2] = [0, 0.1, 0.4, 0.9, 1.6]
        library = self.make_library()
        self.load(library)
        np.testing.assert_allclose(library.dvs[:, 0], [1, 3, 5, 7, 5], atol=1e-6)

    def test_smoothed_angular_velocity_has_terminal_zero_difference(self):
        angles = np.arange(5) / 10
        rotations = np.column_stack([np.zeros((5, 2)), np.sin(angles / 2), np.cos(angles / 2)])
        rotations[2] *= -1  # Equivalent quaternion signs must not change velocity.
        angular = HumanoidBatch._compute_angular_velocity(torch.tensor(rotations)[None, :, None], 0.1)
        expected = gaussian_filter1d(np.array([1.0, 1, 1, 1, 0]), 2, mode="nearest")
        np.testing.assert_allclose(angular[0, :, 0, 2], expected, atol=1e-12)
        np.testing.assert_allclose(angular[0, :, 0, :2], 0, atol=1e-12)

    def test_quaternion_interpolation_keeps_shortest_path_and_close_pair_rule(self):
        initial = torch.tensor([[0.0, 0, 0, 1]])
        final = torch.tensor([[0.0, 0, -1, 0]])
        actual = slerp(initial, final, torch.tensor([[0.25]]))
        # A half-turn's sign is ambiguous; the chosen endpoint is negative z.
        np.testing.assert_allclose(actual, [[0, 0, -np.sin(np.pi / 8), np.cos(np.pi / 8)]], atol=1e-6)
        close = torch.tensor([[0, 0, np.sin(0.00025), np.cos(0.00025)]], dtype=torch.float32)
        np.testing.assert_allclose(slerp(initial, close, torch.tensor([[0.1]])), (initial + close) / 2, atol=0)

    def test_invalid_motion_data_and_queries_have_context(self):
        with self.assertRaisesRegex(ValueError, "first.*missing.*pose_aa"):
            library = self.make_library({"first": {"root_trans_offset": np.zeros((5, 3)), "fps": 30}})
            self.load(library)
        for fps in (0, float("nan")):
            with self.subTest(fps=fps), self.assertRaisesRegex(ValueError, "first.*positive fps"):
                library = self.make_library({"first": {**self.clip, "fps": fps}})
                self.load(library)
        with self.assertRaisesRegex(ValueError, "at least 3"):
            library = self.make_library({"first": {**self.clip, "pose_aa": np.zeros((5, 2, 3), dtype=np.float32)}})
            self.load(library)
        with self.assertRaisesRegex(ValueError, "at least three"):
            library = self.make_library(
                {"first": {**self.clip, "pose_aa": self.clip["pose_aa"][:2], "root_trans_offset": np.zeros((2, 3))}}
            )
            self.load(library)
        library = self.make_library()
        with self.assertRaisesRegex(RuntimeError, "load_motions"):
            library.get_motion_state([0], [0])
        self.load(library)
        for ids, times, error in (([1], [0], IndexError), ([0, 0], [0], ValueError), ([0], [float("nan")], ValueError)):
            with self.subTest(ids=ids, times=times), self.assertRaises(error):
                library.get_motion_state(ids, times)
        with self.assertRaisesRegex(ValueError, "offset"):
            library.get_motion_state([0], [0], [1, 2])

    def test_training_only_features_are_explicitly_unsupported(self):
        with self.assertRaisesRegex(NotImplementedError, "no_fix"):
            self.make_library(fix_height=FixHeightMode.full_fix)
        library = self.make_library()
        with self.assertRaisesRegex(NotImplementedError, "random_sample=False"):
            library.load_motions([self.tree], [np.zeros(17)], [np.zeros(10)])
        with self.assertRaisesRegex(NotImplementedError, "complete clips"):
            self.load(library, max_len=3)

    def test_invalid_motion_types_identify_the_clip(self):
        invalid_values = (
            ("pose_aa", None, "numeric pose_aa and root_trans_offset"),
            ("pose_aa", "invalid", "numeric pose_aa and root_trans_offset"),
            ("root_trans_offset", {}, "numeric pose_aa and root_trans_offset"),
            ("fps", None, "finite positive fps"),
            ("fps", [], "finite positive fps"),
            ("fps", "invalid", "finite positive fps"),
        )
        for field, value, message in invalid_values:
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, f"first.*{message}"):
                library = self.make_library({"first": {**self.clip, field: value}})
                self.load(library)

    def test_heading_alignment_validates_frame_and_body_counts_first(self):
        for frames, bodies, message in ((0, 4, "at least three motion frames"), (5, 0, "at least 3 bodies")):
            for heading in (None, [0.0, 0.0, 0.0, 1.0]):
                with (
                    self.subTest(frames=frames, bodies=bodies, heading=heading),
                    self.assertRaisesRegex(ValueError, f"first.*{message}"),
                ):
                    library = self.make_library(
                        {
                            "first": {
                                "pose_aa": np.zeros((frames, bodies, 3), dtype=np.float32),
                                "root_trans_offset": np.zeros((frames, 3), dtype=np.float32),
                                "fps": 30,
                            }
                        }
                    )
                    self.load(library, target_heading=heading)


class RobotResourceTest(unittest.TestCase):
    def test_bundled_configs_resolve_without_working_directory_dependency(self):
        expected = ((30, 33), (24, 27), (20, 23))
        with tempfile.TemporaryDirectory() as directory, chdir(directory):
            for name, (bodies, extended) in zip(ROBOT_CONFIGS, expected, strict=True):
                with self.subTest(name=name):
                    config = load_robot_config(name)
                    self.assertTrue(Path(config["asset"]["assetFileName"]).is_file())
                    kinematics = HumanoidBatch(config)
                    self.assertEqual(len(SkeletonTree.from_mjcf(config["asset"]["assetFileName"])), bodies)
                    self.assertEqual(kinematics.num_bodies_augment, extended)

    @unittest.skipUnless(importlib.util.find_spec("mujoco"), "MuJoCo is optional")
    def test_mesh_free_models_load_in_mujoco(self):
        import mujoco

        for name in ROBOT_CONFIGS:
            with self.subTest(name=name):
                config = load_robot_config(name)
                model = mujoco.MjModel.from_xml_path(config["asset"]["assetFileName"])
                self.assertGreater(model.njnt, 1)
                self.assertEqual(model.nmesh, 0)

    def test_missing_configs_and_models_fail_at_resolution(self):
        with self.assertRaisesRegex(FileNotFoundError, "Motion robot config"):
            load_robot_config("robot/not-a-robot.yaml")
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "robot.yaml"
            config.write_text("asset:\n  assetFileName: missing.xml\n")
            with self.assertRaisesRegex(FileNotFoundError, "missing.xml"):
                load_robot_config(config)

    def test_no_external_imports_or_global_torch_and_worker_side_effects(self):
        script = textwrap.dedent(
            """
            import importlib.abc
            import logging
            import multiprocessing
            import sys
            import torch
            from unittest.mock import patch

            class BlockExternal(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, *args):
                    if fullname.split('.')[0] in {'phc', 'poselib', 'smpl_sim', 'isaacgym', 'hydra', 'open3d', 'stl'}:
                        raise AssertionError('External dependency: ' + fullname)

            sys.meta_path.insert(0, BlockExternal())
            before_numpy = torch.Tensor.numpy
            before_threads = torch.get_num_threads()
            before_path = sys.path.copy()
            before_handlers = logging.root.handlers.copy()
            with patch('torch.multiprocessing.Manager', side_effect=AssertionError('Manager created')):
                from robojudo.motion import MotionLibReal, SkeletonTree, load_robot_config
                robot = load_robot_config('robot/unitree_g1_23dof_KungfuBot.yaml')
                library = MotionLibReal({
                    'robot': robot,
                    'motion_file': 'assets/motions/g1/phc/kungfubot/Horse-stance_pose.pkl',
                    'device': 'cpu',
                })
                tree = SkeletonTree.from_mjcf(robot['asset']['assetFileName'])
                library.load_motions([tree], [torch.zeros(17)], [[0] * 10], random_sample=False)
                result = library.get_motion_state([0], [0.03])
                assert result['dof_pos'].shape == (1, 23)
            assert torch.Tensor.numpy is before_numpy
            assert torch.get_num_threads() == before_threads
            assert sys.path == before_path
            assert logging.root.handlers == before_handlers
            assert not multiprocessing.active_children()
            """
        )
        completed = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
