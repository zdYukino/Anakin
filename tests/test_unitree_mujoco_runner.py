"""Failure detection and passive-mode contracts, independent of an SDK process."""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from scripts import test_unitree_mujoco as runner


class FeedbackEnv:
    """Backend boundary fixture; command methods fail if a reader calls them."""

    def __init__(self):
        self.num_dofs = 29
        self.joint_names = [f"joint_{index}" for index in range(29)]
        self.cfg_env = SimpleNamespace(joint2motor_idx=None)
        self.dof_pos = np.zeros(29)
        self.dof_vel = np.zeros(29)
        self.base_quat = [0, 0, 0, 1]
        self.base_ang_vel = [0, 0, 0]
        self.base_pos = [0, 0, 0.8]
        self.base_lin_vel = [0, 0, 0]
        self.robot_state = SimpleNamespace(
            tick=100,
            motor_state=SimpleNamespace(tau_est=np.zeros(29)),
            imu_state=SimpleNamespace(accelerometer=[0, 0, 9.81], rpy=[0, 0, 0]),
        )
        self.advance = True
        self.enabled = False

    def update(self):
        if self.advance:
            self.robot_state.tick += 1

    def step(self, _target):
        raise AssertionError("Read mode published a joint command")

    def shutdown(self):
        raise AssertionError("Read mode called the command-publishing shutdown")


class StateMonitorTest(unittest.TestCase):
    def test_make_env_uses_real_g1_config_loopback_and_official_cpp_odometry_topic(self):
        backend = Mock()
        # Replace only the construction boundary; do not import the optional
        # native extension or initialize DDS for this configuration test.
        module = SimpleNamespace(UnitreeCppEnv=backend)
        with patch.dict(sys.modules, {"robojudo.environment.unitree_cpp_env": module}):
            for mode in ("read", "joints"):
                with self.subTest(mode=mode):
                    runner.make_env(runner.parse_args(["--mode", mode]))
                    cfg = backend.call_args.kwargs["cfg_env"]
                    self.assertEqual(type(cfg).__name__, "G1RealEnvCfg")
                    self.assertEqual(cfg.env_type, "UnitreeCppEnv")
                    self.assertEqual(cfg.act, mode == "joints")
                    self.assertEqual(cfg.dof.num_dofs, 29)
                    self.assertEqual(cfg.unitree.net_if, "lo")
                    self.assertEqual(cfg.unitree.msg_type, "hg")
                    self.assertAlmostEqual(cfg.unitree.control_dt, 0.01)
                    self.assertTrue(cfg.unitree.enable_odometry)
                    self.assertEqual(cfg.unitree.sport_state_topic, "rt/sportmodestate")

    def test_stale_and_backwards_ticks_fail(self):
        env = FeedbackEnv()
        env.advance = False
        monitor = runner.StateMonitor(1.0)
        monitor.observe(env, now=0)
        monitor.observe(env, now=0.5)
        with self.assertRaisesRegex(RuntimeError, "stale"):
            monitor.observe(env, now=1.01)
        env.robot_state.tick -= 1
        with self.assertRaisesRegex(RuntimeError, "backwards"):
            monitor.observe(env, now=1.02)

    def test_uint32_tick_wrap_is_forward_progress(self):
        env = FeedbackEnv()
        env.advance = False
        env.robot_state.tick = 0xFFFFFFFE
        monitor = runner.StateMonitor(1.0)
        monitor.observe(env, now=0)
        env.robot_state.tick = 1
        monitor.observe(env, now=0.1)
        self.assertEqual(monitor.report()["tick_elapsed"], 3)

    def test_zero_tick_nonfinite_motor_and_invalid_imu_fail(self):
        for field in ("tick", "motor", "imu"):
            env = FeedbackEnv()
            env.advance = False
            if field == "tick":
                env.robot_state.tick = 0
            elif field == "motor":
                env.dof_vel[4] = np.inf
            else:
                env.base_quat = [0, 0, 0, 0]
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                runner.StateMonitor(1.0).observe(env)

    def test_read_mode_never_steps_or_shuts_down(self):
        args = runner.parse_args(["--duration", "0.2", "--rate", "20"])
        summary = {}
        with patch.object(runner, "make_env", return_value=FeedbackEnv()):
            runner.run(args, summary, None)
        self.assertGreaterEqual(summary["state"]["tick_updates"], 2)

    def test_invalid_read_feedback_also_never_shuts_down(self):
        env = FeedbackEnv()
        env.dof_pos[8] = np.nan
        with patch.object(runner, "make_env", return_value=env), self.assertRaisesRegex(RuntimeError, "motor.q"):
            runner.run(runner.parse_args([]), {}, None)


if __name__ == "__main__":
    unittest.main()
