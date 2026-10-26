"""Run an Anakin deployment pipeline against the official floating G1 simulator.

After SDK/model loading, an initial target is published and the simulator is
reset to its own initial state directly into closed-loop policy control. This
simulation-only startup replaces the physical robot's lifted preparation procedure;
it does not change the model or provide support during the measured run.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

import numpy as np

if __package__:
    from .run_unitree_mujoco import ROOT, find_xvfb, stop_process, virtual_display
    from .test_unitree_mujoco import StateMonitor, finite_vector
else:
    from run_unitree_mujoco import ROOT, find_xvfb, stop_process, virtual_display
    from test_unitree_mujoco import StateMonitor, finite_vector


@dataclass(frozen=True)
class ScheduledEvent:
    at: float
    kind: str
    value: Any


def parse_axes(values) -> tuple[float, float, float]:
    try:
        axes = tuple(float(value) for value in values)
    except ValueError as error:
        raise ValueError("axes must be three numbers between -1 and 1") from error
    if len(axes) != 3 or not all(math.isfinite(value) and -1 <= value <= 1 for value in axes):
        raise ValueError("axes must be three finite numbers between -1 and 1")
    return axes


def parse_event(value: str) -> ScheduledEvent:
    try:
        when, payload = value.split(":", 1)
        at = float(when)
        if not math.isfinite(at) or at < 0:
            raise ValueError("event time must be finite and nonnegative")
        if payload.startswith("axes:"):
            return ScheduledEvent(at, "axes", parse_axes(payload[5:].split(",")))
        if payload.startswith("button:") and re.fullmatch(r"[A-Za-z0-9_]+", payload[7:]):
            return ScheduledEvent(at, "button", payload[7:])
        if re.fullmatch(r"\[[A-Z0-9_]+\](?:,[^:\n]+)?", payload):
            return ScheduledEvent(at, "command", payload)
        raise ValueError("expected [COMMAND], button:NAME, or axes:VX,VY,YAW")
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"Invalid event {value!r}: {error}") from error


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--config", default="g1_real")
    parser.add_argument("--repo", type=Path, default=ROOT.parent / "unitree_mujoco")
    parser.add_argument("--headless", action="store_true", help="Use a private Xvfb display.")
    parser.add_argument("--input", choices=("scripted", "keyboard", "unitree"), default="scripted")
    parser.add_argument("--duration", type=float, default=30.0, help="Measured control duration in seconds.")
    parser.add_argument("--command", nargs=3, type=float, default=(0.0, 0.0, 0.0), metavar=("VX", "VY", "YAW"))
    parser.add_argument("--event", type=parse_event, action="append", default=[], metavar="TIME:ACTION")
    parser.add_argument("--motion-path", type=Path, help="Tracker policy reference motion override.")
    parser.add_argument("--motion-index", type=int, help="Tracker policy reference index override.")
    parser.add_argument("--stale-timeout", type=float, default=0.5)
    parser.add_argument("--max-tilt", type=float, default=1.0, help="Maximum base tilt in radians.")
    parser.add_argument("--min-height", type=float, default=0.3, help="Minimum pelvis height in metres.")
    parser.add_argument("--summary", type=Path, default=ROOT / "logs/unitree_policy/summary.json")
    parser.add_argument("--log", type=Path, help="Write measured states, policy IDs and targets as JSONL.")
    parser.add_argument("--simulator-log", type=Path, help="Write simulator/Xvfb output separately.")
    parser.add_argument("--screenshot", type=Path, help="Save the official viewer before shutdown damping.")
    args = parser.parse_args(argv)
    for name, minimum, maximum in (
        ("duration", 0.2, 3600),
        ("stale_timeout", 0.1, 10),
        ("max_tilt", 0.01, math.pi),
        ("min_height", 0, 2),
    ):
        value = getattr(args, name)
        if not math.isfinite(value) or not minimum <= value <= maximum:
            parser.error(f"--{name.replace('_', '-')} must be finite and between {minimum} and {maximum}")
    try:
        args.command = parse_axes(args.command)
    except ValueError as error:
        parser.error(str(error))
    if args.motion_index is not None and args.motion_index < 0:
        parser.error("--motion-index must be nonnegative")
    paths = [
        path.resolve() for path in (args.summary, args.log, args.simulator_log, args.screenshot) if path is not None
    ]
    if len(paths) != len(set(paths)):
        parser.error("summary, sample log, simulator log and screenshot must be different files")
    if any(event.at >= args.duration for event in args.event):
        parser.error("all events must occur before --duration")
    if args.input != "scripted" and (any(args.command) or any(event.kind != "command" for event in args.event)):
        parser.error("axes and button events require --input scripted")
    args.event.sort(key=lambda event: event.at)
    return args


def build_config(args: argparse.Namespace):
    """Adapt a private config instance; physical robot defaults remain untouched."""
    from robojudo.config.config_manager import ConfigManager
    from robojudo.config.g1.env.g1_real_env_cfg import G1RealEnvCfg
    from robojudo.controller.ctrl_cfgs import KeyboardCtrlCfg, UnitreeCtrlCfg

    cfg = ConfigManager(config_name=args.config).get_cfg().model_copy(deep=True)
    if cfg.robot != "g1":
        raise ValueError("This runner uses the official G1 29-DOF scene; H1 requires its own backend and scene")
    original_env = cfg.env
    cfg.env = G1RealEnvCfg()
    same_joint_order = original_env.dof.joint_names == cfg.env.dof.joint_names
    # The deployment backend always supplies native 29-joint feedback. A
    # reduced simulation FK model cannot consume that vector without changing
    # its body topology; retain the native model when adapting such configs.
    if same_joint_order or original_env.forward_kinematic is None:
        cfg.env.forward_kinematic = original_env.forward_kinematic
    cfg.env.update_with_fk = original_env.update_with_fk
    if same_joint_order or original_env.torso_name == cfg.env.torso_name:
        cfg.env.torso_name = original_env.torso_name
    else:
        native_bodies = {body.get("name") for body in ET.parse(cfg.env.xml).findall(".//body")}
        if original_env.torso_name in native_bodies:
            cfg.env.torso_name = original_env.torso_name
    cfg.env.unitree.net_if = "lo"
    cfg.env.unitree.sport_state_topic = "rt/sportmodestate"
    cfg.env.born_place_align = False
    cfg.do_safety_check = False  # Startup samples precede the simulator reset.
    cfg.run_fullspeed = False
    policies = []
    for field in ("policy", "loco_policy"):
        if hasattr(cfg, field):
            policies.append(getattr(cfg, field))
    for field in ("policies", "mimic_policies"):
        policies.extend(getattr(cfg, field, []))
    cfg.env.unitree.control_dt = 1.0 / policies[0].freq
    if args.motion_path is not None or args.motion_index is not None:
        trackers = [policy for policy in policies if hasattr(policy, "motion_path")]
        if not trackers:
            raise ValueError("Motion overrides require a tracker policy with motion_path/motion_index fields")
        for policy in trackers:
            if args.motion_path is not None:
                policy.motion_path = str(args.motion_path.resolve())
            if args.motion_index is not None:
                policy.motion_index = args.motion_index
    input_types = {"KeyboardCtrl", "JoystickCtrl", "UnitreeCtrl"}
    original_inputs = {
        controller.ctrl_type: controller for controller in cfg.ctrl if controller.ctrl_type in input_types
    }
    cfg.ctrl = [controller for controller in cfg.ctrl if controller.ctrl_type not in input_types]
    if args.input == "keyboard":
        cfg.ctrl.insert(0, original_inputs.get("KeyboardCtrl", KeyboardCtrlCfg()))
    elif args.input == "unitree":
        cfg.ctrl.insert(0, original_inputs.get("UnitreeCtrl", UnitreeCtrlCfg()))
    for controller in cfg.ctrl:
        if hasattr(controller, "motion_ctrl_gui"):
            controller.motion_ctrl_gui = False
    return cfg


class ScriptedInputs:
    """Local input adapter that preserves reference controllers and callbacks."""

    def __init__(self, manager, command, events, scripted: bool = True):
        self.manager = manager
        self.axes = tuple(command)
        self.events = events
        self.scripted = scripted
        self.elapsed = 0.0
        self.cursor = 0
        self.last_events: list[str] = []
        self.deliveries: list[dict] = []
        self.time_origin: float | None = None

    def __getattr__(self, name):
        return getattr(self.manager, name)

    def get_ctrl_data(self, env_data):
        data = self.manager.get_ctrl_data(env_data)
        buttons = []
        commands = list(data.get("COMMANDS", []))
        self.last_events = []
        while self.cursor < len(self.events) and self.events[self.cursor].at <= self.elapsed:
            event = self.events[self.cursor]
            self.cursor += 1
            self.last_events.append(f"{event.kind}:{event.value}")
            self.deliveries.append(
                {
                    "scheduled_s": event.at,
                    "delivered_s": self.elapsed if self.time_origin is None else time.monotonic() - self.time_origin,
                    "kind": event.kind,
                    "value": event.value,
                }
            )
            if event.kind == "command":
                commands.append(event.value)
            elif event.kind == "axes":
                self.axes = event.value
            else:
                buttons.append({"type": "button", "name": event.value, "pressed": True})
        if self.scripted:
            vx, vy, yaw = self.axes
            data["UnitreeCtrl"] = {
                "axes": {"LeftX": vy, "LeftY": vx, "RightX": yaw, "RightY": 0.0},
                "button_event": buttons,
                "keyboard_event": [],
            }
        elif buttons:
            raise ValueError("Scripted button events require --input scripted")
        data["COMMANDS"] = commands
        return data


class CommandRecorder:
    """Validate targets before the native backend, without changing its behavior."""

    def __init__(self, env, period: float = 0.02):
        self.env = env
        self.original = env.step
        self.last = None
        self.count = 0
        self.max_abs = 0.0
        self.outside_limits = 0
        self.period = period
        self.last_send_time = time.monotonic()
        self.first_send_time: float | None = None
        self.max_gap_s = 0.0
        self.gap_sum_s = 0.0
        self.late_commands = 0

    def command_age(self) -> float:
        age = time.monotonic() - self.last_send_time
        self.max_gap_s = max(self.max_gap_s, age)
        return age

    def check_gap(self):
        age = self.command_age()
        if age > 0.2:
            raise RuntimeError(f"Policy target gap exceeded 200ms: {age:.3f}s")

    def step(self, pd_target, hand_pose=None):
        self.check_gap()
        sent_at = time.monotonic()
        target = finite_vector(pd_target, 29, "policy PD target")
        self.original(pd_target, hand_pose)
        if self.count:
            gap = sent_at - self.last_send_time
            self.gap_sum_s += gap
            self.late_commands += int(gap > self.period * 1.5)
        else:
            self.first_send_time = sent_at
        self.last_send_time = sent_at
        self.last = target.copy()
        self.count += 1
        self.max_abs = max(self.max_abs, float(np.max(np.abs(target))))
        limits = self.env.position_limits
        self.outside_limits += int(np.any((target < limits[:, 0]) | (target > limits[:, 1])))


POLICY_PROGRESS_FIELDS = (
    "timestep",
    "flag_motion_done",
    "_frame",
    "_motion_done",
    "default_pose_mode",
    "_default_pose_mode",
    "_paused",
    "play_speed",
    "motion_length_s",
    "max_timestep",
)
CONTROLLER_PROGRESS_FIELDS = ("motion_time", "play_speed_ratio", "timestep", "playing", "motion_length")


def scalar_progress(instance, fields) -> dict:
    """Read known progress scalars, never serialize model tensors or arbitrary state."""
    result = {}
    for field in fields:
        value = getattr(instance, field, None)
        if isinstance(value, np.generic) or isinstance(value, np.ndarray) and value.size == 1:
            value = value.item()
        elif hasattr(value, "numel") and value.numel() == 1:
            value = value.item()
        if isinstance(value, str | bool | int | float) and (not isinstance(value, float) or math.isfinite(value)):
            result[field] = value
    return result


def policy_progress(policy) -> dict:
    return scalar_progress(getattr(policy, "policy", policy), POLICY_PROGRESS_FIELDS)


def controller_progress(manager) -> dict:
    return {
        name: scalar_progress(entry["inst"], CONTROLLER_PROGRESS_FIELDS)
        for name, entry in getattr(manager, "controllers", {}).items()
        if any(hasattr(entry["inst"], field) for field in CONTROLLER_PROGRESS_FIELDS)
    }


class SimulatorWindow:
    def __init__(self, display_name: str, process, timeout: float = 15):
        from Xlib import Xatom, display

        self.display = display.Display(display_name)
        pid_atom = self.display.intern_atom("_NET_WM_PID")
        self.window = None
        deadline = time.monotonic() + timeout
        while self.window is None:
            if process.poll() is not None:
                self.close()
                raise RuntimeError(f"Simulator exited before its window was ready: {process.returncode}")
            for window in self.display.screen().root.query_tree().children:
                owner = window.get_full_property(pid_atom, Xatom.CARDINAL)
                if (
                    "MuJoCo" in (window.get_wm_name() or "")
                    and owner is not None
                    and len(owner.value) == 1
                    and int(owner.value[0]) == process.pid
                ):
                    self.window = window
                    break
            if time.monotonic() > deadline:
                self.close()
                raise RuntimeError("Timed out waiting for the official MuJoCo window")
            time.sleep(0.05)

    def key(self, name: str):
        from Xlib import XK, X
        from Xlib.ext import xtest

        self.window.set_input_focus(X.RevertToParent, X.CurrentTime)
        code = self.display.keysym_to_keycode(XK.string_to_keysym(name))
        xtest.fake_input(self.display, X.KeyPress, code)
        xtest.fake_input(self.display, X.KeyRelease, code)
        self.display.sync()
        time.sleep(0.05)

    def close(self):
        self.display.close()

    def click(self, x: int, y: int):
        from Xlib import X
        from Xlib.ext import xtest

        origin = self.window.translate_coords(self.display.screen().root, 0, 0)
        xtest.fake_input(self.display, X.MotionNotify, x=origin.x + x, y=origin.y + y)
        xtest.fake_input(self.display, X.ButtonPress, 1)
        xtest.fake_input(self.display, X.ButtonRelease, 1)
        self.display.sync()

    def save_screenshot(self, path: Path):
        from PIL import Image
        from Xlib import X

        geometry = self.window.get_geometry()
        pixels = self.window.get_image(0, 0, geometry.width, geometry.height, X.ZPixmap, 0xFFFFFFFF)
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.frombytes("RGB", (geometry.width, geometry.height), pixels.data, "raw", "BGRX").save(path)


def start_control(pipeline, window):
    """Publish initial PD control before resetting, and verify the reset via DDS.

    Upstream replaces GLFW's key callback; Space does not reliably pause this
    build. BackSpace is handled explicitly by its callback and clears mjData.
    """
    env = pipeline.env
    pipeline.reset()
    initial_target = finite_vector(pipeline.policy.get_init_dof_pos(), 29, "initial policy PD target")
    env.step(initial_target)
    time.sleep(0.15)  # Let the native recurrent writer publish before reset.
    deadline = time.monotonic() + 2
    while True:
        env.update()
        before = int(env.robot_state.tick)
        if before > 500:
            break
        if time.monotonic() > deadline:
            raise RuntimeError("Simulator was not advancing before initialization reset")
        time.sleep(0.01)
    window.key("BackSpace")
    deadline = time.monotonic() + 1
    while True:
        env.update()
        tick = int(env.robot_state.tick)
        if 0 < tick <= 250 and tick < before:
            break
        if time.monotonic() > deadline:
            raise RuntimeError("Simulator reset was not acknowledged by LowState; refusing a fallen-state trial")
        time.sleep(0.002)
    quaternion = finite_vector(env.base_quat, 4, "initial base quaternion")
    position = finite_vector(env.base_pos, 3, "initial base position")
    if np.sum(quaternion[:2] ** 2) > 0.05 or position[2] < 0.6:
        raise RuntimeError("Simulator reset produced an invalid initial upright state")
    # Pipeline dry runs observe the pre-reset world. Trackers must establish
    # heading against the fresh simulator state, independently of motion reset.
    reset_alignment = getattr(pipeline.policy, "reset_alignment", None)
    if callable(reset_alignment):
        reset_alignment()
    pipeline.do_safety_check = True
    return {
        "before_reset_tick": before,
        "initial_tick": tick,
        "initial_position": position.tolist(),
        "initial_quaternion_xyzw": quaternion.tolist(),
    }


def run_closed_loop(pipeline, args, summary: dict, log: TextIO | None, simulator=None, xserver=None):
    env = pipeline.env
    monitor = StateMonitor(args.stale_timeout)
    recorder = CommandRecorder(env, pipeline.dt)
    env.step = recorder.step
    inputs = ScriptedInputs(pipeline.ctrl_manager, args.command, args.event, args.input == "scripted")
    pipeline.ctrl_manager = inputs
    started = time.monotonic()
    inputs.time_origin = started
    deadline = started + args.duration
    timings = []
    total_timings = []
    heights = []
    tilts = []
    policy_steps = {}
    policy_first_progress = {}
    policy_last_progress = {}
    initial_controller_progress = controller_progress(inputs.manager)
    summary["steps"] = 0
    try:
        # Include time spent in an intentional inner blend in the feedback span.
        monitor.observe(env)
        index = 0
        while time.monotonic() < deadline:
            tick = time.monotonic()
            for process, name in ((simulator, "simulator"), (xserver, "Xvfb")):
                if process is not None and process.poll() is not None:
                    raise RuntimeError(f"{name} exited during policy control")
            inputs.elapsed = tick - started
            policy_before_step = pipeline.policy
            policy_name = policy_before_step.name
            progress_before_step = policy_progress(policy_before_step)
            policy_first_progress.setdefault(policy_name, progress_before_step)
            previous_action_count = recorder.count
            previous_deliveries = len(inputs.deliveries)
            pipeline.step()
            # A blend may occupy seconds inside step() while publishing targets
            # every policy period. Reject target starvation, not that outer span.
            recorder.check_gap()
            frame = monitor.observe(env)
            quaternion = np.asarray(frame["imu_quaternion_xyzw"])
            tilt = float(np.arccos(np.clip(1 - 2 * np.sum(quaternion[:2] ** 2), -1, 1)))
            height = frame["position"][2]
            policy_steps[policy_name] = policy_steps.get(policy_name, 0) + 1
            policy_last_progress[policy_name] = policy_progress(policy_before_step)
            elapsed = time.monotonic() - tick
            timings.append(elapsed)
            heights.append(height)
            tilts.append(tilt)
            summary["steps"] = index + 1
            deliveries = inputs.deliveries[previous_deliveries:]
            frame.update(
                step=index,
                policy=policy_name,
                policy_after_step=pipeline.policy.name,
                policy_progress_before=progress_before_step,
                policy_progress=policy_last_progress[policy_name],
                active_policy_progress=policy_progress(pipeline.policy),
                controller_progress=controller_progress(inputs.manager),
                command_q=None if recorder.last is None else recorder.last.tolist(),
                command_count=recorder.count - previous_action_count,
                total_action_count=recorder.count,
                max_command_gap_s=recorder.max_gap_s,
                input_axes=list(inputs.axes),
                events=[f"{event['kind']}:{event['value']}" for event in deliveries],
                event_deliveries=deliveries,
                tilt_rad=tilt,
                loop_work_s=elapsed,
                backend_enabled=env.enabled,
            )
            if log:
                log.write(json.dumps(frame, allow_nan=False) + "\n")
                log.flush()
            if not env.enabled:
                raise RuntimeError("Deployment backend disabled itself (shutdown or fall safety check)")
            if tilt > args.max_tilt or height < args.min_height:
                raise RuntimeError(f"Robot fell: pelvis height {height:.3f}m, tilt {tilt:.3f}rad")
            total_timings.append(time.monotonic() - tick)
            recorder.check_gap()  # Include state processing and JSONL flush stalls.
            # Each iteration owns its next deadline; a long controlled blend
            # must not cause a burst of compressed catch-up policy frames.
            time.sleep(max(0, min(tick + pipeline.dt, deadline) - time.monotonic()))
            index += 1
        recorder.check_gap()
        if monitor.tick_updates < 2 or recorder.count < 2:
            raise RuntimeError("Insufficient advancing feedback or policy commands")
        if inputs.cursor != len(inputs.events):
            raise RuntimeError("Run ended before all scheduled events were delivered; schedule them earlier")
        required_simulation = 0.9 * max(0, args.duration - pipeline.dt)
        if monitor.tick_elapsed / 1000.0 < required_simulation:
            raise RuntimeError(
                f"Insufficient simulated duration: {monitor.tick_elapsed / 1000.0:.3f}s, "
                f"required at least {required_simulation:.3f}s"
            )
    finally:
        recorder.command_age()
        env.step = recorder.original
        pipeline.ctrl_manager = inputs.manager
        summary.update(
            wall_duration_s=time.monotonic() - started,
            simulated_duration_s=monitor.tick_elapsed / 1000.0,
            state=monitor.report(),
            action_count=recorder.count,
            max_abs_target_rad=recorder.max_abs,
            targets_outside_configured_limits=recorder.outside_limits,
            policy_steps=policy_steps,
            policy_progress_initial=policy_first_progress,
            policy_progress=policy_last_progress,
            controller_progress_initial=initial_controller_progress,
            controller_progress=controller_progress(inputs.manager),
            events_consumed=inputs.cursor,
            event_deliveries=inputs.deliveries,
            min_height_m=min(heights, default=None),
            max_height_m=max(heights, default=None),
            max_tilt_rad=max(tilts, default=None),
            max_loop_work_s=max(timings, default=None),
            mean_loop_work_s=float(np.mean(timings)) if timings else None,
            max_loop_total_work_s=max(total_timings, default=None),
            mean_loop_total_work_s=float(np.mean(total_timings)) if total_timings else None,
            max_command_gap_s=recorder.max_gap_s,
            mean_command_gap_s=recorder.gap_sum_s / (recorder.count - 1) if recorder.count > 1 else None,
            frame_drops=recorder.late_commands,
            outer_steps_over_period=sum(value > pipeline.dt for value in timings),
        )


def run(args: argparse.Namespace, summary: dict):
    from robojudo import pipeline as pipelines

    summary["stage"] = "configuration"
    cfg = build_config(args)
    repo = args.repo.resolve()
    binary = repo / "simulate/build/unitree_mujoco"
    scene = repo / "unitree_robots/g1/scene_29dof.xml"
    if not binary.is_file() or not os.access(binary, os.X_OK) or not scene.is_file():
        raise FileNotFoundError("Official compiled simulator or G1 scene missing; see docs/unitree_mujoco.md")
    import yaml

    simulator_cfg = yaml.safe_load((repo / "simulate/config.yaml").read_text())
    if simulator_cfg.get("enable_elastic_band", 0):
        raise ValueError("Disable enable_elastic_band in the official simulator configuration before a balance trial")
    with contextlib.ExitStack() as stack:
        simulator_log = None
        if args.simulator_log:
            args.simulator_log.parent.mkdir(parents=True, exist_ok=True)
            simulator_log = stack.enter_context(args.simulator_log.open("w"))
        sample_log = None
        if args.log:
            args.log.parent.mkdir(parents=True, exist_ok=True)
            sample_log = stack.enter_context(args.log.open("w"))
        xserver = None
        display_name = os.environ.get("DISPLAY")
        if args.headless:
            display_name, xserver = stack.enter_context(virtual_display(find_xvfb(), simulator_log))
        if not display_name:
            raise RuntimeError("DISPLAY is unset; use --headless")
        old_display = os.environ.get("DISPLAY")
        os.environ["DISPLAY"] = display_name

        def restore_display():
            if old_display is None:
                os.environ.pop("DISPLAY", None)
            else:
                os.environ["DISPLAY"] = old_display

        stack.callback(restore_display)
        summary["stage"] = "simulator_start"
        simulator = subprocess.Popen(
            [str(binary), "-r", "g1", "-i", "0", "-n", "lo", "-t", "1", "-s", str(scene)],
            cwd=binary.parent,
            stdout=simulator_log,
            stderr=subprocess.STDOUT if simulator_log else None,
            start_new_session=True,
        )
        stack.callback(stop_process, simulator)
        summary.update(simulator_pid=simulator.pid, display=display_name, scene=str(scene), supported_base=False)
        window = SimulatorWindow(display_name, simulator)
        stack.callback(window.close)
        summary["stage"] = "pipeline_load"
        pipeline = getattr(pipelines, cfg.pipeline_type)(cfg=cfg)
        stack.callback(pipeline.env.shutdown)
        summary.update(pipeline=cfg.pipeline_type, joint_names=pipeline.env.joint_names)
        summary["stage"] = "simulator_reset"
        summary["initialization"] = start_control(pipeline, window)
        summary["stage"] = "closed_loop"
        try:
            run_closed_loop(pipeline, args, summary, sample_log, simulator, xserver)
        finally:
            if args.screenshot:
                try:
                    window.save_screenshot(args.screenshot)
                    summary["screenshot"] = str(args.screenshot)
                except Exception as error:
                    summary["screenshot_error"] = str(error)
        if "screenshot_error" in summary:
            raise RuntimeError(f"Screenshot failed: {summary['screenshot_error']}")
        summary["stage"] = "completed"


def request_stop(_signum, _frame):
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = {
        "config": args.config,
        "requested_duration_s": args.duration,
        "input": args.input,
        "passed": False,
        "stage": "initialization",
        "network_interface": "lo",
        "dds_domain": 0,
        "startup": "publish_initial_target_then_live_unconstrained_simulator_reset",
    }
    previous = signal.signal(signal.SIGTERM, request_stop)
    code = 1
    try:
        run(args, summary)
        summary["passed"] = True
        code = 0
    except KeyboardInterrupt:
        summary["error"] = "Interrupted"
        code = 130
    except (Exception, SystemExit) as error:
        summary["error"] = f"{type(error).__name__}: {error}"
        print(summary["error"], file=sys.stderr)
    finally:
        signal.signal(signal.SIGTERM, previous)
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
        print(json.dumps({key: value for key, value in summary.items() if key != "state"}, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
