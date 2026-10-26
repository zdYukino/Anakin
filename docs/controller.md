# Controller

**Controller** is the component that gives `ctrl_data` to the robot.

## [Controller](#controller)

`Controller` is the base class for all controllers. It defines the interface that all controllers must implement.

---
We provide the following controllers:
- [JoystickCtrl](#controller--joystickctrl)
- [UnitreeCtrl](#controller--unitreectrl)
- [KeyboardCtrl](#controller--keyboardctrl)
- [MotionCtrl](#controller--motionctrl)
- [BeyondmimicCtrl](#controller--beyondmimicctrl)

## [Controller](#controller) > [JoystickCtrl](#controller--joystickctrl)

`JoystickCtrl` is the controller that controls the robot using the joystick. It is a subclass of `Controller` and implements the interface defined in `Controller`.

script:
  - [joystick_ctrl.py](../robojudo/controller/joystick_ctrl.py)

Example data of Xbox Joystick with Linear Triggers:

`ctrl_data`:`dict`, the control data.
  - `axes`: `dict[str, float]`:
    - `LeftX`: left axes x value. Range: [-1, 1]
    - `LeftY`: left axes y value. Range: [-1, 1]
    - `RightX`: Right axes x value. Range: [-1, 1]
    - `RightY`: Right axes y value. Range: [-1, 1]
    - `LT`: left trigger value. Range: [0, 1]
    - `RT`: right trigger value. Range: [0, 1]
  - `button_event`: `list[dict]`:
    `dict`:
      - `name`: the name of the button. like `A`, `B`, `X`, `Y`...
      - `press`: whether the button is pressed. `bool`. `True` for `press`, `False` for `release`
      - `timestamp`: the time when the button event occurs. `float`
      - `type`: the type of the button event.

`command`: `list` of commands when `triggers` or `triggers_extra` are detected.

**example**:
```json
{'axes': {'LeftX': 0.0, 'LeftY': 0.0, 'RightX': 0.0, 'RightY': 0.0, 'LT': 0.0, 'RT': 0.0}, 'button_event': [{'type': 'button', 'name': 'A', 'pressed': False, 'timestamp': 1758886189.6776087}]}
```

You can set Hotkeys in JoystickCtrlCfg:
```python
JoystickCtrlCfg(
    triggers_extra={
        "RB+Down": "[POLICY_SWITCH],0",
        "LB+RB+A": "COMBO_TEST",
    }
),
```
when you press the `RB+Down` button, the command will be `["[POLICY_SWITCH],0"]`.

💡We have joystick mapping config for different platforms and Joystick types. 

> For KEY name and more details, please refer to the [joystick.py](../robojudo/controller/utils/joystick.py)

## [Controller](#controller) > [UnitreeCtrl](#controller--unitreectrl)

`UnitreeCtrl` is the controller that controls the robot using the `UnitreeG1` controller. It is a subclass of `Controller` and implements the interface defined in `Controller`. 

> ⚠️ If you don't connect to a Unitree robot, `UnitreeCtrl` won't work.

script:
- [unitree_ctrl.py](../robojudo/controller/unitree_ctrl.py)

`ctrl_data` and `command` are the same as `JoystickCtrl`.

## [Controller](#controller) > [KeyboardCtrl](#controller--keyboardctrl)

`KeyboardCtrl` is the controller that controls the robot using the keyboard. It is a subclass of `Controller` and implements the interface defined in `Controller`.

script:
  - [keyboard_ctrl.py](../robojudo/controller/keyboard_ctrl.py)
  
`ctrl_data`:`list[dict]`, the control data.
  `dict`:
   - `type`: the type of the input. `str`. `keyboard`
   - `name`: the name of the input key. `str`. like `a`, `Key.ctrl_l`, `Key.space`, `\x06`...
   - `pressed`: the value of the input. `bool`. `True` for `press`, `False` for `release`.
   - `timestamp`: the time when the input event occurs. `float`

`command`: `list`, only generate when you set `triggers`, otherwise, the command will be `[]`.

**example**:
```
[{'type': 'keyboard', 'name': 's', 'pressed': True, 'timestamp': 1758888074.643119}]
```

Similarly, you can set command triggers:
```python
KeyboardCtrl(
  cfg_ctrl=KeyboardCtrlCfg(
      triggers_extra={
          "Key.space": "[TEST]",
          "\x01": "[CTRL_A]",
      }
    )
  )
```
when you press the `Ctrl+A` button, the command will be `[CTRL_A]`.

💡For more details, please refer to the [keyboard.py](../robojudo/controller/utils/keyboard.py)


## [Controller](#controller) > [MotionCtrl](#controller--motionctrl)

`MotionCtrl` is the controller that controls the robot using the motion. It is a subclass of `Controller` and implements the interface defined in `Controller`.

`MotionCtrl` usually is used on mimic task to provide refer motion.

Motion loading, kinematics, and time queries use the [bundled runtime](../robojudo/motion/SOURCE.md); no PHC submodule or separate `phc` / `poselib` installation is needed. The existing `phc.robot_config_file` field and PHC-format `.pkl` files remain supported.

The base `MotionCtrl.get_data()` returns:

- `ref_body_pos_subset`: `np.ndarray`, reference positions of selected keypoints and extension nodes.
- `ref_body_vel_subset`: `np.ndarray`, corresponding reference velocities multiplied by the playback speed.
- `dof_pos`: `np.ndarray`, reference robot joint angles.

`MotionH2HCtrl` also returns `robot_body_pos_subset` from the environment's forward kinematics and requires an FK-enabled environment. KungfuBot and TWIST controllers organize the motion into their policy-specific future references or `action_mimic` input. Query quaternions use `xyzw` order. Existing optional hand-output hooks remain, but the current loader and samples do not provide hand data.

`MotionCtrl` can be set by `MotionCtrlCfg`. For instance, `G1MotionCtrlCfg`:

```python
G1MotionCtrlCfg(
    motion_name="singles/0-KIT_6_WalkInCounterClockwiseCircle05_1_poses",
    motion_ctrl_gui=False,  # Disable the motion GUI for headless playback.
)
```

Default configurations and motion locations:

| Configuration | Bundled robot config | Motion directory |
| --- | --- | --- |
| `G1MotionCtrlCfg` / `G1MotionH2HCtrlCfg` | `robot/unitree_g1_29dof.yaml` | `assets/motions/g1/phc_29/` |
| `G1MotionKungfuBotCtrlCfg` / `G1MotionTwistCtrlCfg` | `robot/unitree_g1_23dof_KungfuBot.yaml` | `assets/motions/g1/phc/` |
| `H1MotionH2HCtrlCfg` | `robot/unitree_h1.yaml` | `assets/motions/h1/phc/` |

`motion_name` is the path within the motion directory without the `.pkl` suffix. Custom robot YAML files can be selected through `phc.robot_config_file`; relative model paths resolve against the YAML directory and `assetRoot`.

Motion files must already be retargeted to the matching skeleton and joint order, with `pose_aa`, `root_trans_offset`, and `fps` for each clip. The runtime derives joint and body states from the poses and preserves the existing interpolation, velocities, heading, and position offsets. Compatible policy models are still required. Training, human-motion conversion, retargeting, and mesh-based height fitting remain external workflows.

## [Controller](#controller) > [BeyondMimicCtrl](#controller--beyondmimicctrl)

`BeyondMimicCtrl` is the controller for `BeyondMimicPolicy`. It is a subclass of `Controller` and implements the interface defined in `Controller`.

You don't need to master `BeyondMimicCtrl`. It is just designed for `BeyondMimicPolicy`. You can set it with config:

```python
G1BeyondmimicCtrlCfg(
  motion_name="dance1_subject2", # only when policy: use_motion_from_model=False
)
```