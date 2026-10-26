"""Launch the compiled official G1 C++ simulator on loopback DDS domain 0.

Use --suspended for joint tests without a balance policy, and --headless for a
private Xvfb display. The original Unitree model and host display stay unchanged.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import select
import shutil
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TextIO

ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", type=Path, default=ROOT.parent / "unitree_mujoco", help="Official source/build checkout."
    )
    parser.add_argument("--suspended", action="store_true", help="Generate a copy with the pelvis welded at 1.2 m.")
    parser.add_argument(
        "--headless", action="store_true", help="Run the official viewer on an independent virtual display."
    )
    parser.add_argument("--log", type=Path, help="Write simulator and Xvfb output to this file.")
    return parser.parse_args(argv)


def suspended_scene(repo: Path, destination: Path) -> Path:
    """Copy the official scene, preserving SDK joint and sensor indices."""
    source = repo / "unitree_robots" / "g1"
    robot = ET.parse(source / "g1_29dof.xml")
    root = robot.getroot()
    compiler = root.find("compiler")
    pelvis = root.find("./worldbody/body[@name='pelvis']")
    if compiler is None or pelvis is None:
        raise RuntimeError("Official G1 model is missing its compiler or pelvis body")
    if pelvis.find("./joint[@type='free']") is None and pelvis.find("freejoint") is None:
        raise RuntimeError("Expected a floating pelvis joint; retaining it is required for SDK indices")
    if len(root.findall("./actuator/motor")) != 29:
        raise RuntimeError("Expected 29 motors in the official G1 model")
    compiler.set("meshdir", str((source / "meshes").resolve()))
    pelvis.set("pos", "0 0 1.2")
    equality = root.find("equality")
    if equality is None:
        equality = ET.SubElement(root, "equality")
    ET.SubElement(equality, "weld", name="test_pelvis_weld", body1="pelvis")

    scene = ET.parse(source / "scene_29dof.xml")
    include = scene.getroot().find("include[@file='g1_29dof.xml']")
    if include is None:
        raise RuntimeError("Official 29-DOF scene does not include g1_29dof.xml")
    statistic = scene.getroot().find("statistic")
    if statistic is not None:
        statistic.set("center", "0 0 1.0")
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    robot_path = destination / "g1_29dof_suspended.xml"
    scene_path = destination / "scene_29dof_suspended.xml"
    include.set("file", str(robot_path))
    robot.write(robot_path, encoding="utf-8", xml_declaration=True)
    scene.write(scene_path, encoding="utf-8", xml_declaration=True)
    return scene_path


def stop_process(process: subprocess.Popen | None) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def find_xvfb() -> Path:
    installed = shutil.which("Xvfb")
    path = Path(installed) if installed else ROOT / "build/unitree_mujoco-deps/xvfb/usr/bin/Xvfb"
    if not path.is_file() or not os.access(path, os.X_OK):
        raise RuntimeError("Xvfb is unavailable; see docs/unitree_mujoco.md for headless setup")
    return path


@contextlib.contextmanager
def virtual_display(executable: Path, log: TextIO | None = None, timeout: float = 10):
    read_fd, write_fd = os.pipe()
    process = None
    try:
        try:
            process = subprocess.Popen(
                [
                    str(executable),
                    "-displayfd",
                    str(write_fd),
                    "-screen",
                    "0",
                    "1280x800x24",
                    "-nolisten",
                    "tcp",
                    "-noreset",
                ],
                pass_fds=(write_fd,),
                stdout=log,
                stderr=subprocess.STDOUT if log else None,
                start_new_session=True,
            )
        finally:
            os.close(write_fd)
        # Xvfb chooses and announces a free display only after it is ready.
        deadline = time.monotonic() + timeout
        announcement = b""
        while b"\n" not in announcement:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([read_fd], [], [], max(0, remaining))[0]:
                raise RuntimeError("Timed out waiting for Xvfb to announce a display")
            chunk = os.read(read_fd, 128)
            if not chunk or len(announcement) + len(chunk) > 128:
                raise RuntimeError("Xvfb failed before announcing a display; inspect its output")
            announcement += chunk
        number = announcement.strip()
        if not number.isdigit() or process.poll() is not None:
            raise RuntimeError(f"Invalid Xvfb display announcement: {announcement!r}")
        display = f":{number.decode('ascii')}"
        print(f"Xvfb PID={process.pid}, DISPLAY={display}", flush=True)
        yield display, process
    finally:
        os.close(read_fd)
        stop_process(process)


def run(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    binary = repo / "simulate" / "build" / "unitree_mujoco"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"Compiled simulator not found: {binary}; build the C++ simulator first")
    scene = repo / "unitree_robots" / "g1" / "scene_29dof.xml"
    if args.suspended:
        scene = suspended_scene(repo, ROOT / "build" / "unitree_mujoco-scene")
    if not scene.is_file():
        raise RuntimeError(f"G1 scene not found: {scene}")
    with contextlib.ExitStack() as stack:
        log = None
        if args.log:
            args.log.parent.mkdir(parents=True, exist_ok=True)
            log = stack.enter_context(args.log.open("w"))
        env = os.environ.copy()
        xserver = None
        if args.headless:
            display, xserver = stack.enter_context(virtual_display(find_xvfb(), log))
            env["DISPLAY"] = display
        command = [str(binary), "-r", "g1", "-i", "0", "-n", "lo", "-t", "1", "-s", str(scene)]
        simulator = None
        try:
            simulator = subprocess.Popen(
                command,
                cwd=binary.parent,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT if log else None,
                start_new_session=True,
            )
            print(f"Simulator PID={simulator.pid}, DDS=0, interface=lo, scene={scene}", flush=True)
            while simulator.poll() is None:
                if xserver is not None and xserver.poll() is not None:
                    raise RuntimeError("Xvfb exited while the simulator was running")
                try:
                    simulator.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    pass
            return simulator.returncode
        finally:
            stop_process(simulator)


def request_stop(_signum, _frame) -> None:
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    previous = signal.signal(signal.SIGTERM, request_stop)
    try:
        return run(args)
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ET.ParseError) as error:
        print(f"Simulator launch failed: {error}", file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    raise SystemExit(main())
