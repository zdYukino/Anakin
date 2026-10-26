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


class ProcessTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="g1 launcher test ")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

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
