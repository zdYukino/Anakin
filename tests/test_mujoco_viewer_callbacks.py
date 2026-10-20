"""Exercise mouse callbacks with real MuJoCo objects without opening a window."""

import unittest
from unittest.mock import patch

import glfw
import mujoco
import numpy as np
from mujoco_viewer import callbacks as viewer_callbacks


class TestMujocoViewerCallbacks(unittest.TestCase):
    def setUp(self):
        self.viewer = viewer_callbacks.Callbacks(hide_menus=True)
        self.viewer.model = mujoco.MjModel.from_xml_string(
            """<mujoco><worldbody><body name="target">
            <freejoint/><geom type="sphere" size="0.5"/>
            </body></worldbody></mujoco>"""
        )
        self.viewer.data = mujoco.MjData(self.viewer.model)
        mujoco.mj_forward(self.viewer.model, self.viewer.data)
        self.viewer.cam = mujoco.MjvCamera()
        self.viewer.cam.distance = 3.0
        self.viewer.cam.azimuth = 90.0
        self.viewer.cam.elevation = -20.0
        self.viewer.scn = mujoco.MjvScene(self.viewer.model, maxgeom=10)
        self.viewer.vopt = mujoco.MjvOption()
        self.viewer.pert = mujoco.MjvPerturb()
        self.viewer.viewport = mujoco.MjrRect(0, 0, 800, 600)
        self.viewer._scale = 1.0
        self.window = object()
        mujoco.mjv_updateScene(
            self.viewer.model,
            self.viewer.data,
            self.viewer.vopt,
            self.viewer.pert,
            self.viewer.cam,
            mujoco.mjtCatBit.mjCAT_ALL,
            self.viewer.scn,
        )

    def drag(self, button, shift=False):
        self.viewer._button_left_pressed = button == glfw.MOUSE_BUTTON_LEFT
        self.viewer._button_right_pressed = button == glfw.MOUSE_BUTTON_RIGHT
        with (
            patch.object(glfw, "get_key", return_value=glfw.PRESS if shift else glfw.RELEASE),
            patch.object(glfw, "get_framebuffer_size", return_value=(800, 600)),
        ):
            self.viewer._cursor_pos_callback(self.window, 60, 30)

    def click(self, button, time_value, mods=0, action=glfw.PRESS):
        with (
            patch.object(glfw, "get_cursor_pos", return_value=(400, 300)),
            patch.object(glfw, "get_time", return_value=time_value),
        ):
            self.viewer._mouse_button_callback(self.window, button, action, mods)

    def test_drag_rotates_and_translates_camera(self):
        for button, shift in (
            (glfw.MOUSE_BUTTON_LEFT, False),
            (glfw.MOUSE_BUTTON_LEFT, True),
            (glfw.MOUSE_BUTTON_RIGHT, False),
            (glfw.MOUSE_BUTTON_RIGHT, True),
        ):
            with self.subTest(button=button, shift=shift):
                self.viewer._last_mouse_x = 0
                self.viewer._last_mouse_y = 0
                angles = (self.viewer.cam.azimuth, self.viewer.cam.elevation)
                lookat = self.viewer.cam.lookat.copy()
                self.drag(button, shift)
                if button == glfw.MOUSE_BUTTON_LEFT:
                    self.assertNotEqual(angles, (self.viewer.cam.azimuth, self.viewer.cam.elevation))
                else:
                    self.assertFalse(np.array_equal(lookat, self.viewer.cam.lookat))
                self.assertEqual((self.viewer._last_mouse_x, self.viewer._last_mouse_y), (60, 30))

    def test_scroll_zooms_camera(self):
        distance = self.viewer.cam.distance
        self.viewer._scroll_callback(self.window, 0, 1)
        self.assertGreater(self.viewer.cam.distance, distance)
        zoomed_distance = self.viewer.cam.distance
        self.viewer._scroll_callback(self.window, 0, -1)
        self.assertLess(self.viewer.cam.distance, zoomed_distance)

    def test_pre_3_11_camera_signature_for_drag_and_scroll(self):
        native_move_camera = mujoco.mjv_moveCamera

        # The installed binding is current; emulate the legacy six-argument
        # boundary while still performing the camera movement with MuJoCo.
        def legacy_move_camera(model, action, reldx, reldy, scene, camera):
            self.assertIs(scene, self.viewer.scn)
            native_move_camera(model, action, reldx, reldy, camera)

        with (
            patch.object(viewer_callbacks, "MUJOCO_VERSION", (3, 10, 0)),
            patch.object(mujoco, "mjv_moveCamera", side_effect=legacy_move_camera) as move_camera,
        ):
            self.drag(glfw.MOUSE_BUTTON_LEFT)
            self.viewer._scroll_callback(self.window, 0, 1)
        self.assertEqual(move_camera.call_count, 2)
        self.assertNotEqual(self.viewer.cam.elevation, -20.0)
        self.assertGreater(self.viewer.cam.distance, 3.0)

    def test_3_11_camera_signature_boundary(self):
        with patch.object(viewer_callbacks, "MUJOCO_VERSION", (3, 11, 0)):
            self.drag(glfw.MOUSE_BUTTON_LEFT)
            self.viewer._scroll_callback(self.window, 0, 1)
        self.assertNotEqual(self.viewer.cam.elevation, -20.0)
        self.assertGreater(self.viewer.cam.distance, 3.0)

    def test_double_click_selects_body(self):
        self.click(glfw.MOUSE_BUTTON_LEFT, 1.0)
        self.click(glfw.MOUSE_BUTTON_LEFT, 1.1)
        self.assertEqual(self.viewer.pert.select, 1)
        self.assertEqual(self.viewer.pert.skinselect, -1)
        self.assertTrue(np.isfinite(self.viewer.pert.localpos).all())

    def test_control_drag_perturbs_selected_body_and_release_stops_it(self):
        for button, perturbation in (
            (glfw.MOUSE_BUTTON_LEFT, mujoco.mjtPertBit.mjPERT_ROTATE),
            (glfw.MOUSE_BUTTON_RIGHT, mujoco.mjtPertBit.mjPERT_TRANSLATE),
        ):
            with self.subTest(button=button):
                self.viewer.pert.select = 1
                self.click(button, 2.0, mods=glfw.MOD_CONTROL)
                self.assertEqual(self.viewer.pert.active, perturbation)
                refpos = self.viewer.pert.refpos.copy()
                refquat = self.viewer.pert.refquat.copy()
                self.drag(button)
                self.assertTrue(
                    not np.array_equal(refpos, self.viewer.pert.refpos)
                    or not np.array_equal(refquat, self.viewer.pert.refquat)
                )
                self.click(button, 2.1, action=glfw.RELEASE)
                self.assertEqual(self.viewer.pert.active, 0)


if __name__ == "__main__":
    unittest.main()
