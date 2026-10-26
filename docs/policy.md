# Policy

**Policy** is the component that controls the robot. It receives the `env_data` from the environment, `ctrl_data` from the controller, organize the observation and infer the action fo robot.

## [Policy](#policy)

`Policy` is the base class for all policies. It defines the interface for the policy, as in [base_policy.py](../robojudo/policy/base_policy.py)

---

We provide the following policies:
- [UnitreePolicy](#policy--unitreepolicy)
- [AMOPolicy](#policy--amopolicy)
- [H2HStudentPolicy](#policy--h2hstudentpolicy)
- [HugWBCPolicy](#policy--hugwbcpolicy)
- [BeyondMimicPolicy](#policy--beyondmimicpolicy)
- [ASAPPolicy](#policy--asappolicy)
- [KungfuBotGeneralPolicy](#policy--kungfubotgeneralpolicy)
- [TwistPolicy](#policy--twistpolicy)
- [ProtoMotionsTrackerPolicy](#policy--protomotionstrackerpolicy)

## [Policy](#policy) > [UnitreePolicy](#policy--unitreepolicy)

`UnitreePolicy` is the policy that controls the robot using the [Unitree official policy](https://github.com/unitreerobotics/unitree_rl_gym).

script: [unitree_policy.py](../robojudo/policy/unitree_policy.py)

To control the robot using `UnitreePolicy`, you can refer `_get_commands()`:

`commands`:
- `commands[0]`, [-1, 1], control the robot to walk forward and backward
- `commands[1]`, [-1, 1], control the robot to walk left and right
- `commands[2]`, [-1, 1], control the robot to turn left and right

for instance, use `JoystickCtrl` to control:

```python
def _get_commands(self, ctrl_data: dict) -> list[float]:
    commands = np.zeros(3)
    for key in ctrl_data.keys():
        if key in ["JoystickCtrl", "UnitreeCtrl"]:
            axes = ctrl_data[key]["axes"]
            lx, ly, rx, ry = axes["LeftX"], axes["LeftY"], axes["RightX"], axes["RightY"]

            commands[0] = command_remap(ly, self.commands_map[0])
            commands[1] = command_remap(lx, self.commands_map[1])
            commands[2] = command_remap(rx, self.commands_map[2])
            break
    return commands
```

### [UnitreeWoGaitPolicy](#policy--unitreewogaitpolicy)

For Unitree G1, we also provide `UnitreeWoGaitPolicy`, which supports the new `Unitree-G1-29dof-Velocity` conig from [unitree_rl_lab](https://github.com/unitreerobotics/unitree_rl_lab).

The difference is that `UnitreeWoGaitPolicy` does not include gait in the observation, so the robot will not keep stepping when standing.

script: [unitree_policy.py](../robojudo/policy/unitree_policy.py)

## [Policy](#policy) > [AMOPolicy](#policy--amopolicy)

`AMOPolicy` is the policy that controls the robot using the [AMO](https://github.com/OpenTeleVision/AMO).

script: [amo_policy.py](../robojudo/policy/amo_policy.py)

To control the robot using `AMOPolicy`, you can refer `_get_commands()`:

`commands`:
- `commands[0]`, [-1, 1], control the robot to walk forward and backward
- `commands[1]`, [-1, 1], control the robot to turn left and right
- `commands[2]`, [-1, 1], control the robot to walk left and right
- `commands[3]`, [-0.5, 0.8], control the robot torso height
- `commands[4]`, [-1.57, 1.57], control the robot torso yaw
- `commands[5]`, [-0.52, 1.57], control the robot torso pitch
- `commands[6]`, [-0.7, 0.7], control the robot torso roll

You can apply your own controller to control the robot using `AMOPolicy`. Just set the `commands` in `_get_comands()`


## [Policy](#policy) > [H2HStudentPolicy](#policy--h2hstudentpolicy)

`H2HStudentPolicy` is the policy that controls the robot using the [human2humanoid](https://github.com/LeCAR-Lab/human2humanoid).

> The MotionLib runtime and G1/H1 kinematics resources are bundled; no PHC or poselib installation is needed. Retargeted motions and model files must still match the robot and policy.

script: [h2hstudent_policy.py](../robojudo/policy/h2hstudent_policy.py)

`H2HStudentPolicy` is controlled by `MotionH2HCtrl`. check code [motion_h2h_ctrl.py](../robojudo/controller/motion_h2h_ctrl.py).

For motion source:
- `Unitree H1`: Simply use the motion retargeting pipeline from [human2humanoid](https://github.com/LeCAR-Lab/human2humanoid).
- `Unitree G1`: Use PHC-format 29-DOF motions with the [bundled runtime config](../robojudo/motion/resources/config/robot/unitree_g1_29dof.yaml). The retained [historical fitting config](../third_party/patches/phc_addon_g1/phc/data/cfg/robot/unitree_g1_29dof_fitting.yaml) is a reference for external retargeting workflows; the bundled runtime does not perform fitting or retargeting.

Place H1 and G1 motion files under `assets/motions/h1/phc/` and `assets/motions/g1/phc_29/`, respectively, keeping the existing `.pkl` format. See [MotionCtrl](controller.md#controller--motionctrl).

You can refer to `g1_h2h` config in [g1_cfg.py](../robojudo/config/g1/g1_cfg.py) for more details.


## [Policy](#policy) > [HugWBCPolicy](#policy--hugwbcpolicy)

`HugWBCPolicy` is the policy that controls the robot using the [HugWBC](https://github.com/apexrl/HugWBC).

script: [hugwbc_policy.py](../robojudo/policy/hugwbc_policy.py)

🥺Will release soon.


## [Policy](#policy) > [BeyondMimicPolicy](#policy--beyondmimicpolicy)

`BeyondMimicPolicy` is the policy that controls the robot using the [whole_body_tracking](https://github.com/HybridRobotics/whole_body_tracking).

We support both `G1FlatEnvCfg` and `G1FlatWoStateEstimationEnvCfg`. 
For motion source, you could use the motion inside onnx policy, or use `BeyondmimicCtrl` with npz files.

script: [beyondmimic_policy.py](../robojudo/policy/beyondmimic_policy.py)

[`BeyondMimicPolicyCfg`](../robojudo/policy/policy_cfgs.py): check example at [G1BeyondMimicPolicyCfg](../robojudo/config/g1/policy/g1_beyondmimic_policy_cfg.py):
 - `policy_name`: The name of the policy. We provive `Jump_wose` for test. You should put your policy in `assets/models/g1/beyondmimic`
 - `without_state_estimator`: Weather policy is `WoStateEstimation`. Default is `True`.
 - `use_modelmeta_config`: Whether to use modelmeta config. Default is `True`. If `False`, the policy will use config in your `BeyondMimicPolicyCfg`.
 - `use_motion_from_model`: Whether to use motion in the onnx model. Default is `True`. If `False`, you need to enable `BeyondMimicCtrl`.
.

 You can refer to `g1_beyondmimic` and `g1_beyondmimic_with_ctrl` in [g1_cfg.py](../robojudo/config/g1/g1_cfg.py) for details.

## [Policy](#policy) > [AsapPolicy](#policy--asappolicy)

`AsapPolicy` is the policy that controls the robot using the [ASAP](https://github.com/LeCAR-Lab/ASAP).

Also, [KungfuBot](https://github.com/TeleHuman/PBHC) is supported by `AsapPolicy`.

RoboJuDo support both `deepmimic` and `decoupled_locomotion` of the official repo, implemeted as `AsapPolicy` and `AsapLocoPolicy`.

We fully reproduced the original repository, including keyboard and joystick mapping:
- `i` to make the robot the initial position
- `o` to emergence stop the robot

for locomotion policy:
- `=` to switch between tapping and walking for the locomotion policy
- `w/a/s/d` to control the linear velocity
- `q/e` to control the angular velocity
- `z` to set all commands to zero

for policy switch:
- `[` to switch to MotionMimic
- `]` to switch to LocoMotion
- `;` toggle next mimic policy
- `'` toggle prev mimic policy

or with joystick:
- `Left` to switch between tapping and walking for the locomotion policy
- `Up/Down` to control the height
- `left axes` to control the linear velocity
- `right axes` to control the angular velocity
- `Select/Back` to switch to LocoMotion
- `Start` to switch to MotionMimic
- `R1/RB` to toggle next mimic policy
- `L1/LB` to toggle prev mimic policy

script: [asap_policy.py](../robojudo/policy/asap_policy.py)

> For your convenience, `CR7_level1` checkpoint is included, you can ran sim2sim with `g1_asap` config in [g1_asap_cfg.py](../robojudo/config/g1/g1_asap_cfg.py).

You can add more models to `assets/models/g1/asap/mimic`. Any model in the official repo [ASAP-sim2real](https://github.com/LeCAR-Lab/ASAP/tree/main/sim2real/models), [PBHC](https://github.com/TeleHuman/PBHC/tree/main/example) and [RoboMimic_Deploy](https://github.com/ccrpRepo/RoboMimic_Deploy) should work.

This example highlights the advantages of RoboJudo:
- Modular code & config with easy implementation and strong readability
- Flexible policy switching, with interpolation support.
- Convenient external controller processing

You can refer to `g1_asap` and `g1_asap_loco` config in [g1_asap_cfg.py](../robojudo/config/g1/g1_asap_cfg.py) for test and details.

## [Policy](#policy) > [KungfuBotGeneralPolicy](#policy--kungfubotgeneralpolicy)

`KungfuBotGeneralPolicy` is the policy that controls the robot using the [PBHC](https://github.com/TeleHuman/PBHC)-KungfuBot2.

To be noted, this is for **KungfuBot2** general model, for KungfuBot, please use [AsapPolicy](#policy--asappolicy).

> MotionLib playback uses the bundled runtime; no PHC or poselib installation is needed. Prepare compatible G1 23-DOF motions and a KungfuBot2 policy model.

script: [kungfubot_policy.py](../robojudo/policy/kungfubot_policy.py)

- `KungfuBotGeneralPolicy` is controlled by `MotionKungfuBotCtrl`
    - check code [motion_kungfubot_ctrl.py](../robojudo/controller/motion_kungfubot_ctrl.py).
    - motions from PBHC pipeline are supported. Put your motion files in `assets/motions/g1/phc/kungfubot/`.

You can refer to `g1_kungfubot2` config in [g1_cfg.py](../robojudo/config/g1/g1_cfg.py) for test and details.

## [Policy](#policy) > [TwistPolicy](#policy--twistpolicy)

`TwistPolicy` is the policy that controls the robot using the [TWIST](https://github.com/YanjieZe/TWIST).

script: [twist_policy.py](../robojudo/policy/twist_policy.py)

For TwistPolicy, we implement two motion source controllers:

- `TwistRedisCtrl` at [twist_redis_ctrl.py](../robojudo/controller/twist_redis_ctrl.py): 
    - get motion from redis server, which is used in the original repo.
    - it works with the motion server like [server_high_level_motion_lib.py](https://github.com/YanjieZe/TWIST/blob/42d8c134739eee51f28d7cc0ff72a86728afb8dc/deploy_real/server_high_level_motion_lib.py)

- `MotionTwistCtrl` at [motion_twist_ctrl.py](../robojudo/controller/motion_twist_ctrl.py): 
    - get motion from local .pkl files. 
    - uses the [bundled PHC-format runtime](../robojudo/motion/SOURCE.md), **preserving the existing motion format** without installing PHC or poselib.
    - motions from [PBHC](https://github.com/TeleHuman/PBHC) pipeline is supported,  put your motion files in `assets/motions/g1/phc/`.

You can refer to `g1_twist` config in [g1_cfg.py](../robojudo/config/g1/g1_cfg.py) for test and details.

## [Policy](#policy) > [ProtoMotionsTrackerPolicy](#policy--protomotionstrackerpolicy)

> Thanks to [NVLabs](https://github.com/NVlabs) for ProtoMotions, and to [Chen Tessler](https://github.com/tesslerc) and [Yifeng Jiang](https://github.com/jyf588) for contributing this RoboJuDo integration.

`ProtoMotionsTrackerPolicy` deploys a [ProtoMotions](https://github.com/NVlabs/ProtoMotions) tracker exported as a unified ONNX pipeline.


For the full deployment walkthrough, please read the official ProtoMotions docs first:

- [ProtoMotions G1 deployment workflow](https://nvlabs.github.io/ProtoMotions/tutorials/workflows/g1_deployment.html#step-5-deploy-via-robojudo-simulation)
- [NVLabs / ProtoMotions](https://github.com/NVlabs/ProtoMotions)

> **Important:** You must clone the `ProtoMotions` repository locally as a sibling directory named `protomotions`. RoboJuDo imports `deployment.motion_utils` and `deployment.state_utils` from that checkout at runtime.


### Core files

- policy implementation: [protomotions_tracker_policy.py](../robojudo/policy/protomotions_tracker_policy.py)
- policy config: [g1_protomotions_tracker_cfg.py](../robojudo/config/g1/policy/g1_protomotions_tracker_cfg.py)
- pipeline configs: [g1_cfg.py](../robojudo/config/g1/g1_cfg.py)
- launcher: [run_tracker_pipeline.py](../scripts/run_tracker_pipeline.py)
- built-in tracker assets:
  - `assets/models/g1/protomotions_tracker/unified_pipeline.onnx`
  - `assets/models/g1/protomotions_tracker/unified_pipeline.yaml`
  - `assets/motions/g1/g1_bones_seed_mini.pt`

### How to run

This repository uses the following built-in configs:

- `g1_protomotions_tracker` for MuJoCo simulation
- `g1_protomotions_tracker_real` for real G1 deployment

Simulation:

```bash
python scripts/run_tracker_pipeline.py -c g1_protomotions_tracker \
 --motion-path assets/motions/g1/g1_bones_seed_mini.pt \
 --motion-index 0
```

Real robot:

```bash
python scripts/run_tracker_pipeline.py -c g1_protomotions_tracker_real \
  --motion-path assets/motions/g1/g1_bones_seed_mini.pt \
  --motion-index 0
```

To test your own exported tracker, add:

```bash
--onnx-path /path/to/unified_pipeline.onnx
```


