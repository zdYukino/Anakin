"""Deployment-runner contracts without X11, DDS, GUI or robot connections."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

from scripts import run_unitree_policy as runner


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.now += duration


class FakeEnv:
    def __init__(self, clock):
        self.clock = clock
        self.enabled = True
        self.position_limits = np.tile([-2.0, 2.0], (29, 1))
        self.dof_pos = np.zeros(29)
        self.dof_vel = np.zeros(29)
        self.base_quat = np.array([0.0, 0.0, 0.0, 1.0])
        self.base_ang_vel = np.zeros(3)
        self.base_pos = np.array([0.0, 0.0, 0.8])
        self.base_lin_vel = np.zeros(3)
        self.robot_state = SimpleNamespace(
            tick=1000,
            motor_state=SimpleNamespace(tau_est=np.zeros(29)),
            imu_state=SimpleNamespace(accelerometer=np.array([0.0, 0.0, 9.81]), rpy=np.zeros(3)),
        )
        self.commands = []
        self.frozen = False
        self.base_tick = 1000
        self.tick_scale = 1.0

    def update(self):
        if not self.frozen:
            self.robot_state.tick = self.base_tick + int(self.clock.now * 1000 * self.tick_scale)

    def step(self, target, hand_pose=None):
        self.commands.append((np.asarray(target).copy(), hand_pose))


class FakeManager:
    def __init__(self):
        self.reset_count = 0

    def get_ctrl_data(self, _env_data):
        return {"MotionCtrl": {"reference": [1, 2, 3]}, "COMMANDS": ["[EXISTING]"]}

    def reset(self):
        self.reset_count += 1


class FakePipeline:
    def __init__(self, clock):
        self.env = FakeEnv(clock)
        self.ctrl_manager = FakeManager()
        self.policy = SimpleNamespace(name="TestPolicy", get_init_dof_pos=lambda: np.zeros(29))
        self.dt = 0.02
        self.target = np.zeros(29)
        self.reset_count = 0
        self.do_safety_check = False

    def reset(self):
        self.reset_count += 1

    def step(self):
        self.ctrl_manager.get_ctrl_data(None)
        self.env.step(self.target)


class ArgumentsTest(unittest.TestCase):
    def test_event_payloads_are_typed_and_ordered(self):
        args = runner.parse_args(
            ["--event", "2:[POLICY_SWITCH],NEXT", "--event", "0:button:Left", "--event", "1:axes:0.2,-0.3,0"]
        )
        self.assertEqual([event.at for event in args.event], [0, 1, 2])
        self.assertEqual(args.event[1].value, (0.2, -0.3, 0))
        self.assertEqual(args.event[2].value, "[POLICY_SWITCH],NEXT")

    def test_invalid_events_and_nonfinite_duration_are_rejected(self):
        cases = [
            ["--duration", "nan"],
            ["--duration", "inf"],
            ["--event", "-1:[MOTION_RESET]"],
            ["--event", "nan:[MOTION_RESET]"],
            ["--event", "0:axes:1.1,0,0"],
            ["--event", "0:axes:0,0"],
            ["--event", "0:unknown"],
            ["--event", "30:[MOTION_RESET]"],
            ["--command", "0", "nan", "0"],
            ["--input", "keyboard", "--event", "0:button:Left"],
        ]
        for args in cases:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                runner.parse_args(args)

    def test_output_files_cannot_overwrite_each_other(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            runner.parse_args(["--summary", "result.json", "--log", "./result.json"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            runner.parse_args(["--summary", "result.json", "--screenshot", "./result.json"])


class ConfigTest(unittest.TestCase):
    def test_real_defaults_are_preserved_while_runner_uses_loopback(self):
        from robojudo.config.config_manager import ConfigManager

        args = runner.parse_args([])
        cfg = runner.build_config(args)
        original = ConfigManager(config_name="g1_real").get_cfg()
        self.assertEqual(cfg.env.env_type, "UnitreeCppEnv")
        self.assertEqual(cfg.env.unitree.net_if, "lo")
        self.assertEqual(cfg.env.unitree.sport_state_topic, "rt/sportmodestate")
        self.assertEqual(cfg.ctrl, [])
        self.assertEqual(original.env.unitree.net_if, "eth0")
        self.assertEqual(original.env.unitree.sport_state_topic, "rt/odommodestate")
        self.assertTrue(original.do_safety_check)
        self.assertFalse(cfg.do_safety_check)

    def test_motion_controller_is_retained_without_gui(self):
        cfg = runner.build_config(runner.parse_args(["-c", "g1_h2h"]))
        self.assertEqual([item.ctrl_type for item in cfg.ctrl], ["MotionH2HCtrl"])
        self.assertFalse(cfg.ctrl[0].motion_ctrl_gui)
        self.assertTrue(cfg.env.update_with_fk)

    def test_reduced_dev_config_uses_native_fk_without_mutating_source_or_policy(self):
        from robojudo.config.config_manager import ConfigManager
        from robojudo.tools.kinematics import MujocoKinematics

        original = ConfigManager(config_name="g1_dev").get_cfg()
        before = original.model_dump()
        cfg = runner.build_config(runner.parse_args(["-c", "g1_dev"]))
        self.assertEqual(len(original.env.dof.joint_names), 23)
        self.assertEqual(len(original.env.forward_kinematic.kinematic_joint_names), 23)
        self.assertEqual(len(cfg.env.dof.joint_names), 29)
        self.assertEqual(cfg.env.forward_kinematic.kinematic_joint_names, cfg.env.dof.joint_names)
        self.assertEqual(cfg.policy.model_dump(), original.policy.model_dump())
        kinematics = MujocoKinematics(cfg.env.forward_kinematic)
        result = kinematics.forward(
            joint_pos=np.zeros(29),
            base_pos=np.array([0.0, 0.0, 0.8]),
            base_quat=np.array([0.0, 0.0, 0.0, 1.0]),
        )
        self.assertTrue(np.isfinite(result[cfg.env.torso_name]["pos"]).all())
        self.assertEqual(original.model_dump(), before)

    def test_reduced_config_preserves_explicitly_disabled_fk_and_valid_torso(self):
        from robojudo.config.config_manager import ConfigManager

        original = ConfigManager(config_name="g1_dev").get_cfg()
        original.env.forward_kinematic = None
        original.env.update_with_fk = False
        original.env.torso_name = "pelvis"
        manager = SimpleNamespace(get_cfg=lambda: original)
        with mock.patch("robojudo.config.config_manager.ConfigManager", return_value=manager):
            cfg = runner.build_config(runner.parse_args(["-c", "g1_dev"]))
        self.assertIsNone(cfg.env.forward_kinematic)
        self.assertFalse(cfg.env.update_with_fk)
        self.assertEqual(cfg.env.torso_name, "pelvis")
        self.assertEqual(len(original.env.dof.joint_names), 23)

    def test_reduced_config_torso_missing_from_native_model_uses_native_default(self):
        from robojudo.config.config_manager import ConfigManager

        original = ConfigManager(config_name="g1_dev").get_cfg()
        original.env.torso_name = "reduced_model_only_body"
        manager = SimpleNamespace(get_cfg=lambda: original)
        with mock.patch("robojudo.config.config_manager.ConfigManager", return_value=manager):
            cfg = runner.build_config(runner.parse_args(["-c", "g1_dev"]))
        self.assertEqual(cfg.env.torso_name, "torso_link")

    def test_h1_and_irrelevant_motion_overrides_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "H1 requires"):
            runner.build_config(runner.parse_args(["-c", "h1_real"]))
        with self.assertRaisesRegex(ValueError, "tracker policy"):
            runner.build_config(runner.parse_args(["--motion-path", "motion.pt"]))

    def test_tracker_overrides_and_keyboard_input(self):
        args = runner.parse_args(
            [
                "-c",
                "g1_protomotions_tracker",
                "--motion-path",
                "motion.pt",
                "--motion-index",
                "3",
                "--input",
                "keyboard",
            ]
        )
        cfg = runner.build_config(args)
        self.assertEqual(cfg.policy.motion_path, str(Path("motion.pt").resolve()))
        self.assertEqual(cfg.policy.motion_index, 3)
        self.assertEqual([item.ctrl_type for item in cfg.ctrl], ["KeyboardCtrl"])


class InputsTest(unittest.TestCase):
    def test_overlay_preserves_reference_data_and_emits_each_event_once(self):
        manager = FakeManager()
        events = [runner.parse_event(value) for value in ("0:button:Left", "1:axes:0.5,-0.2,0.1", "1:[POLICY_MIMIC]")]
        adapter = runner.ScriptedInputs(manager, (0, 0, 0), events)
        first = adapter.get_ctrl_data(None)
        self.assertEqual(first["MotionCtrl"]["reference"], [1, 2, 3])
        self.assertEqual(first["UnitreeCtrl"]["button_event"][0]["name"], "Left")
        self.assertEqual(adapter.get_ctrl_data(None)["UnitreeCtrl"]["button_event"], [])
        adapter.elapsed = 1
        second = adapter.get_ctrl_data(None)
        self.assertEqual(second["COMMANDS"], ["[EXISTING]", "[POLICY_MIMIC]"])
        self.assertEqual(second["UnitreeCtrl"]["axes"], {"LeftX": -0.2, "LeftY": 0.5, "RightX": 0.1, "RightY": 0})
        self.assertEqual(adapter.get_ctrl_data(None)["COMMANDS"], ["[EXISTING]"])
        adapter.reset()
        self.assertEqual(manager.reset_count, 1)

    def test_target_monitor_forwards_original_targets_and_hands(self):
        env = FakeEnv(FakeClock())
        recorder = runner.CommandRecorder(env)
        target = np.full(29, 2.1)
        hands = np.array([[0.1], [0.2]])
        recorder.step(target, hands)
        np.testing.assert_array_equal(env.commands[0][0], target)
        self.assertIs(env.commands[0][1], hands)
        self.assertEqual(recorder.outside_limits, 1)

    def test_target_monitor_uses_updated_policy_limits_after_switch(self):
        env = FakeEnv(FakeClock())
        recorder = runner.CommandRecorder(env)
        target = np.full(29, 1.5)
        recorder.step(target)
        self.assertEqual(recorder.outside_limits, 0)
        env.position_limits = np.tile([-1.0, 1.0], (29, 1))
        recorder.step(target)
        self.assertEqual(recorder.outside_limits, 1)

    def test_progress_serializes_only_whitelisted_finite_scalars(self):
        policy = SimpleNamespace(
            timestep=np.int64(7),
            _frame=np.array([3]),
            _motion_done=np.bool_(False),
            _default_pose_mode=np.array([True]),
            _paused=False,
            play_speed=np.array([1, 2]),
            motion_length_s=float("nan"),
            model_weights=np.ones(1000),
        )
        self.assertEqual(
            runner.policy_progress(SimpleNamespace(policy=policy)),
            {"timestep": 7, "_frame": 3, "_motion_done": False, "_default_pose_mode": True, "_paused": False},
        )


class SimulatorWindowTest(unittest.TestCase):
    def test_only_the_owned_process_window_can_receive_reset(self):
        from Xlib import display

        wrong_window = SimpleNamespace(
            get_wm_name=lambda: "MuJoCo : another user's scene",
            get_full_property=lambda *_: SimpleNamespace(value=[999]),
        )
        owned_window = SimpleNamespace(
            get_wm_name=lambda: "MuJoCo : g1_29dof scene",
            get_full_property=lambda *_: SimpleNamespace(value=[1234]),
        )
        connection = SimpleNamespace(
            intern_atom=lambda _: 1,
            screen=lambda: SimpleNamespace(
                root=SimpleNamespace(query_tree=lambda: SimpleNamespace(children=[wrong_window, owned_window]))
            ),
            close=mock.Mock(),
        )
        with mock.patch.object(display, "Display", return_value=connection), mock.patch.object(runner.time, "sleep"):
            window = runner.SimulatorWindow(":test", SimpleNamespace(pid=1234, poll=lambda: None))
        self.assertIs(window.window, owned_window)
        window.close()
        connection.close.assert_called_once_with()


class LoopTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.pipeline = FakePipeline(self.clock)
        self.args = runner.parse_args(["--duration", "0.3", "--stale-timeout", "0.1"])
        self.summary = {}
        self.monotonic = mock.patch.object(runner.time, "monotonic", self.clock.monotonic)
        self.sleep = mock.patch.object(runner.time, "sleep", self.clock.sleep)
        self.monotonic.start()
        self.sleep.start()
        self.addCleanup(self.monotonic.stop)
        self.addCleanup(self.sleep.stop)

    def test_actual_control_and_advancing_feedback_are_recorded(self):
        log = io.StringIO()
        original_step = self.pipeline.env.step
        original_manager = self.pipeline.ctrl_manager
        runner.run_closed_loop(self.pipeline, self.args, self.summary, log)
        self.assertEqual(self.summary["steps"], 15)
        self.assertEqual(self.summary["action_count"], 15)
        self.assertGreater(self.summary["state"]["tick_elapsed"], 200)
        self.assertEqual(self.summary["policy_steps"], {"TestPolicy": 15})
        self.assertAlmostEqual(self.summary["wall_duration_s"], 0.3)
        self.assertEqual(len(log.getvalue().splitlines()), 15)
        self.assertEqual(len(json.loads(log.getvalue().splitlines()[0])["command_q"]), 29)
        self.assertEqual(self.pipeline.env.step, original_step)
        self.assertIs(self.pipeline.ctrl_manager, original_manager)

    def test_frozen_feedback_cannot_pass(self):
        self.pipeline.env.frozen = True
        with self.assertRaisesRegex(RuntimeError, "stale"):
            runner.run_closed_loop(self.pipeline, self.args, self.summary, None)
        self.assertEqual(self.summary["state"]["tick_updates"], 0)

    def test_slow_simulation_cannot_pass_a_requested_duration(self):
        self.pipeline.env.tick_scale = 0.5
        with self.assertRaisesRegex(RuntimeError, "Insufficient simulated duration"):
            runner.run_closed_loop(self.pipeline, self.args, self.summary, None)
        self.assertAlmostEqual(self.summary["simulated_duration_s"], 0.14, delta=0.002)
        self.assertGreater(self.summary["state"]["tick_updates"], 2)

    def test_continuously_controlled_blocking_blend_passes_without_catchup_burst(self):
        self.args.duration = 0.6
        self.args.event = [runner.parse_event("0:[MOTION_FADE_IN]")]
        send_times = []
        native_step = self.pipeline.env.step

        def sent(target, hand_pose=None):
            send_times.append(self.clock.now)
            native_step(target, hand_pose)

        self.pipeline.env.step = sent
        blended = False

        def step():
            nonlocal blended
            self.pipeline.ctrl_manager.get_ctrl_data(None)
            if not blended:
                blended = True
                for _ in range(15):
                    self.pipeline.env.step(self.pipeline.target)
                    self.clock.sleep(0.02)
                    self.pipeline.ctrl_manager.get_ctrl_data(None)
            else:
                self.pipeline.env.step(self.pipeline.target)

        self.pipeline.step = step
        log = io.StringIO()
        runner.run_closed_loop(self.pipeline, self.args, self.summary, log)
        self.assertAlmostEqual(self.summary["wall_duration_s"], 0.6)
        self.assertEqual(self.summary["action_count"], 30)
        self.assertEqual(self.summary["steps"], 16)
        self.assertGreater(self.summary["max_loop_work_s"], 0.2)
        self.assertLessEqual(self.summary["max_command_gap_s"], 0.021)
        self.assertEqual(self.summary["frame_drops"], 0)
        self.assertTrue(np.all(np.diff(send_times) >= 0.019))
        first = json.loads(log.getvalue().splitlines()[0])
        self.assertEqual(first["command_count"], 15)
        self.assertEqual(first["events"], ["command:[MOTION_FADE_IN]"])
        self.assertEqual(self.summary["events_consumed"], 1)

    def test_target_starvation_fails_before_or_after_backend_call(self):
        for publish_first in (False, True):
            with self.subTest(publish_first=publish_first):
                self.clock.now = 0
                pipeline = FakePipeline(self.clock)

                def step(pipeline=pipeline, publish_first=publish_first):
                    if publish_first:
                        pipeline.env.step(pipeline.target)
                    self.clock.sleep(0.201)
                    if not publish_first:
                        pipeline.env.step(pipeline.target)

                pipeline.step = step
                summary = {}
                with self.assertRaisesRegex(RuntimeError, "target gap exceeded 200ms"):
                    runner.run_closed_loop(pipeline, self.args, summary, None)
                self.assertEqual(len(pipeline.env.commands), int(publish_first))
                self.assertGreater(summary["max_command_gap_s"], 0.2)

    def test_log_flush_stall_is_part_of_control_gap_monitoring(self):
        clock = self.clock

        class SlowLog(io.StringIO):
            def flush(self):
                clock.sleep(0.21)

        with self.assertRaisesRegex(RuntimeError, "target gap exceeded 200ms"):
            runner.run_closed_loop(self.pipeline, self.args, self.summary, SlowLog())
        self.assertGreater(self.summary["max_loop_total_work_s"], 0.2)

    def test_progress_distinguishes_static_reference_from_playback(self):
        for playing in (False, True):
            with self.subTest(playing=playing):
                self.clock.now = 0
                pipeline = FakePipeline(self.clock)
                motion = SimpleNamespace(timestep=0, playing=playing, motion_length=np.array(2.0))
                pipeline.ctrl_manager.controllers = {"BeyondMimicCtrl": {"inst": motion}}
                pipeline.policy.timestep = 0

                def step(pipeline=pipeline, motion=motion):
                    pipeline.env.step(pipeline.target)
                    pipeline.policy.timestep += 1
                    if motion.playing:
                        motion.timestep += 1

                pipeline.step = step
                summary = {}
                log = io.StringIO()
                runner.run_closed_loop(pipeline, self.args, summary, log)
                self.assertEqual(summary["policy_progress"]["TestPolicy"]["timestep"], 15)
                self.assertEqual(summary["controller_progress_initial"]["BeyondMimicCtrl"]["timestep"], 0)
                self.assertEqual(summary["controller_progress"]["BeyondMimicCtrl"]["timestep"], 15 if playing else 0)
                last = json.loads(log.getvalue().splitlines()[-1])
                self.assertEqual(last["controller_progress"]["BeyondMimicCtrl"]["playing"], playing)

    def test_progress_belongs_to_the_policy_that_generated_the_frame(self):
        old = self.pipeline.policy
        old.timestep = 0
        new = SimpleNamespace(name="OtherPolicy", timestep=10)

        def step():
            self.pipeline.env.step(self.pipeline.target)
            self.pipeline.policy.timestep += 1
            self.pipeline.policy = new

        self.pipeline.step = step
        log = io.StringIO()
        runner.run_closed_loop(self.pipeline, self.args, self.summary, log)
        first = json.loads(log.getvalue().splitlines()[0])
        self.assertEqual(first["policy"], "TestPolicy")
        self.assertEqual(first["policy_progress"]["timestep"], 1)
        self.assertEqual(first["active_policy_progress"]["timestep"], 10)
        self.assertEqual(self.summary["policy_progress"]["TestPolicy"]["timestep"], 1)

    def test_invalid_action_is_blocked_before_native_actuation(self):
        self.pipeline.target[0] = np.nan
        with self.assertRaisesRegex(RuntimeError, "policy PD target"):
            runner.run_closed_loop(self.pipeline, self.args, self.summary, None)
        self.assertEqual(self.pipeline.env.commands, [])
        self.assertEqual(self.summary["action_count"], 0)

    def test_fall_and_disabled_backend_are_reported(self):
        self.pipeline.env.base_pos[2] = 0.1
        with self.assertRaisesRegex(RuntimeError, "Robot fell"):
            runner.run_closed_loop(self.pipeline, self.args, self.summary, None)
        self.assertEqual(self.summary["steps"], 1)
        self.pipeline.env.base_pos[2] = 0.8
        self.pipeline.env.enabled = False
        with self.assertRaisesRegex(RuntimeError, "disabled itself"):
            runner.run_closed_loop(self.pipeline, self.args, {}, None)

    def test_control_stops_when_owned_simulator_exits(self):
        process = SimpleNamespace(poll=lambda: 1)
        with self.assertRaisesRegex(RuntimeError, "simulator exited"):
            runner.run_closed_loop(self.pipeline, self.args, self.summary, None, simulator=process)
        self.assertEqual(self.summary["action_count"], 0)

    def test_unconsumed_event_does_not_silently_pass(self):
        self.args.event = [runner.parse_event("0.299:[MOTION_RESET]")]
        with self.assertRaisesRegex(RuntimeError, "all scheduled events"):
            runner.run_closed_loop(self.pipeline, self.args, self.summary, None)

    def test_live_reset_requires_acknowledgement(self):
        window = SimpleNamespace(key=lambda _name: None)
        with self.assertRaisesRegex(RuntimeError, "reset was not acknowledged"):
            runner.start_control(self.pipeline, window)
        self.assertFalse(self.pipeline.do_safety_check)

    def test_initial_target_is_sent_before_reset_and_safety_is_restored(self):
        def reset(_name):
            self.assertEqual(len(self.pipeline.env.commands), 1)
            self.pipeline.env.base_tick = -int(self.clock.now * 1000)
            self.clock.sleep(0.05)

        runner.start_control(self.pipeline, SimpleNamespace(key=reset))
        self.assertTrue(self.pipeline.do_safety_check)
        self.assertEqual(self.pipeline.reset_count, 1)

    def test_initial_target_is_validated_before_native_actuation(self):
        self.pipeline.policy.get_init_dof_pos = lambda: np.full(29, np.nan)
        with self.assertRaisesRegex(RuntimeError, "initial policy PD target"):
            runner.start_control(self.pipeline, SimpleNamespace(key=lambda _: None))
        self.assertEqual(self.pipeline.env.commands, [])

    def test_heading_alignment_is_reset_only_after_fresh_world_feedback(self):
        observed = []
        self.pipeline.policy.reset_alignment = lambda: observed.append(self.pipeline.env.robot_state.tick)

        def reset(_name):
            self.pipeline.env.base_tick = -int(self.clock.now * 1000)
            self.clock.sleep(0.05)

        runner.start_control(self.pipeline, SimpleNamespace(key=reset))
        self.assertEqual(observed, [50])


class FailureReportTest(unittest.TestCase):
    def test_main_saves_runtime_failure_with_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested/result.json"

            def fail(_args, summary):
                summary["stage"] = "pipeline_load"
                raise FileNotFoundError("checkpoint missing")

            with (
                mock.patch.object(runner, "run", fail),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                code = runner.main(["--summary", str(path)])
            report = json.loads(path.read_text())
            self.assertEqual(code, 1)
            self.assertFalse(report["passed"])
            self.assertEqual(report["stage"], "pipeline_load")
            self.assertIn("checkpoint missing", report["error"])

    def test_owned_simulator_is_stopped_after_window_failure_and_display_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            binary = repo / "simulate/build/unitree_mujoco"
            binary.parent.mkdir(parents=True)
            binary.write_text("placeholder")
            binary.chmod(0o755)
            (repo / "simulate/config.yaml").write_text("enable_elastic_band: 0\n")
            scene = repo / "unitree_robots/g1/scene_29dof.xml"
            scene.parent.mkdir(parents=True)
            scene.write_text("<mujoco/>")
            args = runner.parse_args(["--repo", str(repo), "--headless"])
            process = SimpleNamespace(pid=1234)
            with (
                mock.patch.object(runner, "build_config", return_value=SimpleNamespace()),
                mock.patch.object(runner.subprocess, "Popen", return_value=process),
                mock.patch.object(runner, "SimulatorWindow", side_effect=RuntimeError("window failure")),
                mock.patch.object(runner, "stop_process") as stop,
                mock.patch.object(runner, "find_xvfb", return_value=Path("Xvfb")),
                mock.patch.object(runner, "virtual_display", return_value=contextlib.nullcontext((":private", None))),
                mock.patch.dict(runner.os.environ, {"DISPLAY": ":test"}),
            ):
                with self.assertRaisesRegex(RuntimeError, "window failure"):
                    runner.run(args, {})
                self.assertEqual(runner.os.environ["DISPLAY"], ":test")
            stop.assert_called_once_with(process)


if __name__ == "__main__":
    unittest.main()
