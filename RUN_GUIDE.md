# 仿真与真机启动、运动和 Mimic 控制手册

本文维护当前 `scripts/run_pipeline.py` 及 tracker 专用入口的启动命令和实际控制操作。所有命令在**仓库根目录**执行。

核对日期：**2026-10-21**。当前默认注册 **25 个配置：20 个仿真、4 个 G1 C++ 真机、1 个 H1 Python SDK 真机**。下文“文件齐备”表示当前工作区中对应文件存在；本次核对覆盖配置构造、CLI 和源码，没有执行模型推理、仿真或真机动作。

**`--extra sim` 选择仿真依赖，`-c/--config` 才选择运行环境。** 例如 `-c g1_real` 始终选择真机配置，加上 `--extra sim` 不会把它变成仿真。

- [依赖和环境选择](#setup)
- [入口与全部参数](#cli)
- [全部配置与启动命令](#inventory)
- [键盘、手柄和遥控器操作](#controls)
- [运动、Mimic、策略切换操作步骤](#recipes)
- [模型、动作、网卡与配置修改](#customization)
- [资源现状与维护方法](#maintenance)

<a id="setup"></a>
## 1. 依赖和环境选择

| 目标 | 依赖选择 | 运行前需要准备 |
| --- | --- | --- |
| MuJoCo 仿真 | `--extra sim` | `third_party/mujoco_viewer`、图形显示环境；配置启用 USB 手柄时连接兼容设备，启用键盘时需要可用的 `pynput` 系统后端。 |
| G1 C++ 真机 | `--extra unitree` | 官方 C++ SDK 与本仓库 `packages/unitree_cpp` 绑定；机器人网络连接、正确网卡和原装遥控器。 |
| H1 Python SDK 真机 | 基础依赖，另装 `unitree_sdk2py` | SDK2 Python 必须安装在同一个 Python 环境；`--extra unitree` 安装的是 C++ 绑定，不能代替它。 |
| 同一环境兼顾仿真和 G1 真机 | `--extra sim --extra unitree` | 同时满足以上仿真与 C++ SDK 前提。 |

依赖声明见 [pyproject.toml](pyproject.toml) 和 [requirements.txt](requirements.txt)；SDK 安装与网络配置见 [Unitree 配置说明](docs/unitree_setup.md) 和 [C++ 绑定说明](packages/unitree_cpp/README.md)。需要同步环境时可执行相应的一条：

```bash
# 仿真
uv sync --locked --extra sim

# G1 C++ 真机：先完成官方 SDK 的安装
uv sync --locked --extra unitree

# 共用环境
uv sync --locked --extra sim --extra unitree
```

后文命令中的 `--locked` 要求保持现有锁文件。uv 参数放在脚本名前，脚本参数放在脚本名后。

本次核对的 uv 为 **0.13.1**：`uv run` 默认保留额外已安装包，`--exact` 才要求精确同步；`uv sync` 默认精确同步，保留手工安装的 SDK/Redis 客户端时使用 `uv sync --inexact`。**`uv run` 没有 `--inexact` 参数**。已经准备好的环境也可用 `uv run --no-sync ...` 跳过同步。每次同步时应保留自己需要的 extras。

另外两类前提需要单独处理：

- **PHC 格式动作**：H2H、KungfuBot 等使用仓库内的 `robojudo.motion`，机器人 YAML/MJCF 已随包提供，**不需要拉取原始 PHC 子模块或安装外部 poselib**。动作文件仍位于 `assets/motions/.../phc` 或 `phc_29`，这些是数据目录名。默认 PHC 控制窗口需要 Tk 图形环境。
- **`g1_twist`**：还需要 Python `redis` 客户端、`localhost:6379` 的 Redis 服务和持续提供兼容数据的外部生产者。根依赖未声明 Redis 客户端；可在当前环境用 `uv pip install redis` 安装。只有启动 Redis 服务仍不足以运行，详见 [TWIST 操作](#twist)。

G1 真机默认使用 `eth0`，H1 真机默认使用 `eno2`。先修改为实际网卡再启动；所有真机配置当前均为 `env.act=True`、`do_safety_check=True`，运行命令会连接并控制机器人。

<a id="cli"></a>
## 2. 入口与全部参数

### 2.1 通用入口：`scripts/run_pipeline.py`

```bash
# 默认配置是 g1：MuJoCo + USB 手柄
uv run --locked --extra sim scripts/run_pipeline.py

# 显式指定配置
uv run --locked --extra sim scripts/run_pipeline.py -c g1

# 查看脚本参数
uv run --locked --extra sim scripts/run_pipeline.py --help
```

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `-h`、`--help` | — | 输出帮助并退出。 |
| `-c NAME`、`--config NAME` | `g1` | 选择已注册配置，完整名称见下一节。 |

通用入口只接受以上参数。模型、动作、网卡、controller、频率等由配置决定，不能通过任意 `--字段名` 覆盖。

### 2.2 Tracker 入口：`scripts/run_tracker_pipeline.py`

推荐 tracker 使用此入口，显式给出动作文件：

```bash
# 仿真；采用配置默认的 unified_pipeline.onnx
uv run --locked --extra sim scripts/run_tracker_pipeline.py -c g1_protomotions_tracker --motion-path assets/motions/g1/g1_bones_seed_mini.pt --motion-index 0

# 同时显式指定模型；其同目录还必须有 unified_pipeline.yaml
uv run --locked --extra sim scripts/run_tracker_pipeline.py -c g1_protomotions_tracker --onnx-path assets/models/g1/protomotions_tracker/unified_pipeline.onnx --motion-path assets/motions/g1/g1_bones_seed_mini.pt --motion-index 0

# G1 真机：先完成 C++ SDK、网卡和机器人准备
uv run --locked --extra unitree scripts/run_tracker_pipeline.py -c g1_protomotions_tracker_real --motion-path assets/motions/g1/g1_bones_seed_mini.pt --motion-index 0
```

| 参数 | CLI 默认值 | 作用与优先级 |
| --- | --- | --- |
| `-h`、`--help` | — | 输出帮助并退出。 |
| `-c NAME`、`--config NAME` | `g1_protomotions_tracker` | 先构造配置，再应用下面三个显式传入的覆盖值。 |
| `--onnx-path PATH` | `None`，保留配置值 | 覆盖 `cfg.policy.onnx_path`；非 `None` 时优先于 `onnx_name`。 |
| `--motion-path PATH` | `None`，保留配置值 | 覆盖 `cfg.policy.motion_path`。两个默认 tracker 配置的此字段为空，必须传入或修改配置。 |
| `--motion-index INT` | `None`，保留配置值 | 覆盖多动作库中的动作索引；当前配置值为 `0`。每次运行播放一个选定动作。 |

Tracker 默认模型是 `assets/models/g1/protomotions_tracker/unified_pipeline.onnx`。模型元数据路径由 ONNX 路径的 `.onnx` 替换为 `.yaml` 得到，必须配套提供；没有独立的 YAML 参数。

两个入口均没有 `--sim`、`--real`、`--net-if`、`--policy`、`--controller` 或 `--prepare-seconds`。通用入口也没有 tracker 的三个覆盖参数。源码见 [通用入口](scripts/run_pipeline.py)、[tracker 入口](scripts/run_tracker_pipeline.py)、[配置加载器](robojudo/config/config_manager.py)。

<a id="inventory"></a>
## 3. 全部配置与启动命令

表中配置名链接到其定义文件；命令可直接复制。操作列链接到后文对应说明。

- `RL` = `RlPipeline`，单策略；`Multi` = `RlMultiPolicyPipeline`，普通策略切换；`LocoMimic` = `RlLocoMimicPipeline`，行走/模仿过渡。
- `K` = `KeyboardCtrl`，`J` = USB `JoystickCtrl`，`U` = 原装遥控器 `UnitreeCtrl`。箭头表示配置中的 controller 顺序，会影响运动输入来源。
- 策略名称后的模型路径及 companion 文件见 [资源表](#assets)。`ASAP-loco` 指该表中完整名称很长的 decoupled locomotion 模型。
- 下列仿真统一使用 `MujocoEnv`。G1 默认 29-DOF 环境，只有 `g1_dev` 使用 23-DOF 环境；H1 使用 H1 环境。

### 3.1 G1 仿真：16 个

| 配置 / 定义文件 | 启动命令 | Pipeline / 默认策略顺序 | 已启用 controller / 操作 | 当前前提 |
| --- | --- | --- | --- | --- |
| [`g1`](robojudo/config/g1/g1_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c g1` | RL / Unitree `policy_lstm_1` | J；[默认键](#default-controls)、[Unitree 运动](#unitree-movement) | 模型齐备；需要 USB 手柄，未启用键盘。 |
| [`g1_switch`](robojudo/config/g1/g1_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c g1_switch` | Multi / 0: Unitree → 1: AMO | J；[策略选择](#switch-controls) | 模型及 AMO 两个 companion 文件齐备；需要 USB 手柄。 |
| [`g1_locomimic`](robojudo/config/g1/g1_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c g1_locomimic` | LocoMimic / Unitree；mimic 0: CR7 | K → J；[基础组合控制](#locomimic-controls) | 文件齐备；Unitree 运动取键盘，手柄只保留触发命令作用。 |
| [`g1_h2h`](robojudo/config/g1/g1_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c g1_h2h` | RL / H2H `h2h` | K → `MotionH2HCtrl`；[PHC 播放](#phc-controls) | 模型、G1 29-DOF `.pkl` 和内置资源齐备；默认开启 Tk 窗口。 |
| [`g1_beyondmimic`](robojudo/config/g1/g1_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c g1_beyondmimic` | RL / `Jump_wose`，模型内动作 | K；[单策略动作](#standalone-mimic) | 模型齐备；动作自动推进，`max_timestep=140`。 |
| [`g1_beyondmimic_with_ctrl`](robojudo/config/g1/g1_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c g1_beyondmimic_with_ctrl` | RL / `Dance_wose`，外部参考 | K → `BeyondMimicCtrl`；[单策略动作](#standalone-mimic) | 模型与 `dance1_subject2.npz` 齐备；外部参考初始暂停。 |
| [`g1_asap`](robojudo/config/g1/g1_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c g1_asap` | RL / ASAP `CR7_level1` | K；[ASAP 专用键](#custom-controls) | 模型齐备；动作自动推进，默认键表已替换。 |
| [`g1_asap_loco`](robojudo/config/g1/g1_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c g1_asap_loco` | RL / ASAP-loco | K；[ASAP 运动](#asap-movement) | 模型齐备；先用 `=` 切换运动状态。 |
| [`g1_kungfubot2`](robojudo/config/g1/g1_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c g1_kungfubot2` | RL / `horse_test_43000` | K → `MotionKungfuBotCtrl`；[PHC 播放](#phc-controls) | 模型、Horse-stance `.pkl`、内置 23-DOF 参考资源齐备；初始自动 1 倍速，默认 Tk 窗口。 |
| [`g1_twist`](robojudo/config/g1/g1_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c g1_twist` | RL / `twist_general_motion_tracker` | 仅 `TwistRedisCtrl`；[Redis 输入](#twist) | 模型齐备；另需 Redis 客户端、服务和生产者，默认没有本地播放键。 |
| [`g1_switch_beyondmimic`](robojudo/config/g1/g1_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c g1_switch_beyondmimic` | Multi / 0: AMO → 1: Violin → 2: Waltz → 3: Dance_wose | K → J；[策略选择](#switch-controls) | 模型与 AMO companion 齐备；AMO 运动使用手柄。 |
| [`g1_protomotions_tracker`](robojudo/config/g1/g1_cfg.py) | `uv run --locked --extra sim scripts/run_tracker_pipeline.py -c g1_protomotions_tracker --motion-path assets/motions/g1/g1_bones_seed_mini.pt --motion-index 0` | RL / tracker `unified_pipeline` | K；[tracker 控制](#tracker) | ONNX、同名 YAML、命令中的示例 `.pt` 齐备；默认配置未指定动作。 |
| [`g1_dev`](robojudo/config/g1/g1_custom_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c g1_dev` | RL / Unitree `policy_lstm_1` | 仅 K；[Unitree 键盘运动](#unitree-movement) | 模型齐备；23-DOF 实验环境，模型/环境兼容性未作运行验证。 |
| [`g1_locomimic_beyondmimic`](robojudo/config/g1/g1_loco_mimic_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c g1_locomimic_beyondmimic` | LocoMimic / AMO；mimic 0: Dance_wose → 1: Violin → 2: Waltz | 仅 K；[专用组合控制](#locomimic-controls) | 文件齐备；**AMO 无键盘运动消费者，当前配置不能用 WASD 控制行走**。 |
| [`g1_locomimic_asap`](robojudo/config/g1/g1_loco_mimic_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c g1_locomimic_asap` | LocoMimic / ASAP-loco；mimic 0: CR7 → 1: robomimic → 2: kongfu | 仅 K；[组合控制](#locomimic-controls)、[ASAP 运动](#asap-movement) | 模型齐备；运动速度在松键后保留。 |
| [`g1_locomimic_asap_full`](robojudo/config/g1/g1_loco_mimic_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c g1_locomimic_asap_full` | LocoMimic / ASAP-loco；14 个 YAML mimic | 仅 K；[专用组合控制](#locomimic-controls) | **当前缺 13 个 mimic 模型，不能按现有文件直接启动**；见 [完整 ASAP 清单](#full-asap)。 |

### 3.2 H1 仿真：4 个

| 配置 / 定义文件 | 启动命令 | Pipeline / 默认策略顺序 | 已启用 controller / 操作 | 当前前提 |
| --- | --- | --- | --- | --- |
| [`h1`](robojudo/config/h1/h1_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c h1` | RL / Unitree `motion` | J → K；[Unitree 运动](#unitree-movement)、[默认键](#default-controls) | 模型齐备；运动由手柄控制，键盘仍可发退出/重生等触发命令。 |
| [`h1_switch`](robojudo/config/h1/h1_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c h1_switch` | Multi / 0: Unitree `motion` → 1: Smooth | K → J；[策略选择](#switch-controls)、[Smooth 运动](#smooth-movement) | 模型齐备；用 Tab 切换；USB `L1+Y` 映射无效，Smooth 摇杆中位非零。 |
| [`h1_h2h`](robojudo/config/h1/h1_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c h1_h2h` | RL / H2H `h2h_release` | K → `MotionH2HCtrl`；[PHC 播放](#phc-controls) | 模型、H1 punch `.pkl` 和内置资源齐备；默认开启 Tk 窗口。 |
| [`h1_dev`](robojudo/config/h1/h1_custom_cfg.py) | `uv run --locked --extra sim scripts/run_pipeline.py -c h1_dev` | RL / Smooth `train_default-14000-jit` | J → K；[Smooth 运动](#smooth-movement) | 模型齐备；Smooth 只消费摇杆，回中仍有非零参考。 |

### 3.3 真机：5 个

下列 G1 均为 **`UnitreeCppEnv` / `eth0` / 原装遥控器**；H1 为 **`UnitreeEnv` / `eno2` / 原装遥控器**。命令前先完成相应 SDK 与网卡准备。真机不需要仿真 viewer，除非主动开启 FK 调试可视化；核心 MuJoCo 仍用于配置中的 FK。

| 配置 / 定义文件 | 启动命令 | Pipeline / 默认策略顺序 | 遥控操作 | 当前前提 |
| --- | --- | --- | --- | --- |
| [`g1_real`](robojudo/config/g1/g1_cfg.py) | `uv run --locked --extra unitree scripts/run_pipeline.py -c g1_real` | RL / Unitree `policy_lstm_1` | 默认 U；[Unitree 运动](#unitree-movement)、[默认键](#default-controls) | 模型齐备；C++ SDK/绑定、正确网卡与机器人连接。 |
| [`g1_protomotions_tracker_real`](robojudo/config/g1/g1_cfg.py) | `uv run --locked --extra unitree scripts/run_tracker_pipeline.py -c g1_protomotions_tracker_real --motion-path assets/motions/g1/g1_bones_seed_mini.pt --motion-index 0` | RL / tracker `unified_pipeline` | 默认 U；[X/Y 开始，B 回站姿，A shutdown](#tracker) | 模型、YAML、示例动作齐备；默认动作未设置，另需 C++ SDK/网络。 |
| [`g1_locomimic_beyondmimic_real`](robojudo/config/g1/g1_loco_mimic_cfg.py) | `uv run --locked --extra unitree scripts/run_pipeline.py -c g1_locomimic_beyondmimic_real` | LocoMimic / AMO；mimic 0: Dance_wose → 1: Violin → 2: Waltz | 专用 U；[Select/Start、R1/L1](#locomimic-controls)、[AMO 运动](#amo-movement) | 模型与 companion 齐备；C++ SDK/网络；X/B/Y 默认播放映射已替换。 |
| [`g1_locomimic_asap_real`](robojudo/config/g1/g1_loco_mimic_cfg.py) | `uv run --locked --extra unitree scripts/run_pipeline.py -c g1_locomimic_asap_real` | LocoMimic / ASAP-loco；mimic 0: CR7 → 1: robomimic → 2: kongfu | 专用 U；[Select/Start、R1/L1](#locomimic-controls)、[ASAP 运动](#asap-movement) | 模型齐备；C++ SDK/网络；先切换 standing/moving 再运动。 |
| [`h1_real`](robojudo/config/h1/h1_cfg.py) | `uv run --locked scripts/run_pipeline.py -c h1_real` | RL / Unitree `motion` | 默认 U；[Unitree 运动](#unitree-movement)、[默认键](#default-controls) | 模型齐备；**另需 `unitree_sdk2py`**，当前检查环境未安装；C++ extra 不能替代它。 |

当前没有注册 Go2、独立 `g1_kungfubot`、`g1_locomimic_asap_full_real` 或 HugWBC 入口。存在某个策略类或模型文件不等于存在同名 `-c` 配置。

<a id="controls"></a>
## 4. Controller 操作

### 4.1 输入事件和组合键规则

- **键盘触发命令在松键时执行**；WASD 等运动输入由策略处理 press/repeat 事件，时机不同。当前 `KeyboardCtrl` 没有实现 Ctrl 组合门控，因此普通 `i/o/r/[/]/Tab` 等无需按 Ctrl。
- `<`、`>`、`|`、`{`、`}` 指实际字符。美式布局通常分别输入 `Shift+,`、`Shift+.`、`Shift+\`、`Shift+[`、`Shift+]`；其它布局以输入字符为准。
- USB 手柄肩键名是 **LB/RB**，返回键名是 **Back**；Unitree 原装遥控器是 **L1/R1** 和 **Select**。名字不能互换。
- 默认手柄触发在操作键**按下时**执行。组合键先按住肩键，再按操作键；单键 A/X/B/Y 需要不按任何门控肩键。若同时按住两个肩键，生成的是两个前缀的组合，不会匹配只写了一个前缀的操作。
- 专用真机 loco/mimic 配置关闭肩键门控，因此 **R1/L1 是直接单键**。不要额外按住另一肩键。
- 同一周期的命令会去重，执行顺序不保证；选择动作、切模式、开始播放应分次操作，等待日志显示过渡完成。

源码：[默认映射](robojudo/controller/ctrl_cfgs.py)、[键盘触发](robojudo/controller/keyboard_ctrl.py)、[手柄触发](robojudo/controller/joystick_ctrl.py)、[原装遥控解析](robojudo/controller/utils/joystick.py)。

<a id="default-controls"></a>
### 4.2 默认键表

只适用于启动清单中保留默认映射的 controller。`triggers_extra` 是补充或覆盖某几个键；配置显式给出的 `triggers={...}` 会替换整套默认键。

| 命令 | 默认键盘 K | 默认 USB J / 原装 U | 实际作用 |
| --- | --- | --- | --- |
| Shutdown | Esc | A，不按肩键 | 仿真关闭 viewer；真机进入阻尼/禁用，详见 [停止和退出](#stop)。 |
| 仿真重生 | 反引号 `` ` `` | 无 | 重置仿真机器人状态；不等于动作从头重播。 |
| Fade In | `<` | X，不按肩键 | 给支持它的动作恢复参考推进；单策略还可能执行 blend-in。Tracker 特殊为从头开始。 |
| Fade Out | `>` | B，不按肩键 | 给支持它的动作停止参考推进；单策略还可能 blend-out。Tracker 特殊为默认站姿。**不是通用停走键。** |
| Motion Reset | `\|` | Y，不按肩键 | 重置动作时间/相位；tracker 为从头开始。不会扶起仿真机器人。 |
| 上一个 / 下一个 clip | `{` / `}` | 默认未配置 | 只对 PHC `MotionCtrl` 派生控制器的已加载 `.pkl` 内 clip 有效。 |

映射发出了命令，也要有对应消费者才会生效。例如 BeyondMimic/ASAP 模型内动作没有 `{ }` clip 切换；纯行走配置的 X/B/Y 会触发单策略通用 blend，不负责设置行走速度。AMO 的 Y 没有可用的站立切换功能。

<a id="custom-controls"></a>
### 4.3 替换默认键的配置

| 配置 | 实际触发键 | 默认键缺失情况 |
| --- | --- | --- |
| `g1_asap` | `i` 仿真重生，`o` shutdown，`r` 动作从头重置 | 没有 Esc、`< > \| { }`。 |
| `g1_asap_loco` | `i` 仿真重生，`o` shutdown；运动键见 [ASAP](#asap-movement) | 没有默认播放键和 Esc。 |
| `g1_protomotions_tracker` | `r` 或 `<` 开始/重播，`>` 回默认站姿，`i` 重生，`o` shutdown | 没有 Esc、`\|` 或 `{ }`，没有 GUI clip 选择。 |
| 专用 `g1_locomimic_*` 仿真 | `i/o` 重生/shutdown，`[/]` mimic/loco，`;/'` 下一/上一个待选动作 | 没有默认播放键和 Esc，详见 [组合控制](#locomimic-controls)。 |
| 专用 `g1_locomimic_*_real` | A shutdown，Select loco，Start mimic，R1/L1 下一/上一个待选动作 | 没有 X/B/Y 播放映射；肩键直接按。 |

这里“专用”指 `g1_loco_mimic_cfg.py` 中的 BeyondMimic/ASAP/full 配置。基础 `g1_locomimic` 使用 `triggers_extra`，仍保留默认键表。

<a id="unitree-movement"></a>
### 4.4 Unitree 运动

适用：`g1`、`g1_real`、`g1_dev`、`h1`、`h1_real`、`g1_switch` 的策略 0、`h1_switch` 的策略 0、基础 `g1_locomimic` 的 loco。

| 输入 | 平移 / 转向 | 当前指令幅度 |
| --- | --- | --- |
| 左杆上下 `LeftY` | 前后 | ±0.8 m/s。 |
| 左杆左右 `LeftX` | 横移 | ±0.5 m/s；轴正向映射负横移。 |
| 右杆左右 `RightX` | 转向 | ±1.57 rad/s；轴正向映射负 yaw。 |
| 键盘 `w/s`、`a/d`、`q/e` | 前后、横移、转向 | 当前实现采用 1.5 倍输入：幅度分别为 ±1.2 m/s、±0.75 m/s、±2.355 rad/s；`a/q` 为正横移/正 yaw。 |

摇杆回中给零速度参考；右杆上下不用。USB 的 Y 轴在输入层反转，向上推左杆得到正 `LeftY`；原装遥控直接读取无线数据，实际轴方向应按设备核对。

**键盘是事件式控制**：每次查询先清零，只在收到按下或系统重复按键事件的帧产生速度，无事件帧归零；不能按持续 held-state 控制理解，也不能保证长按产生稳定速度。

该策略按 controller 顺序选中第一个键盘/手柄分支，即使它没有事件也不继续尝试后面的输入：

| 配置 | 实际运动来源 |
| --- | --- |
| `g1` / `g1_real` / `h1_real` / `g1_switch` 策略 0 | 对应的 USB 手柄或原装遥控器。 |
| `g1_dev` | 键盘。 |
| `h1` | USB 手柄排在键盘前；WASD/QE 不用于运动，键盘触发命令仍有效。 |
| `h1_switch` 策略 0 / `g1_locomimic` loco | 键盘排在手柄前；手柄仍可发切换/退出等触发命令，摇杆不用于 Unitree 运动。 |

源码：[UnitreePolicy](robojudo/policy/unitree_policy.py)、[速度映射配置](robojudo/policy/policy_cfgs.py)。

<a id="asap-movement"></a>
### 4.5 ASAP locomotion 运动

适用：`g1_asap_loco` 和 `g1_locomimic_asap*` 的 loco 阶段。初始为 standing，速度为零。

| 操作 | 键盘 | 原装遥控器 / 手柄输入 |
| --- | --- | --- |
| 切换 standing / moving | `=` | 十字键 Left。 |
| 前后 | `w/s` 每次 ±0.1 m/s | 左杆上下，±0.5 m/s。 |
| 横移 | `a/d` 每次 ±0.1 m/s | 左杆左右，轴正向映射 -0.5 m/s。 |
| 转向 | `q/e` 每次 **-/+0.1 rad/s** | 右杆左右，轴正向映射 -1 rad/s。 |
| 清零三项速度 | `z` | moving 时摇杆回中；也可切回 standing。 |
| 调整高度 | `1/2` 每次 **+/-0.05 m** | 十字键 Up/Down，每次 +/-0.05 m。 |

键盘速度按 press/repeat **累加，松键后保留**；先 `=` 进入 moving，再逐次按运动键，`z` 停移动。当前没有速度/高度限幅，不要靠长按累加来估计目标速度。切回 standing 会清零三项速度；键盘 q/e 仍能在 standing 时重新修改 yaw，故 standing 不是绝对不转向的保证。

原装遥控的三项摇杆输出乘 standing/moving 标志，moving 时才生效。当前专用仿真只启用键盘、专用真机只启用原装遥控器；修改 controller 顺序也会改变运动输入来源。

源码：[ASAP locomotion](robojudo/policy/asap_policy.py)。

<a id="amo-movement"></a>
### 4.6 AMO 运动

AMO **只消费 USB 手柄或原装遥控器，不消费键盘 WASD**。这意味着 `g1_locomimic_beyondmimic` 虽能用键盘切换动作，当前默认配置却不能用键盘控制 loco 平移。要改变它，需要显式修改配置中的 controller，不能靠传 CLI 参数开启。

| 轴 | 当前映射 |
| --- | --- |
| `LeftY` | 平移命令槽 `cmd[0]`：-1 / 0 / +1。 |
| `LeftX` | 另一平移命令槽 `cmd[2]`：+0.8 / 0 / -0.8。 |
| `RightX` | 转向参考槽 `cmd[1]`：+0.2 / 0 / -0.2；源码用 `dyaw=-cmd[1]` 构造朝向误差，单位为 rad，**不是 rad/s 角速度**。 |
| `RightY` | 当前未启用高度控制；高度命令默认 0.75。 |

左杆控制平移、右杆横轴控制朝向参考。表中保留源码命令槽，避免把配置注释中的 x/y 顺序当成统一的物理速度定义。默认 Y 会先作为动作重置命令被消费；不能将它当作 AMO 站立开关。

源码：[AMOPolicy](robojudo/policy/amo_policy.py)、[G1 AMO 配置](robojudo/config/g1/policy/g1_amo_policy_cfg.py)。

<a id="smooth-movement"></a>
### 4.7 H1 Smooth 运动

适用：`h1_dev` 和 `h1_switch` 的策略 1。只消费摇杆，键盘 WASD 不控制运动。

| 轴 | 负端 / 中位 / 正端参考 |
| --- | --- |
| `LeftY` → vx | -0.5 / **0.1** / 1.0 m/s。 |
| `LeftX` → vy | +0.25 / **0.05** / -0.25 m/s。 |
| `RightX` → yaw | 3.0 / **1.5** / 0 rad/s。 |

**当前配置摇杆居中仍有非零运动参考，松杆不等于停走。** 需要零中位时应修改 `H1SmoothPolicyCfg.commands_map` 并自行验证模型行为。源码：[SmoothPolicy](robojudo/policy/smooth_policy.py)、[H1 Smooth 配置](robojudo/config/h1/policy/h1_smooth_policy_cfg.py)。

<a id="switch-controls"></a>
### 4.8 普通多策略切换：Multi

初始策略为 0。

| 配置 | 键盘选择 | USB 手柄选择 | 策略 ID |
| --- | --- | --- | --- |
| `g1_switch` | 未启用键盘 | 按住 RB，再按十字键 Down / Up | 0 Unitree / 1 AMO。 |
| `g1_switch_beyondmimic` | Tab 循环；`! @ # $` 直选，美式布局为 Shift+1/2/3/4 | 按住 RB，再按 Down / Left / Up / Right | 0 AMO / 1 Violin / 2 Waltz / 3 Dance_wose。 |
| `h1_switch` | Tab 循环 | **当前配置的 `L1+Y` 无效**：USB 输入只会产生 LB/RB 命名 | 0 Unitree / 1 Smooth；使用键盘切换。 |

选择目标后，pipeline 重置目标策略并预热 10 个策略步，50 Hz 时约 0.2 s 后交接；这不是 LocoMimic 的姿态插值。切到 BeyondMimic 后不会因为动作结束而自动切回 AMO，需要手动选择策略 0。

源码：[多策略 pipeline](robojudo/pipeline/rl_multi_policy_pipeline.py)。

<a id="locomimic-controls"></a>
### 4.9 行走 / 模仿组合：LocoMimic

初始为 **loco**，待选 mimic ID 为 **0**。“选择动作”与“执行动作”是两次操作。

| 配置族 | 进入 mimic / 返回 loco | 下一 / 上一个待选 mimic | 重生 / shutdown |
| --- | --- | --- | --- |
| 基础 `g1_locomimic` | 键盘 `[` / `]`；或 USB RB+Up / RB+Down | 默认未配置；只有一个 CR7 mimic | 保留默认键盘和手柄触发。 |
| 专用 BeyondMimic、ASAP、ASAP full 仿真 | `[` / `]` | `;` / 单引号 `'` | `i` / `o`。 |
| 专用 BeyondMimic、ASAP 真机 | Start / Select | **单按** R1 / L1 | 无仿真重生；A shutdown。 |

待选动作顺序见启动清单，完整 ASAP 则见 [YAML 清单](#full-asap)。**只允许在 loco 中选下一个/上一个动作**；正在 mimic 时切选会被拒绝。操作顺序为：回 loco → 等过渡完成 → 选动作并看日志 → 进入 mimic。

进入 mimic 会重置所选动作，从起始姿势重新执行。默认 loco→mimic 分为 `[0,75,25]` 个策略步，mimic→loco 为 `[25,75,0]` 步，50 Hz 下各约 2 秒；分次操作并等待过渡完成。

动作结束行为取决于策略：ASAP 到配置的 `motion_length_s` 后自动回 loco；BeyondMimic 只有正的 `max_timestep` 到限时才会自动回 loco。当前组合的 Violin/Waltz 分别为 500/850 步，Dance_wose 的默认 `max_timestep=0` 不报告完成，需手动回 loco。

源码：[LocoMimic pipeline](robojudo/pipeline/rl_loco_mimic_pipeline.py)、[专用配置](robojudo/config/g1/g1_loco_mimic_cfg.py)。

<a id="phc-controls"></a>
### 4.10 PHC 格式参考与控制窗口

适用：`g1_h2h`、`h1_h2h`、`g1_kungfubot2`。默认窗口提供：

| GUI | 等价键盘操作 | 含义 |
| --- | --- | --- |
| Fade In | `<` | 逐步增加参考播放速率至目标速率。 |
| Fade Out | `>` | 逐步降低参考播放速率至 0。 |
| Reset Progress | `\|` | 时间回 0、重置平移 offset；**不改变当前速率**。 |
| Switch Motion ID：输入数字后 Enter / Confirm | `{` / `}` 为前后 clip | 选择当前已加载 `.pkl` 内的 clip；不能选择另一个文件或模型。 |

H2H **初始暂停，目标 0.5 倍速**；Fade In 从 0 到目标约 1 秒。KungfuBot 构造时将速率设为 **1.0，即使开 GUI 也自动播放**。Fade 是参考速率变化；单策略入口还会执行下文的姿态 blend，二者不要混为一次模式切换。

GUI 不提供文件浏览器或任意时间 seek。只有一个 clip 的文件不会因为 Next 就出现另一种动作。当前 PHC controller 不发送动作完成通知：播完查询保持末帧，不自动循环、不自动选下一个，也不自动回 loco。Reset 后若原本速率为零，还需 Fade In 才能播放。

源码：[MotionCtrl](robojudo/controller/motion_ctrl.py)、[H2H](robojudo/controller/motion_h2h_ctrl.py)、[KungfuBot](robojudo/controller/motion_kungfubot_ctrl.py)、[GUI](robojudo/controller/utils/motion_gui.py)。

<a id="recipes"></a>
## 5. 具体操作步骤

### 5.1 基础行走与启动状态

1. 从启动清单选配置、准备对应模型和输入设备。`g1` 是 USB 手柄配置，想使用其默认键盘实验入口可选 `g1_dev`，但其环境为 23-DOF，需自行验证兼容性。
2. 仿真直接进入主循环，**不会执行 `prepare()`**。真机完成连接后自动 `prepare()`：默认约 3 秒关节 ramp，再约 5 秒策略 blend，然后进入主循环。两个入口在这里均没有 Enter 确认。
3. 普通 Unitree 真机或手柄仿真：左杆平移、右杆横轴转向，回中使速度参考归零。不要把 B 当停走；B 属于 Fade Out。
4. ASAP 键盘：先 `=` 进入 moving，逐次按 WASD/QE；用 `z` 清零速度，必要时 `=` 回 standing。松键后速度保留。
5. H1 Smooth 使用前先阅读 [非零中位说明](#smooth-movement)，不能套用摇杆回中即停的操作。
6. 结束时使用该配置的 shutdown 操作，见 [停止和退出](#stop)。

<a id="standalone-mimic"></a>
### 5.2 单策略 Mimic

| 方案 | 启动后的状态 | 开始 / 重播 | 停止或结束 |
| --- | --- | --- | --- |
| H2H：`g1_h2h`、`h1_h2h` | 参考停在首帧 | `<` / GUI Fade In 半速播放；`\|` / Reset Progress 回首帧，必要时再 Fade In | `>` / GUI Fade Out 渐停；末尾保持末帧，无自动循环。 |
| KungfuBot：`g1_kungfubot2` | 参考自动 1 倍速推进 | `\|` 重置时间，`<` 恢复速率 | `>` 渐停；末尾保持末帧。 |
| 模型内 BeyondMimic：`g1_beyondmimic` | `Jump_wose` 自动推进 | `\|` 从配置的起始帧重播，`<` 恢复相位推进 | `>` 停相位并触发单策略 blend-out；140 步到限后报告完成。 |
| 外部 BeyondMimic：`g1_beyondmimic_with_ctrl` | `.npz` controller 初始 `playing=False` | `<` 开始；`\|` 回第 0 帧但不改变 playing，原本暂停时仍需 `<` | `>` 暂停参考并触发单策略 blend-out；末尾保持末帧，无完成通知。 |
| ASAP：`g1_asap` | CR7 自动推进 | `r` 从头重播 | 配置时长结束后报告完成；只有 `i/o/r`，没有默认 `< >`。 |

普通单策略收到 Reset 或 Fade In 会执行默认约 **3 秒 blend-in**；Fade Out 或普通策略的完成通知会执行约 **5 秒 blend-out**，目标为 pipeline 的初始化姿态。该姿态可能是动作首帧，不能一概当作稳定站姿。只有 blend-in 期间跳过通常的 post-step 回调；blend-out 仍执行主循环和回调，动作时钟是否推进取决于策略/controller 自身的暂停状态。

ASAP 与模型内 BeyondMimic 的 Fade In/Out 直接将相位速率设为 1/0；PHC 的 Fade 是渐变参考速率。Multi 和 LocoMimic 重写了单策略的后处理，不套用这套自动 blend-out 行为。

### 5.3 普通多策略切换

以 `g1_switch_beyondmimic` 为例：

1. 启动后处于策略 0 AMO，用 USB 手柄控制运动。
2. 将运动输入归中，再用 Tab、`! @ # $` 或 RB+十字键选择策略。按 [策略 ID 表](#switch-controls) 确认目标。
3. 等约 10 个策略步预热并完成交接；动作从目标策略重置位置开始。
4. 要回 AMO，手动选择 0。多策略 pipeline 不会因 BeyondMimic 完成而自动返回。

`g1_switch` 初始是 Unitree，使用 RB+Down/Up 直选；`h1_switch` 用 Tab，切换后运动输入也从 Unitree 键盘变为 Smooth 手柄。

### 5.4 Locomotion / Mimic 组合

键盘 `g1_locomimic_asap`：

1. 启动后处于 loco。`=` 进入 moving，逐次设速度；执行 mimic 前用 `z` 清零并回 standing。
2. 在 loco 中用 `;` / `'` 选择 CR7、robomimic、kongfu，观察待选日志。选择本身不执行动作。
3. 松开 `[` 开始所选 mimic，等待约 2 秒过渡完成。
4. ASAP 完成后自动返回 loco；也可 `]` 提前返回。等回到 loco 后才能选下一个 mimic。
5. `i` 重生仿真，`o` shutdown；这些配置没有 Esc 和默认播放键。

真机 `g1_locomimic_asap_real`：

1. 完成 SDK/网卡设置并启动，等待自动 prepare。Select 返回 loco，等过渡完成。
2. 十字键 Left 切 standing/moving，摇杆控制移动；执行动作前使输入归中并回 standing。
3. 单按 R1/L1 选择下一/上一个待选 mimic，再按 Start 执行；**不需要肩键组合**。
4. 播完自动回 loco，或 Select 提前返回；A shutdown。X/B/Y 在这里没有播放映射。

BeyondMimic 组合使用同样的选择/执行流程，但默认 Dance_wose 不自动返回；用 `]` / Select 返回。仿真 `g1_locomimic_beyondmimic` 当前没有 AMO 键盘运动输入；真机版本使用原装遥控器控制 AMO。

<a id="tracker"></a>
### 5.5 ProtoMotions tracker

1. 使用 [tracker 启动命令](#cli) 明确指定 `.pt` 动作库，可选 `--motion-index`；默认模型与同名 YAML 已提供。
2. 仿真由入口直接开启默认站姿参考；真机完成 prepare 后保持默认站姿参考。此时动作未播放。
3. **仿真**按 `r` 或 `<`；**真机**在不按 L1/R1 时按 X 或 Y：取消默认站姿，从动作第 0 帧开始。真机配置没有键盘监听，日志中的“press R”不适用于它。
4. 仿真 `>` 或真机 B 返回默认站姿参考。再次开始会从第 0 帧重播，不能从暂停处续播；已经 active 的 tracker 重播时也不会额外执行一次姿态 blend。
5. 选定动作到末帧后自动回默认站姿，不自动循环或播放下一条；要换动作索引，修改参数后重新启动。
6. 仿真 `i` 重生、`o` shutdown；真机 A shutdown。

源码：[tracker 策略](robojudo/policy/protomotions_tracker_policy.py)、[单策略状态处理](robojudo/pipeline/rl_pipeline.py)。

<a id="twist"></a>
### 5.6 TWIST Redis

当前 `g1_twist` 只启用 `TwistRedisCtrl`，连接 `localhost:6379`、DB 0、键 `action_mimic_g1`。生产者必须持续写入与 TWIST 策略匹配的 `action_mimic` 数据。

启动前先准备 Redis 客户端、服务和生产者。Controller 构造时会等待首帧，**没有首帧就不能完成初始化**。之后断流会保留最后数据，不会自动停止播放或关机。当前没有默认键盘、手柄、本地 PHC 窗口或 next/reset/stop 映射；结束仿真进程用终端 Ctrl+C。

本地 `MotionTwistCtrl` 虽存在，其配置在 `g1_twist` 中被注释，不能把它的 PHC GUI 操作当成当前默认能力。协议和读取逻辑见 [Redis controller](robojudo/controller/twist_redis_ctrl.py)、[TWIST 策略](robojudo/policy/twist_policy.py)。

<a id="stop"></a>
### 5.7 重生、重置、停移动与退出

| 目的 | 应使用的操作 | 当前效果 |
| --- | --- | --- |
| 停移动 | 对应策略的零速度输入；ASAP 键盘用 `z` | 只改变运动参考；H1 Smooth 中位例外见上文。 |
| 仿真机器人重生 | 默认键盘反引号，或专用配置的 `i` | MuJoCo keyframe 0 重置姿态和状态；不是动作重播。单策略还调用对齐重置，Multi/LocoMimic 没有同样的处理。 |
| 动作从头 | 对应 Reset、tracker 的开始键，或重新进入 mimic | 改动作时间/相位；不会将倒下的仿真机器人扶起。 |
| 仿真 shutdown | 对应 Esc / `o` / 手柄 A | 关闭 viewer；此方法没有终止 Python 主循环，不保证进程同时结束。 |
| 真机 shutdown | 当前配置的遥控器 A | Python 后端发送阻尼并禁用；C++ 后端禁用并发送 `kp=0, kd=5` 阻尼命令；不是保持站立。禁用后不能靠 X/Y 自动恢复。 |
| 结束 Python 进程 | 终端 Ctrl+C | 与 controller 的 shutdown 是两个操作。真机应先执行上面的 shutdown，再结束进程；Ctrl+C 本身不等于已发送阻尼。 |

<a id="customization"></a>
## 6. 修改模型、动作、网卡和 Controller

除 tracker 的三个覆盖参数外，修改以下内容需要编辑所选配置及其引用的配置类。也可新增带注册装饰器的配置类，并确保被 [配置包](robojudo/config/__init__.py) 导入；只有注册后新名称才能用于 `-c`。

| 修改目标 | 修改位置与字段 | 注意事项 |
| --- | --- | --- |
| 真机网卡 | 启动清单链接的配置中 `env.unitree.net_if`；默认类见 [G1 real env](robojudo/config/g1/env/g1_real_env_cfg.py)、[H1 real env](robojudo/config/h1/env/h1_real_env_cfg.py) | 顶层配置可能重新构造 `unitree`，应以选定配置的最终值为准。没有 `--net-if`。 |
| 后端、仿真机器人 | `env.env_type`、仿真 `env.xml`，对应 [环境配置](robojudo/environment/env_cfgs.py) | `UnitreeCppEnv` / `UnitreeEnv` 的依赖不同；仅改 uv extra 不会改后端。机器人 DOF/顺序必须与策略一致。 |
| 单/多/组合策略 | 所选配置的 `policy`、`policies`，或 `loco_policy` / `mimic_policies` | 列表顺序决定策略 ID；初始普通策略为 0，组合初始为 loco、待选 mimic 为 0。 |
| Unitree/H2H/Smooth 模型 | 对应 policy 配置的 `policy_name` 与 `policy_file` 属性 | 默认路径按 `assets/models/{robot}/{策略族}/...` 解析；见 [策略路径定义](robojudo/policy/policy_cfgs.py)。 |
| AMO 模型 | [G1 AMO 配置](robojudo/config/g1/policy/g1_amo_policy_cfg.py) 及其 `policy_file` / adapter 路径 | 不要遗漏 `adapter_jit.pt` 和 `adapter_norm_stats.pt`。 |
| ASAP / BeyondMimic / KungfuBot 模型 | 启动清单中的 policy 配置，以及其 `policy_name` / ONNX 路径字段 | BeyondMimic 的模型 metadata、`without_state_estimator`、`use_motion_from_model` 等必须与导出模型匹配。不要只改文件名。 |
| PHC `.pkl` 参考 | 对应 motion controller 的 `motion_name` / `motion_path`，见 [G1 motion 配置](robojudo/config/g1/ctrl/g1_motion_ctrl_cfg.py) | G1 H2H 使用 `phc_29`，KungfuBot 使用 `phc`；GUI clip ID 不更换文件。机器人 YAML/MJCF 是仓库内置资源。 |
| BeyondMimic 外部 `.npz` | `BeyondMimicCtrlCfg.motion_name`，见 [controller 配置](robojudo/controller/ctrl_cfgs.py) | 需同时启用该 controller，并将 policy 的 `use_motion_from_model=False`；动作与模型匹配。 |
| Tracker | [tracker 配置](robojudo/config/g1/policy/g1_protomotions_tracker_cfg.py) 的 `onnx_path` / `onnx_name`、`motion_path`、`motion_index` | 可用专用入口覆盖；更换 ONNX 时配套同名 YAML。 |
| 完整 ASAP 动作列表 | [asap.yaml](robojudo/config/g1/asap.yaml) 的 `mimic_models` | 构造器按 YAML 顺序生成 mimic 列表，模型路径、时长、上身初始姿态一起核对。 |
| 输入设备和按键 | 顶层 `ctrl` 列表、各 controller 的 `triggers` / `triggers_extra` / `combination_init_buttons` | 更换顺序可能改变运动输入；`triggers` 替换默认表，`triggers_extra` 补充。键盘的 Ctrl 门控字段当前未实现。 |
| 运动尺度、初始指令 | 对应 policy 的 `commands_map`、`max_cmd` 及策略实现 | Unitree、ASAP、AMO、Smooth 语义不同；不能互换表中的单位与中位值。 |
| 时序和执行开关 | 策略的 `freq`，顶层 [pipeline 配置](robojudo/pipeline/pipeline_cfgs.py) 的 `run_fullspeed` / `do_safety_check`，环境的 `sim_dt` / `sim_decimation` 或 `unitree.control_dt` / `act` | 均不是现有脚本 CLI 参数；真机不要用仿真全速运行方式替代实时控制。 |

<a id="assets"></a>
## 7. 模型与动作资源现状

以下路径在 **2026-10-21 当前工作区存在**。路径存在不代表模型维度、元数据或真机动作稳定性已经验证。默认环境 XML 为 [G1 29-DOF](assets/robots/g1/g1_29dof_rev_1_0.xml)、[G1 23-DOF](assets/robots/g1/g1_23dof_rev_1_0.xml)、[H1](assets/robots/h1/h1.xml)，所用 FK 文件也已存在。

| 策略 / 参考 | 默认文件 |
| --- | --- |
| G1 Unitree | `assets/models/g1/unitree/policy_lstm_1.pt`。 |
| G1 AMO | `assets/models/g1/amo/amo_jit.pt`；companion 为 `adapter_jit.pt`、`adapter_norm_stats.pt`，均在同目录。 |
| G1 ASAP-loco | `assets/models/g1/asap/dec_loco/20250109_231507-noDR_rand_history_loco_stand_height_noise-decoupled_locomotion-g1_29dof/model_6600.onnx`。 |
| G1 ASAP mimic | `assets/models/g1/asap/mimic/CR7_level1/model_191500.onnx`；`robomimic/dance_0605.onnx`；`kongfu/horse_squat.onnx`，后两项同属 `assets/models/g1/asap/mimic/`。 |
| G1 BeyondMimic | `assets/models/g1/beyondmimic/Jump_wose.onnx`、`Dance_wose.onnx`、`Violin.onnx`、`Waltz.onnx`。基础 Jump 使用模型内动作；外部参考是 `assets/motions/g1/beyondmimic/dance1_subject2.npz`。 |
| G1 H2H | `assets/models/g1/h2h/h2h.pt`；参考 `assets/motions/g1/phc_29/singles/0-KIT_6_WalkInCounterClockwiseCircle05_1_poses.pkl`。 |
| G1 KungfuBot2 | `assets/models/g1/kungfubot2/horse_test_43000.onnx`；参考 `assets/motions/g1/phc/kungfubot/Horse-stance_pose.pkl`。 |
| G1 TWIST | `assets/models/g1/twist/twist_general_motion_tracker.pt`；默认参考来自 Redis。 |
| G1 tracker | `assets/models/g1/protomotions_tracker/unified_pipeline.onnx` 与 `unified_pipeline.yaml`；提供的动作示例 `assets/motions/g1/g1_bones_seed_mini.pt`。 |
| H1 Unitree | `assets/models/h1/unitree/motion.pt`。 |
| H1 Smooth | `assets/models/h1/smooth/train_default-14000-jit.pt`。 |
| H1 H2H | `assets/models/h1/h2h/h2h_release.pt`；参考 `assets/motions/h1/phc/singles/0-KIT_572_punch_right01_poses.pkl`。 |

PHC 格式参考使用以下内置配置；各 YAML 引用的 MJCF 也在对应 `robojudo/motion/resources/assets/robot/` 下，无外部 PHC checkout 依赖：

| 参考机器人 | 内置 YAML | 对应 MJCF |
| --- | --- | --- |
| G1 H2H 29-DOF | [unitree_g1_29dof.yaml](robojudo/motion/resources/config/robot/unitree_g1_29dof.yaml) | [g1_29dof_rev_1_0.xml](robojudo/motion/resources/assets/robot/unitree_g1/g1_29dof_rev_1_0.xml) |
| G1 KungfuBot 23-DOF | [unitree_g1_23dof_KungfuBot.yaml](robojudo/motion/resources/config/robot/unitree_g1_23dof_KungfuBot.yaml) | [g1_23dof_lock_wrist_fitmotionONLY.xml](robojudo/motion/resources/assets/robot/unitree_g1/g1_23dof_lock_wrist_fitmotionONLY.xml) |
| H1 | [unitree_h1.yaml](robojudo/motion/resources/config/robot/unitree_h1.yaml) | [h1.xml](robojudo/motion/resources/assets/robot/unitree_h1/h1.xml) |

<a id="full-asap"></a>
### 7.1 完整 ASAP：注册成功，但当前文件不齐

`g1_locomimic_asap_full` 从 [asap.yaml](robojudo/config/g1/asap.yaml) 展开以下 14 个 mimic。路径均相对于 `assets/models/g1/asap/mimic/`；只有 CR7 现有，另外 **13 个缺失**。启动会准备这些策略，不能因为只想选 CR7 就忽略其它缺失项。

| mimic ID | 目录 / 模型文件 | 当前状态 |
| --- | --- | --- |
| 0 | `APT_level1/model_176500.onnx` | 缺失。 |
| 1 | `CR7_level1/model_191500.onnx` | 存在。 |
| 2 | `jump_forward_level1/model_191500.onnx` | 缺失。 |
| 3 | `jump_forward_level2/model_130500.onnx` | 缺失。 |
| 4 | `jump_forward_level3/model_149000.onnx` | 缺失。 |
| 5 | `kick_level1/model_168000.onnx` | 缺失。 |
| 6 | `kick_level2/model_293000.onnx` | 缺失。 |
| 7 | `kick_level3/model_240000.onnx` | 缺失。 |
| 8 | `Kobe_level1/model_193000.onnx` | 缺失。 |
| 9 | `lebron_level1/model_233500.onnx` | 缺失。 |
| 10 | `lebron_level2/model_190000.onnx` | 缺失。 |
| 11 | `side_jump_level1/model_135000.onnx` | 缺失。 |
| 12 | `side_jump_level2/model_131500.onnx` | 缺失。 |
| 13 | `side_jump_level3/model_245000.onnx` | 缺失。 |

补齐 YAML 指定文件，或明确修改列表及对应时长/姿态后再使用；文件齐备的三个动作组合可选 `g1_locomimic_asap`。

<a id="maintenance"></a>
## 8. 现有限制与维护

当前会影响启动或操作的已知事项：tracker 默认 `motion_path` 为空；完整 ASAP 缺 13 个模型；本次检查的 `.venv` 未安装 `redis` 和 `unitree_sdk2py`；`h1_switch` 的 USB `L1+Y` 不匹配实际按键名；AMO 没有键盘运动输入；Unitree 按 controller 顺序只取第一个运动输入；H1 Smooth 摇杆中位非零。以上按现有实现记录，本手册不修改这些行为。

新增配置、修改入口参数、controller 映射或策略输入后，维护者同步更新本文件的启动清单、操作说明、资源前提及核对日期。可在已准备的环境里运行以下只读检查；它们不创建 pipeline、controller、policy、环境或网络连接：

```bash
.venv/bin/python scripts/run_pipeline.py --help
.venv/bin/python scripts/run_tracker_pipeline.py --help

# 只构造配置，打印注册名、后端、pipeline 和 controller 顺序
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
from robojudo.config import cfg_registry
from robojudo.config.config_manager import ConfigManager

for name in cfg_registry.types:
    cfg = ConfigManager(name).get_cfg()
    print(name, cfg.env.env_type, cfg.pipeline_type,
          [ctrl.ctrl_type for ctrl in cfg.ctrl])
PY
```

维护时依次核对：

1. [配置注册入口](robojudo/config/__init__.py) 与本手册全部名称一一对应；不要把未导入或未注册的策略类列成可运行配置。
2. [G1 基础配置](robojudo/config/g1/g1_cfg.py)、[G1 专用组合配置](robojudo/config/g1/g1_loco_mimic_cfg.py)、[G1 实验配置](robojudo/config/g1/g1_custom_cfg.py)、[H1 基础配置](robojudo/config/h1/h1_cfg.py)、[H1 实验配置](robojudo/config/h1/h1_custom_cfg.py) 的后端、策略列表和 controller 顺序。
3. 两个脚本的实际 argparse 参数、[依赖 extras](pyproject.toml)，再核对配置字段，不从日志或旧注释推断 CLI 能力。
4. [默认/额外触发合并](robojudo/controller/base_ctrl.py)、输入层真正发出的键名、[控制数据顺序](robojudo/controller/ctrl_manager.py)，以及策略/pipeline 是否实际消费该命令。
5. 对应模型、metadata、adapter、动作和内置资源是否仍存在；缺失路径用代码文本标注，不建立指向不存在文件的链接。文件存在检查与实际运行验证分别记录。
6. Markdown 本地链接、锚点和 shell 参数仍有效；查看新增文件本身的空白错误，避免仅检查已跟踪文件。

内置动作库的来源和支持边界见 [Motion runtime 来源说明](robojudo/motion/SOURCE.md)；进一步架构资料见 [controller 文档](docs/controller.md)、[policy 文档](docs/policy.md)、[environment 文档](docs/environment.md)。
