"""Exercise the official C++ G1 simulator through Anakin's real-robot backend.

Run with the project's Python environment. The simulator must use DDS domain 0
and interface lo. Read mode is passive, including on exit. Joint mode expects a
suspended/pelvis-constrained 29-DOF G1; it does not implement balance control.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO

import numpy as np


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("read", "joints"), default="read")
    parser.add_argument("--duration", type=float, default=5.0, help="Read-mode duration in seconds (0.2 to 600).")
    parser.add_argument("--rate", type=float, default=100.0, help="State polling and command rate in Hz (20 to 200).")
    parser.add_argument(
        "--stale-timeout", type=float, default=1.0, help="Fail if the state tick stops for this many seconds."
    )
    parser.add_argument("--amplitude", type=float, default=0.08, help="Joint excursion in radians (0.01 to 0.15).")
    parser.add_argument(
        "--joint-duration", type=float, default=3.0, help="Seconds for each positive/negative joint cycle."
    )
    parser.add_argument(
        "--ramp-duration", type=float, default=3.0, help="Seconds to ramp from measured to default pose."
    )
    parser.add_argument("--settle-duration", type=float, default=0.5, help="Default-pose hold before each joint cycle.")
    parser.add_argument("--summary", type=Path, help="Also write the final JSON report to this file.")
    parser.add_argument("--log", type=Path, help="Write per-sample feedback and commands as JSONL.")
    args = parser.parse_args(argv)
    bounds = {
        "duration": (0.2, 600),
        "rate": (20, 200),
        "stale_timeout": (0.1, 10),
        "amplitude": (0.01, 0.15),
        "joint_duration": (2, 10),
        "ramp_duration": (1, 30),
        "settle_duration": (0.2, 5),
    }
    for name, (minimum, maximum) in bounds.items():
        value = getattr(args, name)
        if not math.isfinite(value) or not minimum <= value <= maximum:
            parser.error(f"--{name.replace('_', '-')} must be between {minimum} and {maximum}")
    if args.summary and args.log and args.summary.resolve() == args.log.resolve():
        parser.error("--summary and --log must be different files")
    return args


def make_env(args: argparse.Namespace):
    # Import only the real configuration/backend: no pipeline, policy or SDK shim.
    from robojudo.config.g1.env.g1_real_env_cfg import G1RealEnvCfg
    from robojudo.environment.unitree_cpp_env import UnitreeCppEnv

    cfg = G1RealEnvCfg()
    cfg.act = args.mode == "joints"
    cfg.unitree.net_if = "lo"
    cfg.unitree.control_dt = 1.0 / args.rate
    cfg.born_place_align = False
    cfg.forward_kinematic = None
    cfg.update_with_fk = False
    # Keep the simulator's rt/sportmodestate feedback in the real backend path.
    cfg.odometry_type = "UNITREE"
    cfg.unitree.enable_odometry = True
    cfg.unitree.sport_state_topic = "rt/sportmodestate"
    return UnitreeCppEnv(cfg_env=cfg)


def finite_vector(value: Any, size: int, name: str) -> np.ndarray:
    vector = np.asarray(value, dtype=float)
    if vector.shape != (size,) or not np.isfinite(vector).all():
        raise RuntimeError(f"Invalid {name}: expected {size} finite values")
    return vector


class StateMonitor:
    """Validate complete backend snapshots and advancing uint32 DDS ticks."""

    def __init__(self, stale_timeout: float):
        self.stale_timeout = stale_timeout
        self.started = time.monotonic()
        self.last_progress = self.started
        self.first: dict | None = None
        self.last: dict | None = None
        self.samples = 0
        self.tick_updates = 0
        self.tick_elapsed = 0
        self.q_min = np.full(29, np.inf)
        self.q_max = np.full(29, -np.inf)
        self.max_abs_dq = np.zeros(29)
        self.max_abs_tau = np.zeros(29)

    def observe(self, env, now: float | None = None) -> dict:
        env.update()
        now = time.monotonic() if now is None else now
        state = env.robot_state
        tick = int(state.tick)
        if tick <= 0 or tick > 0xFFFFFFFF:
            raise RuntimeError(f"Invalid/missing LowState tick: {tick}")
        q = finite_vector(env.dof_pos, 29, "motor.q")
        dq = finite_vector(env.dof_vel, 29, "motor.dq")
        tau = finite_vector(state.motor_state.tau_est, 29, "motor.tau_est")
        quat = finite_vector(env.base_quat, 4, "IMU quaternion (xyzw)")
        if abs(float(np.linalg.norm(quat)) - 1) > 0.05:
            raise RuntimeError("IMU quaternion is not a unit quaternion")
        frame = {
            "time_s": now - self.started,
            "tick": tick,
            "q": q.tolist(),
            "dq": dq.tolist(),
            "tau_est": tau.tolist(),
            "imu_quaternion_xyzw": quat.tolist(),
            "imu_gyroscope": finite_vector(env.base_ang_vel, 3, "IMU gyroscope").tolist(),
            "imu_accelerometer": finite_vector(state.imu_state.accelerometer, 3, "IMU accelerometer").tolist(),
            "imu_rpy": finite_vector(state.imu_state.rpy, 3, "IMU rpy").tolist(),
            "position": finite_vector(env.base_pos, 3, "odometry position").tolist(),
            "velocity_body": finite_vector(env.base_lin_vel, 3, "odometry velocity").tolist(),
        }
        if self.last is not None:
            advance = (tick - self.last["tick"]) & 0xFFFFFFFF
            if advance >= 0x80000000:
                raise RuntimeError("LowState tick went backwards; simulator reset or multiple publishers")
            if advance:
                self.tick_updates += 1
                self.tick_elapsed += advance
                self.last_progress = now
            elif now - self.last_progress >= self.stale_timeout:
                raise RuntimeError(f"LowState is stale: tick {tick} unchanged for {now - self.last_progress:.2f}s")
        else:
            self.first = frame
            self.last_progress = now
        self.samples += 1
        self.q_min = np.minimum(self.q_min, q)
        self.q_max = np.maximum(self.q_max, q)
        self.max_abs_dq = np.maximum(self.max_abs_dq, np.abs(dq))
        self.max_abs_tau = np.maximum(self.max_abs_tau, np.abs(tau))
        self.last = frame
        return frame

    def report(self) -> dict:
        if self.last is None:
            return {"samples": 0, "tick_updates": 0}
        return {
            "samples": self.samples,
            "tick_updates": self.tick_updates,
            "tick_elapsed": self.tick_elapsed,
            "q_min": self.q_min.tolist(),
            "q_max": self.q_max.tolist(),
            "max_abs_dq": self.max_abs_dq.tolist(),
            "max_abs_tau_est": self.max_abs_tau.tolist(),
            "first": self.first,
            "last": self.last,
        }


def smoothstep(fraction: float) -> float:
    x = float(np.clip(fraction, 0, 1))
    return x * x * x * (10 + x * (-15 + 6 * x))


def excursion(fraction: float) -> float:
    """Smooth 0 -> +1 (hold) -> -1 (hold) -> 0."""
    if fraction < 0.2:
        return smoothstep(fraction / 0.2)
    if fraction < 0.3:
        return 1.0
    if fraction < 0.7:
        return 1.0 - 2.0 * smoothstep((fraction - 0.3) / 0.4)
    if fraction < 0.8:
        return -1.0
    return -1.0 + smoothstep((fraction - 0.8) / 0.2)


def evaluate_response(commands: np.ndarray, measured: np.ndarray, amplitude: float) -> dict:
    """Require motion matching the active command, rejecting drift and reversed wiring."""
    if len(commands) < 20 or measured.shape != commands.shape or not np.isfinite(measured).all():
        raise RuntimeError("Insufficient or invalid joint-response samples")
    positive = commands >= amplitude * 0.99
    negative = commands <= -amplitude * 0.99
    if not positive.any() or not negative.any():
        raise RuntimeError("Joint cycle did not sample both hold phases")
    measured_span = float(np.percentile(measured, 95) - np.percentile(measured, 5))
    response = float((np.mean(measured[positive]) - np.mean(measured[negative])) / 2)
    edge_samples = max(1, len(measured) // 20)
    return_offset = float(np.mean(measured[-edge_samples:]) - np.mean(measured[:edge_samples]))
    correlation = float(np.corrcoef(commands, measured)[0, 1]) if np.std(measured) > 1e-7 else 0.0
    gain = float(
        np.dot(commands - commands.mean(), measured - measured.mean()) / np.sum((commands - commands.mean()) ** 2)
    )
    return {
        "amplitude_rad": amplitude,
        "measured_span_rad": measured_span,
        "signed_response_rad": response,
        "correlation": correlation,
        "response_gain": gain,
        "return_offset_rad": return_offset,
        "relative_tracking_rmse_rad": float(np.sqrt(np.mean((measured - measured.mean() - commands) ** 2))),
        "passed": bool(
            correlation >= 0.6
            and response >= 0.4 * amplitude
            and measured_span >= 0.8 * amplitude
            and abs(return_offset) <= 0.6 * amplitude
        ),
    }


def run_phase(
    env,
    monitor: StateMonitor,
    args: argparse.Namespace,
    duration: float,
    phase: str,
    log: TextIO | None,
    target: Callable[[float], np.ndarray] | None = None,
    joint_index: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    started = time.monotonic()
    deadline = started
    commands, measured = [], []
    while True:
        now = time.monotonic()
        elapsed = now - started
        if elapsed >= duration:
            break
        q_target = target(elapsed / duration) if target else None
        if q_target is not None:
            if not env.enabled:
                raise RuntimeError("Joint commands requested while backend is disabled")
            finite_vector(q_target, 29, "joint target")
            if np.any(q_target < env.position_limits[:, 0]) or np.any(q_target > env.position_limits[:, 1]):
                raise RuntimeError("Command exceeds configured joint limits")
            env.step(q_target)
        frame = monitor.observe(env)
        if log:
            log.write(json.dumps({**frame, "phase": phase, "command_q": q_target.tolist() if target else None}) + "\n")
        if joint_index is not None:
            commands.append(q_target[joint_index] - env.default_pos[joint_index])
            measured.append(frame["q"][joint_index])
        deadline += 1.0 / args.rate
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        else:
            deadline = time.monotonic()
    return np.asarray(commands), np.asarray(measured)


def run(args: argparse.Namespace, summary: dict, log: TextIO | None) -> None:
    env = None
    monitor = StateMonitor(args.stale_timeout)
    try:
        # The native constructor performs its own bounded DDS self-check and can
        # call exit() on failure. main() converts that SystemExit into a failure.
        env = make_env(args)
        if env.num_dofs != 29 or env.cfg_env.joint2motor_idx is not None:
            raise RuntimeError("Expected the standard direct G1 29-DOF SDK joint order")
        summary["joint_names"] = env.joint_names
        monitor.observe(env)
        if args.mode == "read":
            run_phase(env, monitor, args, args.duration, "read", log)
        else:
            neutral = finite_vector(env.default_pos, 29, "configured default pose")
            initial = np.asarray(monitor.last["q"])
            lower, upper = env.position_limits.T
            if np.any(initial < lower - 0.1) or np.any(initial > upper + 0.1):
                raise RuntimeError("Initial joint positions are outside configured limits")
            initial = np.clip(initial, lower, upper)
            amplitudes = np.minimum(args.amplitude, np.minimum(neutral - lower, upper - neutral) - 0.005)
            if np.any(amplitudes < 0.01):
                raise RuntimeError("Configured default pose leaves insufficient joint-limit margin")
            summary["default_pose"] = neutral.tolist()
            summary["stiffness"] = env.stiffness.tolist()
            summary["damping"] = env.damping.tolist()
            run_phase(
                env,
                monitor,
                args,
                args.ramp_duration,
                "ramp_to_default",
                log,
                lambda t: initial + smoothstep(t) * (neutral - initial),
            )
            summary["joints"] = []
            for index, name in enumerate(env.joint_names):
                run_phase(env, monitor, args, args.settle_duration, f"settle:{name}", log, lambda _: neutral)
                amplitude = float(amplitudes[index])

                def target(t: float, index=index, amplitude=amplitude) -> np.ndarray:
                    q = neutral.copy()
                    q[index] += amplitude * excursion(t)
                    return q

                commands, measured = run_phase(
                    env, monitor, args, args.joint_duration, name, log, target, joint_index=index
                )
                result = {"index": index, "name": name, **evaluate_response(commands, measured, amplitude)}
                summary["joints"].append(result)
                print(
                    f"[{index + 1:02}/29] {name}: {'PASS' if result['passed'] else 'FAIL'} "
                    f"response={result['signed_response_rad']:.4f}rad corr={result['correlation']:.3f}",
                    file=sys.stderr,
                    flush=True,
                )
            run_phase(env, monitor, args, args.settle_duration, "return_to_default", log, lambda _: neutral)
            failures = [result["name"] for result in summary["joints"] if not result["passed"]]
            if failures:
                raise RuntimeError(f"Joint response failed: {', '.join(failures)}")
        if monitor.tick_updates < 2:
            raise RuntimeError("Insufficient advancing LowState ticks")
    finally:
        summary["state"] = monitor.report()
        # shutdown() sends a damping command in the native backend. A passive
        # reader must never call it, even when feedback fails validation.
        if env is not None and args.mode == "joints":
            env.shutdown()
            time.sleep(0.05)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = {
        "status": "failed",
        "mode": args.mode,
        "backend": "G1RealEnvCfg / UnitreeCppEnv",
        "network_interface": "lo",
        "dds_domain": 0,
        "rate_hz": args.rate,
        "control_dt": 1 / args.rate,
        "commands_enabled": args.mode == "joints",
    }
    log = None
    exit_code = 1
    try:
        if args.log:
            args.log.parent.mkdir(parents=True, exist_ok=True)
            log = args.log.open("w")
        run(args, summary, log)
        summary["status"] = "passed"
        exit_code = 0
    except SystemExit as error:
        summary["error"] = f"UnitreeCppEnv initialization aborted (exit={error.code}); check simulator DDS state/CRC"
    except KeyboardInterrupt:
        summary["error"] = "Interrupted"
        exit_code = 130
    except Exception as error:
        summary["error"] = f"{type(error).__name__}: {error}"
    finally:
        if log:
            log.close()
        report = json.dumps(summary, indent=2, allow_nan=False)
        if args.summary:
            args.summary.parent.mkdir(parents=True, exist_ok=True)
            args.summary.write_text(report + "\n")
        print(report, flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
