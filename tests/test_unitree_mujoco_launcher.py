"""Scene invariants and real subprocess cleanup without starting DDS or a GUI."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts import run_unitree_mujoco as launcher


def executable(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!{sys.executable}\n{body}\n")
    path.chmod(0o755)
    return path


def fixture_repo(path: Path) -> Path:
    source = path / "unitree_robots/g1"
    (source / "meshes").mkdir(parents=True)
    root = ET.Element("mujoco", model="g1_29dof")
    ET.SubElement(root, "compiler", angle="radian", meshdir="meshes")
    body = ET.SubElement(ET.SubElement(root, "worldbody"), "body", name="pelvis", pos="0 0 0.793")
    ET.SubElement(body, "joint", name="floating_base_joint", type="free")
    actuator = ET.SubElement(root, "actuator")
    sensor = ET.SubElement(root, "sensor")
    for index in range(29):
        child = ET.SubElement(body, "body", name=f"link_{index}")
        ET.SubElement(child, "joint", name=f"joint_{index}", range="-1 1")
        ET.SubElement(actuator, "motor", name=f"motor_{index}", joint=f"joint_{index}")
    for kind in ("jointpos", "jointvel", "jointactuatorfrc"):
        for index in range(29):
            ET.SubElement(sensor, kind, name=f"{kind}_{index}", joint=f"joint_{index}")
    ET.SubElement(sensor, "framequat", name="imu_quat", objtype="site", objname="imu")
    ET.SubElement(sensor, "gyro", name="imu_gyro", site="imu")
    ET.SubElement(sensor, "accelerometer", name="imu_acc", site="imu")
    ET.ElementTree(root).write(source / "g1_29dof.xml")
    scene = ET.Element("mujoco", model="g1_29dof scene")
    ET.SubElement(scene, "include", file="g1_29dof.xml")
    ET.SubElement(scene, "statistic", center="0 0 0.5", extent="2.0")
    ET.SubElement(ET.SubElement(scene, "worldbody"), "geom", name="floor", type="plane")
    ET.ElementTree(scene).write(source / "scene_29dof.xml")
    return source


class SceneTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="g1 scene test ")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.repo = self.directory / "official"
        self.source = fixture_repo(self.repo)

    def test_suspension_preserves_source_joint_actuator_and_sensor_order(self):
        robot_source = self.source / "g1_29dof.xml"
        scene_source = self.source / "scene_29dof.xml"
        before_robot, before_scene = robot_source.read_bytes(), scene_source.read_bytes()
        original = ET.fromstring(before_robot)
        result = launcher.suspended_scene(self.repo, self.directory / "generated")
        self.assertEqual(result.name, "scene_29dof_suspended.xml")
        copied_path = Path(ET.parse(result).getroot().find("include").get("file"))
        copied = ET.parse(copied_path).getroot()
        self.assertTrue(copied_path.is_absolute())
        self.assertEqual(robot_source.read_bytes(), before_robot)
        self.assertEqual(scene_source.read_bytes(), before_scene)
        self.assertEqual(len(copied.findall("./actuator/motor")), 29)
        for section in ("actuator", "sensor"):
            self.assertEqual(ET.tostring(copied.find(section)), ET.tostring(original.find(section)))
        original_joints = [node.attrib for node in original.findall("./worldbody//joint")]
        copied_joints = [node.attrib for node in copied.findall("./worldbody//joint")]
        self.assertEqual(copied_joints, original_joints)
        pelvis = copied.find("./worldbody/body[@name='pelvis']")
        self.assertEqual(pelvis.get("pos"), "0 0 1.2")
        self.assertIsNotNone(pelvis.find("./joint[@type='free']"))
        self.assertEqual(copied.find("./equality/weld").get("body1"), "pelvis")
        self.assertEqual(copied.find("compiler").get("meshdir"), str((self.source / "meshes").resolve()))
        self.assertEqual(ET.parse(result).getroot().find("statistic").get("center"), "0 0 1.0")

    def test_missing_free_joint_is_rejected(self):
        robot_path = self.source / "g1_29dof.xml"
        robot = ET.parse(robot_path)
        pelvis = robot.getroot().find("./worldbody/body")
        pelvis.remove(pelvis.find("joint"))
        robot.write(robot_path)
        with self.assertRaisesRegex(RuntimeError, "floating pelvis"):
            launcher.suspended_scene(self.repo, self.directory / "generated")

    def test_wrong_motor_count_is_rejected(self):
        robot_path = self.source / "g1_29dof.xml"
        robot = ET.parse(robot_path)
        actuator = robot.getroot().find("actuator")
        actuator.remove(actuator.find("motor"))
        robot.write(robot_path)
        with self.assertRaisesRegex(RuntimeError, "29 motors"):
            launcher.suspended_scene(self.repo, self.directory / "generated")


class ProcessTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="g1 launcher test ")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def test_private_display_stops_on_error_and_does_not_mutate_host_display(self):
        stub = executable(
            self.directory / "Xvfb",
            "import os, sys, time\n"
            "fd = int(sys.argv[sys.argv.index('-displayfd') + 1])\n"
            "os.write(fd, b'107\\n')\n"
            "os.close(fd)\n"
            "time.sleep(30)",
        )
        old_display = os.environ.get("DISPLAY")
        with self.assertRaisesRegex(RuntimeError, "test failure"), contextlib.redirect_stdout(io.StringIO()):
            with launcher.virtual_display(stub) as (display, child):
                self.assertEqual(display, ":107")
                self.assertIsNone(child.poll())
                raise RuntimeError("test failure")
        self.assertIsNotNone(child.poll())
        self.assertEqual(os.environ.get("DISPLAY"), old_display)

    def test_simulator_uses_fixed_g1_loopback_hg_arguments(self):
        repo = self.directory / "official"
        fixture_repo(repo)
        recorded = self.directory / "arguments.json"
        executable(
            repo / "simulate/build/unitree_mujoco",
            f"import json, sys\nfrom pathlib import Path\nPath({str(recorded)!r}).write_text(json.dumps(sys.argv[1:]))",
        )
        args = launcher.parse_args(["--repo", str(repo), "--log", str(self.directory / "simulator.log")])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(launcher.run(args), 0)
        arguments = json.loads(recorded.read_text())
        self.assertEqual(arguments[:8], ["-r", "g1", "-i", "0", "-n", "lo", "-t", "1"])
        self.assertEqual(arguments[8:], ["-s", str(repo / "unitree_robots/g1/scene_29dof.xml")])

    def test_sigterm_cleans_up_simulator_and_xvfb(self):
        repo = self.directory / "official"
        fixture_repo(repo)
        sim_pid = self.directory / "sim.pid"
        xvfb_pid = self.directory / "xvfb.pid"
        executable(
            repo / "simulate/build/unitree_mujoco",
            "import os, time\nfrom pathlib import Path\n"
            f"Path({str(sim_pid)!r}).write_text(str(os.getpid()))\n"
            "time.sleep(30)",
        )
        executable(
            self.directory / "Xvfb",
            "import os, sys, time\nfrom pathlib import Path\n"
            f"Path({str(xvfb_pid)!r}).write_text(str(os.getpid()))\n"
            "fd = int(sys.argv[sys.argv.index('-displayfd') + 1])\n"
            "os.write(fd, b'108\\n')\nos.close(fd)\ntime.sleep(30)",
        )
        env = {**os.environ, "PATH": str(self.directory) + os.pathsep + os.environ.get("PATH", "")}
        process = subprocess.Popen(
            [sys.executable, str(Path(launcher.__file__)), "--repo", str(repo), "--headless"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            deadline = time.monotonic() + 5
            while not sim_pid.is_file() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(sim_pid.is_file())
            process.terminate()
            output, _ = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 130, output)
            for path in (sim_pid, xvfb_pid):
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(path.read_text()), 0)
        finally:
            launcher.stop_process(process)
            if process.stdout:
                process.stdout.close()


if __name__ == "__main__":
    unittest.main()
