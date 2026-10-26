"""Initial deployment feedback and H2H FK consumption without DDS or a GUI."""

import importlib.util
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation


class NativeFeedback:
    """Native binding boundary double; no network or background threads."""

    def __init__(self):
        self.quaternion_xyzw = Rotation.from_euler("xyz", [0.08, -0.04, 0.3]).as_quat()
        self.robot = SimpleNamespace(
            tick=1234,
            motor_state=SimpleNamespace(
                q=np.linspace(-0.08, 0.12, 29),
                dq=np.linspace(0.01, 0.1, 29),
                tau_est=np.zeros(29),
            ),
            imu_state=SimpleNamespace(
                quaternion=self.quaternion_xyzw[[3, 0, 1, 2]],
                gyroscope=np.array([0.1, -0.2, 0.3]),
                rpy=np.array([0.08, -0.04, 0.3]),
            ),
            wireless_remote=bytes(40),
        )
        self.sport = SimpleNamespace(position=np.array([1.3, -0.4, 0.84]), velocity=np.array([0.1, -0.3, 0.2]))
        self.ready = False
        self.read_count = 0

    def self_check(self):
        self.ready = True
        return True

    def get_robot_state(self):
        if not self.ready:
            raise AssertionError("Feedback read before native self-check")
        self.read_count += 1
        return self.robot

    def get_sport_state(self):
        return self.sport


@unittest.skipUnless(
    importlib.util.find_spec("unitree_cpp"), "unitree-cpp optional deployment binding is not installed"
)
class InitialStateTest(unittest.TestCase):
    def setUp(self):
        from robojudo.config.g1.env.g1_real_env_cfg import G1RealEnvCfg
        from robojudo.environment import unitree_cpp_env

        self.module = unitree_cpp_env
        self.cfg = G1RealEnvCfg()
        self.cfg.forward_kinematic.debug_viz = False
        self.feedback = NativeFeedback()
        self.controller = patch.object(unitree_cpp_env, "UnitreeController", return_value=self.feedback)
        self.controller.start()
        self.addCleanup(self.controller.stop)
        sleep = patch.object(unitree_cpp_env.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)

    def independent_torso_pose(self, env):
        """Bare MuJoCo oracle, independent of Environment.fk/MujocoKinematics."""
        model = mujoco.MjModel.from_xml_path(self.cfg.forward_kinematic.xml_path)
        data = mujoco.MjData(model)
        data.qpos[:3] = self.feedback.sport.position
        data.qpos[3:7] = self.feedback.robot.imu_state.quaternion
        for name, position in zip(env.joint_names, self.feedback.robot.motor_state.q, strict=True):
            joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
            data.qpos[model.jnt_qposadr[joint]] = position
        mujoco.mj_forward(model, data)
        torso = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, self.cfg.torso_name)
        return data.xpos[torso].copy(), data.xquat[torso][[1, 2, 3, 0]].copy()

    def test_constructor_exposes_measured_joint_imu_odometry_and_real_fk(self):
        env = self.module.UnitreeCppEnv(self.cfg)
        self.assertGreaterEqual(self.feedback.read_count, 1)
        np.testing.assert_allclose(env.dof_pos, self.feedback.robot.motor_state.q)
        np.testing.assert_allclose(env.dof_vel, self.feedback.robot.motor_state.dq)
        np.testing.assert_allclose(env.base_quat, self.feedback.quaternion_xyzw)
        np.testing.assert_allclose(env.base_pos, self.feedback.sport.position)
        np.testing.assert_allclose(env.base_ang_vel, self.feedback.robot.imu_state.gyroscope)
        expected_position, expected_quaternion = self.independent_torso_pose(env)
        np.testing.assert_allclose(env.torso_pos, expected_position, atol=1e-7)
        np.testing.assert_allclose(env.torso_quat, expected_quaternion, atol=1e-7)
        self.assertEqual(set(env.fk_info), set(env.kinematics.body_names))
        np.testing.assert_allclose(env.fk_info[self.cfg.torso_name]["pos"], expected_position, atol=1e-7)
        self.assertTrue(np.isfinite(env.torso_ang_vel).all())

    def test_h2h_can_consume_first_snapshot_and_sees_updated_fk(self):
        from robojudo.config.g1.ctrl.g1_motion_ctrl_cfg import G1MotionH2HCtrlCfg
        from robojudo.controller.motion_h2h_ctrl import MotionH2HCtrl

        env = self.module.UnitreeCppEnv(self.cfg)
        cfg = G1MotionH2HCtrlCfg(motion_ctrl_gui=False, track_keypoints_names=["pelvis", "torso_link"])
        with patch("robojudo.controller.motion_ctrl.MotionGUI", side_effect=AssertionError("Unexpected window")):
            controller = MotionH2HCtrl(cfg, env)
        first = controller.get_data()
        self.assertEqual(first["robot_body_pos_subset"].shape, (5, 3))
        np.testing.assert_allclose(first["robot_body_pos_subset"][0], self.feedback.sport.position, atol=1e-7)
        np.testing.assert_allclose(first["robot_body_pos_subset"][1], self.independent_torso_pose(env)[0], atol=1e-7)

        self.feedback.sport.position += np.array([0.2, -0.1, 0.03])
        self.feedback.robot.motor_state.q[13] += 0.2
        env.update()
        second = controller.get_data()
        self.assertGreater(np.linalg.norm(second["robot_body_pos_subset"] - first["robot_body_pos_subset"]), 0.1)
        np.testing.assert_allclose(second["robot_body_pos_subset"][0], self.feedback.sport.position, atol=1e-7)
        np.testing.assert_allclose(second["robot_body_pos_subset"][1], self.independent_torso_pose(env)[0], atol=1e-7)
        for value in second.values():
            self.assertTrue(np.isfinite(value).all())

    def test_feedback_is_available_when_fk_is_explicitly_disabled(self):
        self.cfg.forward_kinematic = None
        self.cfg.update_with_fk = False
        env = self.module.UnitreeCppEnv(self.cfg)
        np.testing.assert_allclose(env.get_data().dof_pos, self.feedback.robot.motor_state.q)
        np.testing.assert_allclose(env.get_data().base_pos, self.feedback.sport.position)
        self.assertIsNone(env.fk_info)
        self.assertIsNone(env.torso_pos)


if __name__ == "__main__":
    unittest.main()
