"""Playback resume must retain active balance while reaching real callbacks."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from box import Box

from robojudo.controller.beyondmimic_ctrl import BeyondMimicCtrl
from robojudo.controller.ctrl_manager import CtrlManager
from robojudo.pipeline.rl_pipeline import RlPipeline


class FeedbackEnv:
    def __init__(self):
        self.targets = []

    def update(self):
        pass

    def get_data(self):
        return Box()

    def step(self, target, hand_pose=None):
        self.targets.append(np.asarray(target).copy())


class ReferenceManager(CtrlManager):
    """Use real manager dispatch and real BeyondMimic playback state changes."""

    def __init__(self, commands):
        super().__init__(cfg_ctrls=[])
        self.commands = list(commands)
        reference = object.__new__(BeyondMimicCtrl)
        reference.cfg_ctrl = SimpleNamespace(motion_name="test")
        reference.motion = SimpleNamespace(
            time_step_total=100,
            body_pos_w=np.zeros((100, 1, 3)),
            body_quat_w=np.tile([1.0, 0.0, 0.0, 0.0], (100, 1, 1)),
        )
        reference.motion_anchor_body_index = 0
        reference.motion_init_align = SimpleNamespace(set_base=Mock())
        reference.timestep = 0
        reference.playing = False
        reference.pbar = Mock()
        self.reference = reference
        self.controllers = Box({"BeyondMimicCtrl": {"inst": reference}})

    def get_ctrl_data(self, env_data):
        commands = self.commands.pop(0) if self.commands else []
        return Box(COMMANDS=commands, reference_frame=self.reference.timestep)


class BalancingPolicy:
    def __init__(self):
        self.commands = []

    def get_observation(self, env_data, ctrl_data):
        return ctrl_data.reference_frame, {}

    def get_pd_target(self, observation):
        return np.array([0.4, 0.5]) + observation * 0.01

    def post_step_callback(self, commands):
        self.commands.append(list(commands))


class TrackerPolicy(BalancingPolicy):
    def __init__(self):
        super().__init__()
        self.default_pose_modes = []

    def set_default_pose_mode(self, enabled):
        self.default_pose_modes.append(enabled)


def pipeline_for(commands, *, blending_out=False, tracker=False):
    pipeline = object.__new__(RlPipeline)
    pipeline.env = FeedbackEnv()
    pipeline.ctrl_manager = ReferenceManager(commands)
    pipeline.policy = TrackerPolicy() if tracker else BalancingPolicy()
    pipeline.cfg = SimpleNamespace(debug=SimpleNamespace(log_obs=False))
    pipeline.visualizer = None
    pipeline.timestep = 0
    pipeline.do_safety_check = False
    pipeline._blend_out_active = blending_out
    pipeline._blend_out_step = 0
    pipeline._blend_out_duration = 250
    pipeline._init_dof_pos = np.zeros(2)
    pipeline._pending_blend_in = False
    pipeline._blend_in_completed = False
    pipeline._user_fade_out = blending_out
    pipeline._run_blend_in = Mock()
    return pipeline


class MotionResumeTest(unittest.TestCase):
    def setUp(self):
        progress = patch("robojudo.controller.beyondmimic_ctrl.ProgressBar", return_value=Mock())
        progress.start()
        self.addCleanup(progress.stop)

    def test_active_resume_keeps_balance_and_advances_actual_reference(self):
        pipeline = pipeline_for([["[MOTION_FADE_IN]"]])
        pipeline.step()
        pipeline.step()
        pipeline.step()

        pipeline._run_blend_in.assert_not_called()
        self.assertFalse(pipeline._pending_blend_in)
        self.assertTrue(pipeline.ctrl_manager.reference.playing)
        self.assertEqual(pipeline.ctrl_manager.reference.timestep, 2)
        self.assertEqual(pipeline.policy.commands[0], ["[MOTION_FADE_IN]"])
        np.testing.assert_allclose(pipeline.env.targets, [[0.4, 0.5], [0.4, 0.5], [0.41, 0.51]])

    def test_paused_reference_stays_paused_without_resume(self):
        pipeline = pipeline_for([])
        pipeline.step()
        pipeline.step()
        self.assertFalse(pipeline.ctrl_manager.reference.playing)
        self.assertEqual(pipeline.ctrl_manager.reference.timestep, 0)
        np.testing.assert_allclose(pipeline.env.targets, [[0.4, 0.5], [0.4, 0.5]])

    def test_motion_reset_keeps_legacy_blend_and_reference_reset(self):
        pipeline = pipeline_for([["[MOTION_RESET]"]])
        pipeline.ctrl_manager.reference.timestep = 8
        pipeline.step()
        pipeline._run_blend_in.assert_called_once_with()
        self.assertTrue(pipeline._blend_in_completed)
        self.assertEqual(pipeline.ctrl_manager.reference.timestep, 0)
        self.assertEqual(pipeline.policy.commands[0], ["[MOTION_RESET]"])

    def test_resume_after_actual_blend_out_keeps_legacy_blend(self):
        pipeline = pipeline_for([["[MOTION_FADE_IN]"]], blending_out=True)
        pipeline.step()
        pipeline._run_blend_in.assert_called_once_with()
        self.assertFalse(pipeline._blend_out_active)
        self.assertFalse(pipeline._user_fade_out)
        self.assertTrue(pipeline.ctrl_manager.reference.playing)

    def test_tracker_resume_uses_existing_default_pose_switch(self):
        pipeline = pipeline_for([["[MOTION_FADE_IN]"]], tracker=True)
        pipeline.step()
        pipeline._run_blend_in.assert_not_called()
        self.assertEqual(pipeline.policy.default_pose_modes, [False])
        self.assertTrue(pipeline.ctrl_manager.reference.playing)

    def test_tracker_reset_retains_existing_default_pose_switch(self):
        pipeline = pipeline_for([["[MOTION_RESET]"]], tracker=True)
        pipeline.step()
        pipeline._run_blend_in.assert_not_called()
        self.assertEqual(pipeline.policy.default_pose_modes, [False])


if __name__ == "__main__":
    unittest.main()
