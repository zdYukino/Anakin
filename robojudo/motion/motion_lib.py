"""Bounded loader/query runtime for robot motions stored in PHC format.

Adapted from PHC motion_lib_{base,real}.py, pinned at
f8e75fb94918140e85db9744abf1f3b7667428a1 plus this repository's heading/dtype
patch. See SOURCE.md and LICENSE-PHC. Training/SMPL/mesh/worker services are
deliberately outside this playback implementation.
"""

import glob
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import joblib
import numpy as np
import torch
from scipy.spatial.transform import Rotation

from ._quaternion import inverse_heading_wxyz, slerp
from .kinematics import HumanoidBatch


class FixHeightMode(Enum):
    no_fix = 0
    full_fix = 1
    ankle_fix = 2


class MotionLibReal:
    """Load deterministic robot reference clips and query batched times.

    Supported input is a joblib ``.pkl`` mapping clip names to ``pose_aa``,
    ``root_trans_offset``, and ``fps``, or a directory of such files. Cached
    ``dof``, ``root_rot`` and SMPL fields do not replace FK-derived state.
    """

    def __init__(self, motion_lib_cfg):
        self.m_cfg = motion_lib_cfg
        self._device = torch.device(motion_lib_cfg.get("device", "cpu"))
        self.fix_height = motion_lib_cfg.get("fix_height", FixHeightMode.no_fix)
        if self.fix_height != FixHeightMode.no_fix:
            raise NotImplementedError(
                "Internal motion playback supports FixHeightMode.no_fix; mesh fitting is external"
            )
        if motion_lib_cfg.get("min_length", -1) != -1 or motion_lib_cfg.get("im_eval", False):
            raise NotImplementedError("Training/evaluation clip filtering is not part of internal motion playback")
        self.mesh_parsers = HumanoidBatch(motion_lib_cfg["robot"])
        self.num_joints = self.mesh_parsers.num_bodies
        self.num_bodies = self.num_joints
        self.load_data(motion_lib_cfg["motion_file"])

    def load_data(self, motion_file):
        path = Path(motion_file)
        if path.is_file():
            clips = self._read_motion_file(path)
            self._motion_data_keys = np.asarray(list(clips))
            self._motion_data_list = list(clips.values())
        elif path.is_dir():
            files = glob.glob(str(path / "*.pkl"))
            if not files:
                raise ValueError(f"Motion directory {path} contains no .pkl files")
            # Retain PHC's file keys and directory traversal order.
            self._motion_data_keys = np.asarray(files)
            self._motion_data_list = files
        else:
            raise FileNotFoundError(f"Motion file or directory does not exist: {path}")
        self._num_unique_motions = len(self._motion_data_list)
        self._sampling_prob = torch.ones(self._num_unique_motions, device=self._device) / self._num_unique_motions

    @staticmethod
    def _read_motion_file(path):
        clips = joblib.load(path)
        if not isinstance(clips, Mapping) or not clips:
            raise ValueError(f"PHC motion file {path} must contain a nonempty mapping of clip names to data")
        return clips

    def num_motions(self):
        return self._num_motions

    def num_unique_motions(self):
        return self._num_unique_motions

    def get_total_length(self):
        return self._motion_lengths.sum().item()

    def get_motion_length(self, motion_ids=None):
        return self._motion_lengths if motion_ids is None else self._motion_lengths[motion_ids]

    def _clip_data(self, index):
        clip = self._motion_data_list[index]
        if isinstance(clip, str):
            path = Path(clip)
            clips = self._read_motion_file(path)
            key = path.name.split(".", 1)[0]
            if key not in clips:
                raise ValueError(f"Motion file {path} must contain its filename key {key!r}")
            clip = clips[key]
        if not isinstance(clip, Mapping):
            raise ValueError(f"Motion clip {self._motion_data_keys[index]!r} must be a mapping")
        return clip

    def _load_clip(self, index, target_heading):
        clip = self._clip_data(index)
        key = self._motion_data_keys[index]
        missing = {"pose_aa", "root_trans_offset", "fps"} - clip.keys()
        if missing:
            raise ValueError(f"Motion clip {key!r} is missing required fields: {', '.join(sorted(missing))}")
        try:
            pose = torch.as_tensor(clip["pose_aa"]).detach().cpu().clone()
            trans = torch.as_tensor(clip["root_trans_offset"]).detach().cpu().clone()
        except (TypeError, ValueError, RuntimeError) as error:
            raise ValueError(f"Motion clip {key!r} needs numeric pose_aa and root_trans_offset arrays") from error
        try:
            fps = float(clip["fps"])
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f"Motion clip {key!r} must have a finite positive fps") from error
        if not np.isfinite(fps) or fps <= 0:
            raise ValueError(f"Motion clip {key!r} must have a finite positive fps, got {fps}")
        if pose.ndim != 3 or pose.shape[-1] != 3 or trans.shape != (pose.shape[0], 3):
            raise ValueError(f"Motion clip {key!r} needs pose_aa (frames, bodies, 3) and root_trans_offset (frames, 3)")
        if pose.shape[0] < 3:
            raise ValueError(f"Motion clip {key!r} needs at least three motion frames for velocity calculation")
        if pose.shape[1] < self.mesh_parsers.num_bodies_augment:
            raise ValueError(
                f"Motion clip {key!r} needs pose_aa with at least {self.mesh_parsers.num_bodies_augment} bodies"
            )
        if not pose.is_floating_point() or not trans.is_floating_point():
            raise ValueError(f"Motion clip {key!r} poses and root translations must be floating point")
        if not torch.isfinite(pose).all() or not torch.isfinite(trans).all():
            raise ValueError(f"Motion clip {key!r} contains nonfinite poses or translations")
        if "beta" in clip:
            raise NotImplementedError(f"Motion clip {key!r} contains SMPL beta data; supply a retargeted robot motion")
        if target_heading is not None:
            start_root = Rotation.from_rotvec(pose[0, 0].numpy())
            heading_inverse = inverse_heading_wxyz(torch.from_numpy(start_root.as_quat()[None]))
            heading_delta = Rotation.from_quat(target_heading) * Rotation.from_quat(
                heading_inverse.numpy(), scalar_first=True
            )
            pose[:, 0] = torch.from_numpy((heading_delta * Rotation.from_rotvec(pose[:, 0].numpy())).as_rotvec())
            # This float32 cast is part of the repository's original PHC patch.
            trans = trans.float() @ torch.from_numpy(heading_delta.as_matrix().squeeze().T).float()
        result = self.mesh_parsers.fk_batch(pose[None], trans[None], return_full=True, dt=1 / fps)
        return SimpleNamespace(
            **{name: value.squeeze(0) if torch.is_tensor(value) else value for name, value in vars(result).items()}
        )

    def load_motions(
        self,
        skeleton_trees,
        gender_betas,
        limb_weights,
        random_sample=True,
        start_idx=0,
        max_len=-1,
        target_heading=None,
    ):
        if random_sample:
            raise NotImplementedError(
                "Internal motion playback requires random_sample=False; training sampling is external"
            )
        if max_len != -1:
            raise NotImplementedError(
                "Internal motion playback loads complete clips; random max_len cropping is external"
            )
        if not skeleton_trees:
            raise ValueError("At least one skeleton tree is required to load motions")
        if len(limb_weights) != len(skeleton_trees) or len(gender_betas) != len(skeleton_trees):
            raise ValueError("Provide one gender_betas and limb_weights entry per skeleton tree")
        for tree in skeleton_trees:
            if list(tree.node_names) != self.mesh_parsers.body_names:
                raise ValueError("Motion skeleton body order does not match the configured robot MJCF")
        indices = [(slot + start_idx) % self._num_unique_motions for slot in range(len(skeleton_trees))]
        motions = [self._load_clip(index, target_heading) for index in indices]
        self._curr_motion_ids = torch.tensor(indices, dtype=torch.long, device=self._device)
        self.curr_motion_keys = self._motion_data_keys[indices]
        self._num_motions = len(motions)
        self._motion_fps = torch.tensor([motion.fps for motion in motions], dtype=torch.float32, device=self._device)
        self._motion_dt = torch.tensor([1 / motion.fps for motion in motions], dtype=torch.float32, device=self._device)
        self._motion_num_frames = torch.tensor(
            [motion.global_rotation.shape[0] for motion in motions], dtype=torch.long, device=self._device
        )
        self._motion_lengths = torch.tensor(
            [(motion.global_rotation.shape[0] - 1) / motion.fps for motion in motions],
            dtype=torch.float32,
            device=self._device,
        )
        self._motion_bodies = torch.zeros((len(motions), 17), device=self._device)
        self._motion_aa = torch.zeros((int(self._motion_num_frames.sum()), self.num_joints * 3), device=self._device)
        self._motion_limb_weights = torch.as_tensor(np.asarray(limb_weights), dtype=torch.float32, device=self._device)
        fields = {
            "gts": "global_translation",
            "grs": "global_rotation",
            "lrs": "local_rotation",
            "grvs": "global_root_velocity",
            "gravs": "global_root_angular_velocity",
            "gavs": "global_angular_velocity",
            "gvs": "global_velocity",
            "dvs": "dof_vels",
            "dof_pos": "dof_pos",
        }
        if self.mesh_parsers.extend_config:
            fields.update(
                gts_t="global_translation_extend",
                grs_t="global_rotation_extend",
                gvs_t="global_velocity_extend",
                gavs_t="global_angular_velocity_extend",
            )
        for name, field in fields.items():
            setattr(self, name, torch.cat([getattr(motion, field) for motion in motions]).float().to(self._device))
        self.length_starts = torch.cat(
            [torch.zeros(1, device=self._device, dtype=torch.long), self._motion_num_frames[:-1]]
        )
        self.length_starts = self.length_starts.cumsum(0)
        self.motion_ids = torch.arange(len(motions), dtype=torch.long, device=self._device)
        return motions

    def _query_frames(self, motion_ids, motion_times):
        if not hasattr(self, "_motion_lengths"):
            raise RuntimeError("Call load_motions before querying reference motion")
        ids = torch.as_tensor(motion_ids, dtype=torch.long, device=self._device)
        times = torch.as_tensor(motion_times, dtype=torch.float32, device=self._device)
        if ids.ndim != 1 or times.ndim != 1 or ids.shape != times.shape:
            raise ValueError("motion_ids and motion_times must be one-dimensional arrays of equal length")
        if not torch.isfinite(times).all():
            raise ValueError("Motion query times must be finite")
        if ((ids < 0) | (ids >= self._num_motions)).any():
            raise IndexError(f"Motion query IDs must refer to the {self._num_motions} currently loaded clips")
        first, second, blend = self._calc_frame_blend(
            times, self._motion_lengths[ids], self._motion_num_frames[ids], self._motion_dt[ids]
        )
        return ids, first + self.length_starts[ids], second + self.length_starts[ids], blend[:, None]

    @staticmethod
    def _calc_frame_blend(time, length, num_frames, dt):
        time = time.clone()
        phase = torch.clip(time / length, 0.0, 1.0)
        time[time < 0] = 0
        first = (phase * (num_frames - 1)).long()
        second = torch.minimum(first + 1, num_frames - 1)
        blend = torch.clip((time - first * dt) / dt, 0.0, 1.0)
        return first, second, blend

    def get_root_pos_smpl(self, motion_ids, motion_times):
        _, first, second, blend = self._query_frames(motion_ids, motion_times)
        blend = blend[..., None]
        positions = (1 - blend) * self.gts[first] + blend * self.gts[second]
        return {"root_pos": positions[..., 0, :].clone()}

    def get_motion_state(self, motion_ids, motion_times, offset=None):
        ids, first, second, blend = self._query_frames(motion_ids, motion_times)
        body_blend = blend[..., None]

        def linear(data, weight=body_blend):
            return (1 - weight) * data[first] + weight * data[second]

        if offset is not None:
            offset = torch.as_tensor(offset, dtype=torch.float32, device=self._device)
            if offset.shape not in ((3,), (1, 3), (len(ids), 3)) or not torch.isfinite(offset).all():
                raise ValueError("Position offset must be finite with shape (3,), (1, 3), or (number of queries, 3)")
            offset = offset[..., None, :]
        position_offset = 0 if offset is None else offset
        positions = linear(self.gts) + position_offset
        rotations = slerp(self.grs[first], self.grs[second], body_blend)
        velocity = linear(self.gvs)
        angular_velocity = linear(self.gavs)
        if self.mesh_parsers.extend_config:
            extended_positions = linear(self.gts_t) + position_offset
            extended_rotations = slerp(self.grs_t[first], self.grs_t[second], body_blend)
            extended_velocity = linear(self.gvs_t)
            extended_angular_velocity = linear(self.gavs_t)
        else:
            extended_positions, extended_rotations = positions, rotations
            extended_velocity, extended_angular_velocity = velocity, angular_velocity
        return {
            "root_pos": positions[..., 0, :].clone(),
            "root_rot": rotations[..., 0, :].clone(),
            "dof_pos": linear(self.dof_pos, blend).clone(),
            "root_vel": velocity[..., 0, :].clone(),
            "root_ang_vel": angular_velocity[..., 0, :].clone(),
            "dof_vel": linear(self.dvs, blend).reshape(len(ids), -1),
            "motion_aa": self._motion_aa[first],
            "motion_bodies": self._motion_bodies[ids],
            "motion_limb_weights": self._motion_limb_weights[ids],
            "rg_pos": positions,
            "rb_rot": rotations,
            "body_vel": velocity,
            "body_ang_vel": angular_velocity,
            "rg_pos_t": extended_positions,
            "rg_rot_t": extended_rotations,
            "body_vel_t": extended_velocity,
            "body_ang_vel_t": extended_angular_velocity,
        }
