"""Small quaternion helpers for playback.

``slerp`` is adapted from PHC's NVIDIA BSD-3-Clause torch_utils.py at
f8e75fb94918140e85db9744abf1f3b7667428a1. See LICENSE-NVIDIA.
The heading helper uses the repository's existing xyzw vector rotation.
"""

import torch

from robojudo.utils.util_func_torch import quat_apply


def inverse_heading_wxyz(quaternion_xyzw):
    """Return the inverse yaw as wxyz, matching the local PHC patch."""
    forward = torch.zeros_like(quaternion_xyzw[..., :3])
    forward[..., 0] = 1
    direction = quat_apply(quaternion_xyzw, forward, w_last=True)
    half_angle = -torch.atan2(direction[..., 1], direction[..., 0]) / 2
    result = torch.zeros_like(quaternion_xyzw)
    result[..., 0] = half_angle.cos()
    result[..., 3] = half_angle.sin()
    return result / result.norm(dim=-1, keepdim=True).clamp(min=1e-9)


@torch.jit.script
def slerp(q0, q1, t):
    """PHC's shortest-path xyzw interpolation, including its close-pair rule."""
    cos_half_theta = torch.sum(q0 * q1, dim=-1)
    negative = cos_half_theta < 0
    q1 = q1.clone()
    q1[negative] = -q1[negative]
    cos_half_theta = cos_half_theta.abs().unsqueeze(-1)
    half_theta = torch.acos(cos_half_theta)
    sin_half_theta = torch.sqrt(1.0 - cos_half_theta * cos_half_theta)
    ratio_a = torch.sin((1 - t) * half_theta) / sin_half_theta
    ratio_b = torch.sin(t * half_theta) / sin_half_theta
    result = ratio_a * q0 + ratio_b * q1
    result = torch.where(sin_half_theta.abs() < 0.001, 0.5 * q0 + 0.5 * q1, result)
    return torch.where(cos_half_theta.abs() >= 1, q0, result)
