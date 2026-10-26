"""Robot FK and reference velocities for the bounded PHC playback runtime.

The FK/velocity path is adapted from PHC's torch_humanoid_batch.py at
f8e75fb94918140e85db9744abf1f3b7667428a1. See SOURCE.md and LICENSE-PHC.
The stdlib MJCF parser and quaternion velocity arithmetic are local code;
no external poselib implementation is included.
"""

from types import SimpleNamespace
from xml.etree import ElementTree

import numpy as np
import torch
from scipy.ndimage import gaussian_filter1d

from ._transforms import axis_angle_to_quaternion, matrix_to_quaternion, quaternion_to_matrix


class HumanoidBatch:
    """Forward kinematics for the single-axis Unitree motion skeletons."""

    def __init__(self, cfg, device="cpu"):
        self.cfg = cfg
        self.mjcf_file = cfg["asset"]["assetFileName"]
        tree = ElementTree.parse(self.mjcf_file).getroot()
        root = tree.find("worldbody/body")
        if root is None:
            raise ValueError(f"MJCF {self.mjcf_file} has no root body under worldbody")
        self.num_dof = len(tree.findall("actuator/*"))
        if not self.num_dof:
            raise ValueError(f"MJCF {self.mjcf_file} has no actuators")

        # Preorder is the pose_aa body order. Parse only explicit kinematic
        # properties; geoms and mesh services do not participate in playback.
        names, parents, offsets, rotations, actuated, ranges = [], [], [], [], [], []
        pending = [(root, -1)]
        while pending:
            body, parent = pending.pop()
            index = len(names)
            name = body.get("name")
            if not name or name in names:
                raise ValueError(f"MJCF {self.mjcf_file} must give each body a unique name")
            names.append(name)
            parents.append(parent)
            offsets.append(self._vector(body.get("pos", "0 0 0"), 3, name))
            rotations.append(self._vector(body.get("quat", "1 0 0 0"), 4, name))
            joints = body.findall("joint")
            if joints:
                actuated.append(index)
            # The old H1 assets can express the free root as six joints.
            for joint in joints[6:] if len(joints) == 6 else joints:
                if joint.get("range") is not None:
                    ranges.append(self._vector(joint.get("range"), 2, name))
                elif joint.get("type") != "free":
                    ranges.append([-np.pi, np.pi])
            pending.extend((child, index) for child in reversed(body.findall("body")))
        if len(ranges) != self.num_dof:
            raise ValueError(f"MJCF {self.mjcf_file} has {len(ranges)} joint ranges but {self.num_dof} actuators")
        self.body_names = names
        self.num_bodies = len(names)
        self.actuated_joints_idx = np.asarray(actuated, dtype=np.int64)
        self.body_names_augment = names.copy()
        self.extend_config = cfg.get("extend_config", [])
        for extension in self.extend_config:
            self.body_names_augment.append(extension["joint_name"])
            parents.append(names.index(extension["parent_name"]))
            offsets.append(extension["pos"])
            rotations.append(extension["rot"])
        self.num_bodies_augment = len(parents)
        self.num_extend_dof = self.num_dof + len(self.extend_config)
        self._parents = tuple(parents)
        self._offsets = torch.tensor(np.asarray(offsets), dtype=torch.float32, device=device)[None]
        self._local_rotation = torch.tensor(np.asarray(rotations), dtype=torch.float32, device=device)[None]
        self._local_rotation_mat = quaternion_to_matrix(self._local_rotation)
        self.joints_range = torch.tensor(np.asarray(ranges), device=device)

    @staticmethod
    def _vector(value, size, body):
        vector = np.fromstring(value, sep=" ")
        if vector.shape != (size,) or not np.isfinite(vector).all():
            raise ValueError(f"Invalid {size}-component MJCF vector on body {body}: {value!r}")
        return vector

    def fk_batch(self, pose, trans, convert_to_mat=True, return_full=False, dt=1 / 30):
        """Evaluate batched axis-angle poses, preserving PHC's body order.

        Fitted motions may contain extra pose nodes. As in the old runtime,
        only the configured base and extension nodes participate in FK.
        """
        if not convert_to_mat:
            raise NotImplementedError("Motion playback requires axis-angle poses (convert_to_mat=True)")
        if pose.ndim != 4 or pose.shape[-1] != 3 or pose.shape[2] < self.num_bodies_augment:
            raise ValueError(
                f"pose_aa must have shape (batch, frames, at least {self.num_bodies_augment}, 3), "
                f"got {tuple(pose.shape)}"
            )
        if trans.shape != (*pose.shape[:2], 3):
            raise ValueError(f"Root translations must have shape {(*pose.shape[:2], 3)}, got {tuple(trans.shape)}")
        if return_full and pose.shape[1] < 3:
            raise ValueError("PHC playback velocity calculation requires at least three motion frames")
        pose = pose[..., : self.num_bodies_augment, :]
        pose_quat = axis_angle_to_quaternion(pose)
        pose_mat = quaternion_to_matrix(pose_quat)
        wbody_pos, wbody_mat = self.forward_kinematics_batch(pose_mat[:, :, 1:], pose_mat[:, :, :1], trans)
        wbody_rot = matrix_to_quaternion(wbody_mat)[..., [1, 2, 3, 0]]
        result = {}
        if self.extend_config:
            if return_full:
                result["global_velocity_extend"] = self._compute_velocity(wbody_pos, dt)
                result["global_angular_velocity_extend"] = self._compute_angular_velocity(wbody_rot, dt)
            result["global_translation_extend"] = wbody_pos.clone()
            result["global_rotation_mat_extend"] = wbody_mat.clone()
            result["global_rotation_extend"] = wbody_rot
            wbody_pos = wbody_pos[..., : self.num_bodies, :]
            wbody_mat = wbody_mat[..., : self.num_bodies, :, :]
            wbody_rot = wbody_rot[..., : self.num_bodies, :]
        result.update(
            global_translation=wbody_pos,
            global_rotation_mat=wbody_mat,
            global_rotation=wbody_rot,
        )
        if return_full:
            velocity = self._compute_velocity(wbody_pos, dt)
            angular_velocity = self._compute_angular_velocity(wbody_rot, dt)
            if self.extend_config:
                dof_pos = pose.sum(dim=-1)[..., 1 : self.num_bodies]
            elif len(self.actuated_joints_idx) != self.num_bodies:
                dof_pos = pose.sum(dim=-1)[..., self.actuated_joints_idx]
            else:
                dof_pos = pose.sum(dim=-1)[..., 1:]
            dof_vel = (dof_pos[:, 1:] - dof_pos[:, :-1]) / dt
            result.update(
                local_rotation=pose_quat[..., [1, 2, 3, 0]],
                global_root_velocity=velocity[..., 0, :],
                global_root_angular_velocity=angular_velocity[..., 0, :],
                global_angular_velocity=angular_velocity,
                global_velocity=velocity,
                dof_pos=dof_pos,
                # Deliberately retain PHC's penultimate difference at the end.
                dof_vels=torch.cat([dof_vel, dof_vel[:, -2:-1]], dim=1),
                fps=int(1 / dt),
            )
        return SimpleNamespace(**result)

    def forward_kinematics_batch(self, rotations, root_rotations, root_positions):
        batch, frames = rotations.shape[:2]
        offsets = self._offsets[:, None].expand(batch, frames, self.num_bodies_augment, 3).to(root_rotations)
        local = self._local_rotation_mat.to(root_rotations)
        positions, matrices = [], []
        for index, parent in enumerate(self._parents):
            if parent == -1:
                positions.append(root_positions)
                matrices.append(root_rotations)
            else:
                offset = offsets[:, :, index, :, None]
                positions.append((matrices[parent][:, :, 0] @ offset).squeeze(-1) + positions[parent])
                matrices.append(matrices[parent] @ (local[:, index : index + 1] @ rotations[:, :, index - 1 : index]))
        return torch.stack(positions, dim=2), torch.cat(matrices, dim=2)

    @staticmethod
    def _compute_velocity(positions, time_delta):
        velocity = np.gradient(positions.detach().cpu().numpy(), axis=-3) / time_delta
        return torch.from_numpy(gaussian_filter1d(velocity, 2, axis=-3, mode="nearest")).to(positions)

    @staticmethod
    def _compute_angular_velocity(rotations, time_delta):
        """Quaternion finite differences, then PHC's sigma=2 smoothing.

        Quaternions here are xyzw. Use the unit Hamilton relative rotation
        and its positive-scalar angle in [0, pi]; the last difference is zero.
        This arithmetic is independent of poselib, whose API is unnecessary.
        """
        previous = rotations[..., :-1, :, :]
        following = rotations[..., 1:, :, :]
        # Expand the standard Hamilton product component by component. A dot
        # reduction groups additions differently; a one-ULP scalar change is
        # amplified by acos for tiny rotations and changes reference speeds.
        ax, ay, az, aw = following.unbind(-1)
        bx, by, bz, bw = torch.cat([-previous[..., :3], previous[..., 3:]], dim=-1).unbind(-1)
        difference = torch.stack(
            (
                aw * bx + ax * bw + ay * bz - az * by,
                aw * by + ay * bw + az * bx - ax * bz,
                aw * bz + az * bw + ax * by - ay * bx,
                aw * bw - ax * bx - ay * by - az * bz,
            ),
            dim=-1,
        )
        difference = torch.where(difference[..., 3:] < 0, -difference, difference)
        difference = difference / difference.norm(dim=-1, keepdim=True).clamp(min=1e-9)
        angle = (2 * difference[..., 3].square() - 1).clamp(-1, 1).acos()
        axis = difference[..., :3] / difference[..., :3].norm(dim=-1, keepdim=True).clamp(min=1e-9)
        velocity = torch.zeros_like(rotations[..., :3])
        velocity[..., :-1, :, :] = axis * angle[..., None] / time_delta
        filtered = gaussian_filter1d(velocity.detach().cpu().numpy(), 2, axis=-3, mode="nearest")
        return torch.from_numpy(filtered).to(rotations)
