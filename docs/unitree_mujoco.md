# 官方 G1 C++ 仿真联调

将官方 `unitree_mujoco` C++ 仿真器作为外部机器人通信端运行，通过 Anakin 现有的真机后端读取状态反馈，并测试全身 29 个关节。整个流程无需策略检查点或推理流水线。

## 启动与测试

在 Anakin 项目根目录下，打开一个终端启动仿真器：

```bash
.venv/bin/python scripts/run_unitree_mujoco.py --headless --suspended \
  --log logs/unitree_mujoco/simulator.log
```

`--headless` 会在独立的 1280 × 800 Xvfb 虚拟显示器中运行正常的 C++ 图形界面。若桌面显示正常，可以省略该参数，直接显示仿真窗口。联调会话中的 Xwayland 显示器报告的分辨率为 0 × 0，导致上游 GLFW 创建窗口失败；使用虚拟显示器可以解决该问题，无需更改桌面配置。

`--suspended` 会在 `build/unitree_mujoco-scene/` 下生成测试场景，将骨盆约束在世界坐标系中 1.2 米高的位置。模型保留原有的自由关节、29 个执行器、关节顺序、传感器、重力和关节动力学。这是一项无需平衡控制器的关节台架测试。省略 `--suspended` 后使用原始浮动基座地面场景；原始 XML 文件不会被修改。

在另一个终端中，读取状态 5 秒：

```bash
.venv/bin/python scripts/test_unitree_mujoco.py \
  --summary logs/unitree_mujoco/read.json
```

保持悬空场景运行，随后执行全身关节测试：

```bash
.venv/bin/python scripts/test_unitree_mujoco.py --mode joints \
  --summary logs/unitree_mujoco/joints.json \
  --log logs/unitree_mujoco/joints.jsonl
```

初始化完成后，全身关节测试约需 105 秒。脚本先从实测姿态平滑过渡到 Anakin 的默认姿态，再依次让每个关节在配置限位内完成最大幅度为 0.08 弧度的平滑正反向运动，其余关节保持默认目标。每个关节都会输出实际运动幅度、指令与反馈的相关性、回位偏差和相对跟踪误差。只有全部 29 个关节响应通过检查，测试才算成功；反馈无效、过期或关节响应不合格时，脚本以非零状态退出。

只读模式不会调用 `step()` 或 `shutdown()`，因为原生 `shutdown()` 本身也会发布阻尼指令。关节模式在结束时发布阻尼指令。按 Ctrl-C 可以停止启动器及其仿真器、Xvfb 子进程。

## 通信约定

两个脚本均仅使用本机回环接口：

| 配置项 | 取值 |
| --- | --- |
| 网络接口 | `lo` |
| DDS 域 | `0` |
| 控制后端 | `G1RealEnvCfg` + `UnitreeCppEnv` + 原生 `unitree_cpp` |
| 控制指令 | `rt/lowcmd`，`unitree_hg::msg::dds_::LowCmd_` |
| 状态反馈 | `rt/lowstate`，`unitree_hg::msg::dds_::LowState_` |
| 仿真位置与速度 | `rt/sportmodestate`，`unitree_go::msg::dds_::SportModeState_` |
| G1 模型 | `scene_29dof.xml`，`mode_machine = 5` |

Anakin 的原生控制器目前将 DDS 域固定为 0，因此启动器会覆盖上游默认的域 1。仿真器发布 `rt/sportmodestate`，而 Anakin 的 G1 真机配置默认订阅 `rt/odommodestate`。测试脚本仅在本地覆盖该话题，不更改真机的默认配置。

原生读取器在提供反馈前会校验 LowState 的 CRC。测试脚本检查 29 个关节的位置、速度和估计力矩，IMU 的四元数、陀螺仪、加速度计及横滚、俯仰、偏航角（RPY），以及位置、速度和持续递增的 LowState 时间戳。SDK 原始四元数的分量顺序为 WXYZ，环境对外提供的顺序为 XYZW。JSONL 记录中包含控制指令和实测反馈。

由于仿真器未实现相应的 RPC 服务，SDK 的 MotionSwitcher 初始化可能需要约 5 秒。本次联调验证的是电机、IMU 和位置相关的 DDS 通信，不涵盖机器人固件中的高层运动服务。

## 本机编译

现有源码位于同级目录 `../unitree_mujoco`，版本提交为 `1eb6642e3f3fdfb7fb13a9794fd6a2dd93ea0e7d`。编译生成的可执行文件位于 `../unitree_mujoco/simulate/build/unitree_mujoco`。

本机使用的依赖如下：

- 已安装在 `/usr/local` 下的真实 Unitree SDK2。
- 系统中的 GCC、CMake、Boost program_options、yaml-cpp 和 fmt 开发文件。
- 官方 MuJoCo 3.3.6 Linux x86_64 发行包，包含 `simulate` 源码，已解压至 `build/unitree_mujoco-deps/mujoco-3.3.6`。
- Ubuntu Jammy 的 `libglfw3` 和 `libglfw3-dev` 3.3.6-1 软件包，已解压至 `build/unitree_mujoco-deps/glfw`，未安装到系统目录。
- 用于虚拟显示器的 Ubuntu Xvfb 软件包，已解压至 `build/unitree_mujoco-deps/xvfb`。启动器也支持使用系统安装的 `Xvfb`。

被 Git 忽略的符号链接 `../unitree_mujoco/simulate/mujoco` 指向本地 MuJoCo 发行包。其 `include/GLFW/glfw3.h` 和 `lib/libglfw.so` 链接到解压后的 Ubuntu GLFW 文件；`lib/libglfw.so.3` 链接到 `libglfw.so`。

使用现有依赖目录重新编译：

```bash
cmake -S ../unitree_mujoco/simulate \
  -B ../unitree_mujoco/simulate/build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_BUILD_RPATH="$PWD/build/unitree_mujoco-deps/mujoco-3.3.6/lib"
cmake --build ../unitree_mujoco/simulate/build -j 4
```

本次联调无需为官方 C++ 源码或 Anakin 原生后端打补丁。使用该编译结果时，请保留依赖目录，因为可执行文件通过构建时设置的 RPATH 查找 MuJoCo 和 GLFW。

## 验证结果与文件

运行结果保存在被 Git 忽略的 `logs/unitree_mujoco/` 目录下：

- `existing-example-state.json`：使用现有的 `packages/unitree_cpp/example/unitree_cpp_env.py` 进行被动状态读取，网络接口配置为 `lo`，并使用仿真器的运动状态话题。
- `read-ground.json`：在原始地面场景中执行限时状态验证的结果。
- `joints.json` 和 `joints.jsonl`：悬空场景中完整的 29 关节响应报告与采样数据。
- `read-launcher.json`：使用本文启动器启动仿真后，通过原生后端读取反馈的结果。
- `no-simulator.json`：没有仿真器发布反馈时，脚本按预期以非零状态退出的验证结果。
- `simulator.png`：独立虚拟显示器中实际运行的 C++ 仿真窗口截图。

2026 年 10 月 21 日的验证结果：现有示例读取了 20 帧状态；地面场景读取器采集了 301 帧状态；全部 29 个关节测试通过，共采集 10,501 帧状态，覆盖 105,022 毫秒仿真时间。指令与反馈的最低相关系数为 0.938，最大相对跟踪均方根误差（RMSE）为 0.0213 弧度。随后又使用本文启动器采集了 201 帧反馈，验证启动流程。全部 16 项专项测试以及 Ruff 0.12.7 代码检查和格式检查均已通过。

运行专项检查：

```bash
.venv/bin/python -m unittest tests.test_unitree_mujoco_runner tests.test_unitree_mujoco_launcher
```
