"""Run PHC-format controller paths without external PHC/poselib or a window."""

import copy
import importlib
import importlib.abc
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import joblib
import numpy as np
import torch


class _BlockUpstream(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in {"phc", "poselib"}:
            raise AssertionError(f"External motion dependency imported: {fullname}")
        return None


class TestPHCControllers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Install before importing RoboJuDo: robot configs are also loaded during
        # package initialization, so this covers config and controller imports.
        for name in sys.modules:
            if name.split(".", 1)[0] in {"phc", "poselib"}:
                raise AssertionError(f"Upstream package was already imported: {name}")
        blocker = _BlockUpstream()
        sys.meta_path.insert(0, blocker)
        cls.addClassCleanup(sys.meta_path.remove, blocker)

        from robojudo.config.g1.ctrl.g1_motion_ctrl_cfg import (
            G1MotionCtrlCfg,
            G1MotionH2HCtrlCfg,
            G1MotionKungfuBotCtrlCfg,
            G1MotionTwistCtrlCfg,
        )
        from robojudo.config.h1.ctrl.h1_motion_ctrl_cfg import H1MotionH2HCtrlCfg
        from robojudo.controller.motion_ctrl import MotionCtrl
        from robojudo.controller.motion_h2h_ctrl import MotionH2HCtrl
        from robojudo.controller.motion_kungfubot_ctrl import MotionKungfuBotCtrl
        from robojudo.controller.motion_twist_ctrl import MotionTwistCtrl
        from robojudo.tools.kinematics import MujocoKinematics
        from robojudo.tools.tool_cfgs import ForwardKinematicCfg

        cls.G1MotionCtrlCfg = G1MotionCtrlCfg
        cls.G1MotionH2HCtrlCfg = G1MotionH2HCtrlCfg
        cls.G1MotionKungfuBotCtrlCfg = G1MotionKungfuBotCtrlCfg
        cls.G1MotionTwistCtrlCfg = G1MotionTwistCtrlCfg
        cls.H1MotionH2HCtrlCfg = H1MotionH2HCtrlCfg
        cls.MotionCtrl = MotionCtrl
        cls.MotionH2HCtrl = MotionH2HCtrl
        cls.MotionKungfuBotCtrl = MotionKungfuBotCtrl
        cls.MotionTwistCtrl = MotionTwistCtrl
        cls.MujocoKinematics = MujocoKinematics
        cls.ForwardKinematicCfg = ForwardKinematicCfg

    def setUp(self):
        gui = patch("robojudo.controller.motion_ctrl.MotionGUI", side_effect=AssertionError("Unexpected window"))
        gui.start()
        self.addCleanup(gui.stop)

    def assert_payload(self, data, expected_shapes):
        self.assertEqual(set(data), set(expected_shapes))
        for key, shape in expected_shapes.items():
            with self.subTest(field=key):
                self.assertIsInstance(data[key], np.ndarray)
                self.assertEqual(data[key].shape, shape)
                self.assertTrue(np.isfinite(data[key]).all())

    def fk_environment(self, cfg):
        """A headless environment fixture with real MuJoCo forward kinematics."""
        kinematics = self.MujocoKinematics(
            self.ForwardKinematicCfg(xml_path=cfg.phc.robot_config["asset"]["assetFileName"], debug_viz=False)
        )
        fk_info = kinematics.forward(
            joint_pos=np.linspace(-0.05, 0.05, kinematics.num_joints),
            base_pos=np.array([0.2, -0.1, 1.0]),
            base_quat=np.array([0.0, 0.0, 0.0, 1.0]),
        )
        return SimpleNamespace(kinematics=kinematics, fk_info=fk_info)

    def test_import_guard_and_internal_resource_resolution(self):
        for package in ("phc", "poselib"):
            with self.subTest(package=package), self.assertRaisesRegex(AssertionError, "External motion dependency"):
                importlib.import_module(package)
        for cfg_type in (self.G1MotionCtrlCfg, self.G1MotionKungfuBotCtrlCfg, self.H1MotionH2HCtrlCfg):
            with self.subTest(config=cfg_type.__name__):
                cfg = cfg_type(motion_ctrl_gui=False)
                model = Path(cfg.phc.robot_config["asset"]["assetFileName"])
                self.assertTrue(model.is_file())
                self.assertIn("robojudo/motion/resources/", model.as_posix())
                self.assertNotIn("third_party", model.parts)

    def test_controller_registry_uses_internal_runtime(self):
        from robojudo.controller import ctrl_registry

        for ctrl in (self.MotionCtrl, self.MotionH2HCtrl, self.MotionKungfuBotCtrl, self.MotionTwistCtrl):
            with self.subTest(controller=ctrl.__name__):
                self.assertIs(ctrl_registry.get(ctrl.__name__), ctrl)

    def test_base_controller_shapes_progress_reset_and_copy(self):
        cfg = self.G1MotionCtrlCfg(motion_ctrl_gui=False, track_keypoints_names=["pelvis", "torso_link"])
        ctrl = self.MotionCtrl(cfg, env=None)
        data = ctrl.get_data()
        self.assert_payload(data, {"ref_body_pos_subset": (5, 3), "ref_body_vel_subset": (5, 3), "dof_pos": (29,)})
        self.assertFalse(ctrl.enable_gui)
        self.assertFalse(hasattr(ctrl, "motion_gui"))
        np.testing.assert_allclose(data["ref_body_pos_subset"][0, :2], 0, atol=1e-6)
        initial_dofs = data["dof_pos"].copy()
        data["dof_pos"][:] = 100
        np.testing.assert_array_equal(ctrl.get_data()["dof_pos"], initial_dofs)

        ctrl.play_speed_ratio = 0.5
        ctrl.post_step_callback(motion_time_step=0.2)
        self.assertAlmostEqual(ctrl.motion_time, 0.1)
        self.assertGreater(np.max(np.abs(ctrl.get_data()["dof_pos"] - initial_dofs)), 1e-4)
        ctrl.play_speed_ratio = 0
        ctrl.post_step_callback(motion_time_step=0.2)
        self.assertAlmostEqual(ctrl.motion_time, 0.1)
        ctrl.post_step_callback(commands=["[MOTION_RESET]"])
        self.assertEqual(ctrl.motion_time, 0)
        np.testing.assert_allclose(ctrl.get_data()["dof_pos"], initial_dofs, atol=1e-6)

    def test_h2h_with_real_fk_on_g1_and_h1(self):
        for cfg_type, dofs in ((self.G1MotionH2HCtrlCfg, 29), (self.H1MotionH2HCtrlCfg, 19)):
            with self.subTest(config=cfg_type.__name__):
                cfg = cfg_type(motion_ctrl_gui=False, track_keypoints_names=["pelvis", "torso_link"])
                env = self.fk_environment(cfg)
                ctrl = self.MotionH2HCtrl(cfg, env)
                data = ctrl.get_data()
                self.assert_payload(
                    data,
                    {
                        "ref_body_pos_subset": (5, 3),
                        "ref_body_vel_subset": (5, 3),
                        "robot_body_pos_subset": (5, 3),
                        "dof_pos": (dofs,),
                    },
                )
                np.testing.assert_allclose(data["robot_body_pos_subset"][0], env.fk_info["pelvis"]["pos"])
                np.testing.assert_array_equal(data["ref_body_vel_subset"], 0)
                ctrl.play_speed_ratio = 0.5
                ctrl.post_step_callback()
                self.assertAlmostEqual(ctrl.motion_time, 0.01)
                self.assertTrue(np.isfinite(ctrl.get_data()["ref_body_vel_subset"]).all())

    def test_kungfubot_batched_future_payload(self):
        cfg = self.G1MotionKungfuBotCtrlCfg(motion_ctrl_gui=False)
        ctrl = self.MotionKungfuBotCtrl(cfg, env=None)
        data = ctrl.get_data()
        anchor = data.pop("ref_frame_anchor")
        self.assertEqual(tuple(value.shape for value in anchor), ((3,), (4,)))
        self.assertTrue(all(np.isfinite(value).all() for value in anchor))
        self.assert_payload(
            data,
            {
                "future_motion_root_height": (20,),
                "future_motion_roll_pitch": (40,),
                "future_motion_base_lin_vel": (60,),
                "future_motion_base_yaw_vel": (20,),
                "future_motion_dof_pos": (460,),
                "next_step_ref_motion": (57,),
            },
        )
        np.testing.assert_array_equal(ctrl.tar_obs_steps[[0, -1]].cpu(), [1, 95])
        ctrl.motion_time = 0.5
        ctrl.post_step_callback()
        self.assertAlmostEqual(ctrl.motion_time, 0.52)
        self.assertTrue(np.isfinite(ctrl.get_data()["next_step_ref_motion"]).all())

    def test_twist_wrist_padding_payload(self):
        ctrl = self.MotionTwistCtrl(self.G1MotionTwistCtrlCfg(motion_ctrl_gui=False), env=None)
        data = ctrl.get_data()
        self.assert_payload(data, {"action_mimic": (33,)})
        # TWIST prepends eight root values and inserts zero G1 wrist joints.
        np.testing.assert_array_equal(data["action_mimic"][[8 + 19, 8 + 24]], 0)
        ctrl.motion_time = 0.5
        ctrl.post_step_callback()
        self.assertAlmostEqual(ctrl.motion_time, 0.52)
        self.assert_payload(ctrl.get_data(), {"action_mimic": (33,)})

    def test_switching_derived_two_clip_motion(self):
        cfg = self.G1MotionCtrlCfg(motion_ctrl_gui=False)
        original = next(iter(joblib.load(cfg.motion_path).values()))
        raised = copy.deepcopy(original)
        raised["root_trans_offset"] = raised["root_trans_offset"] + np.array([0, 0, 0.25])

        class FileCfg(self.G1MotionCtrlCfg):
            source_file: str

            @property
            def motion_path(self):
                return self.source_file

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "two_clips.pkl"
            joblib.dump({"first": original, "raised": raised}, path)
            ctrl = self.MotionCtrl(FileCfg(motion_ctrl_gui=False, source_file=str(path)), env=None)
            initial = ctrl.get_motion()["root_pos"].clone()
            self.assertEqual(list(ctrl.motion_name), ["first"])
            ctrl.post_step_callback(motion_time_step=0.2)
            ctrl.get_data()
            ctrl.load_motion(1, block=True)
            self.assertEqual(ctrl.motion_id, 1)
            self.assertEqual(list(ctrl.motion_name), ["raised"])
            self.assertEqual(ctrl.motion_time, 0)
            torch.testing.assert_close(ctrl.get_motion()["root_pos"], initial + torch.tensor([[0.0, 0.0, 0.25]]))
            ctrl.post_step_callback(motion_time_step=0.2)
            ctrl.get_data()
            ctrl.load_motion(0, block=True)
            self.assertEqual(list(ctrl.motion_name), ["first"])
            torch.testing.assert_close(ctrl.get_motion()["root_pos"], initial)


if __name__ == "__main__":
    unittest.main()
