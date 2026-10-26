"""Episode reset must clear inference state, including exported LSTM memory."""

import unittest
from types import SimpleNamespace

import numpy as np
import torch

from robojudo.config.g1.policy.g1_unitree_policy_cfg import G1UnitreePolicyCfg
from robojudo.policy.unitree_policy import UnitreePolicy


class UnitreePolicyResetTest(unittest.TestCase):
    def test_exported_lstm_replays_identically_after_reset(self):
        cfg = G1UnitreePolicyCfg()
        policy = UnitreePolicy(cfg, "cpu")
        observations = [np.linspace(-0.2, 0.3, 47, dtype=np.float32) + i * 0.01 for i in range(4)]
        first = [policy.get_action(obs).copy() for obs in observations]
        self.assertGreater(torch.linalg.vector_norm(policy.model.hidden_state).item(), 0)
        self.assertGreater(np.linalg.norm(policy.last_action), 0)

        policy.post_step_callback()
        policy.reset()
        self.assertEqual(policy.timestep, 0)
        np.testing.assert_array_equal(policy.last_action, np.zeros(policy.num_actions))
        self.assertEqual(torch.count_nonzero(policy.model.hidden_state).item(), 0)
        self.assertEqual(torch.count_nonzero(policy.model.cell_state).item(), 0)
        replay = [policy.get_action(obs).copy() for obs in observations]
        np.testing.assert_allclose(replay, first, atol=0, rtol=0)

    def test_feedforward_export_does_not_require_reset_memory(self):
        policy = object.__new__(UnitreePolicy)
        policy.model = SimpleNamespace()
        policy.num_actions = 3
        policy.last_action = np.ones(3)
        policy.history_length = 2
        policy.history_obs_size = 5
        policy.reset()
        np.testing.assert_array_equal(policy.last_action, np.zeros(3))
        self.assertEqual(len(policy.history_buf), 2)
        np.testing.assert_array_equal(policy.history_buf[0], np.zeros(5))


if __name__ == "__main__":
    unittest.main()
