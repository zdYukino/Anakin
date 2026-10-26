# 部署测试保留与精简依据

基线：已合并 release 6ba7bbf50546268c753c5c1686dc267e8df0ce0e；
部署提交 4d58df1bae9fe3358b3d92353e23a579f31a7a62。
先保存本依据，再删除已提交测试；历史版本可用 Git 正常恢复，不生成恢复包。

## 保留的风险覆盖

| 风险 | 保留位置 |
| --- | --- |
| 固定 lo/HG/G1，保持物理机器人默认值 | policy runner 配置、launcher 固定参数、make_env |
| 非有限动作/初始目标禁止发令；跌倒/后端禁用/进程退出失败 | 目标检查与控制循环 |
| 冻结/倒退回包、非法 IMU/电机数据、仿真时间不足 | StateMonitor 与控制循环 |
| 发令饥饿失败；持续发令的 blend 不误判或突发追赶 | target starvation / blocking blend |
| 被动读取即使失败也不能发控制或 shutdown | read mode 两条测试 |
| 首次反馈、四元数/FK、H2H 消费、关节映射 | native boundary + 独立 MuJoCo FK oracle；补充反馈/目标映射 |
| LSTM 复位、可选 reset_memory、Tracker 复位/朝向 | 真实 JIT replay、feedforward、pipeline、heading alignment |
| 活跃恢复保留平衡；reset/blend-out 维持原语义 | motion resume / reset / blend-out |
| RC 40 字节布局、按下/释放、保持去重、最新轴值 | 新内存 packet 测试，不连接输入设备 |
| 只操作自己的窗口、清理自己的进程 | own-window、failure cleanup、stub SIGTERM |

CRC 当前只有 C++ 源码实现，尚无独立 CRC 数值/原生通信测试，不声称已覆盖。
RC 内存测试不代表真实手柄、DDS 或真机验收。替身回包测试只验证判定逻辑；
物理稳定性另以官方 G1 闭环运行记录为证据。

## 删除或合并的依据

- 删除事件排序、输出路径碰撞、进度白名单/归属、CLI 摘要序列化等外围断言。
- 删除 reduced-FK 两个可选分支与 keyboard/tracker 参数覆盖；保留 23→29 主适配、H1 拒绝、Tracker 复位。
- 删除日志 flush 专项；保留后端前后发令饥饿、足够仿真时长、连续 blend 的主判定。
- 将初始发令顺序/安全恢复断言并入 fresh-world heading reset 测试。
- 删除悬空场景三条与合成响应分类三条；悬空台架不作为浮动 G1 验收。
- 删除 private-display 单独异常测试；保留真实 stub SIGTERM 清理及 runner 异常清理/显示恢复。
- 删除关闭 FK 可选路径与重复暂停参考测试。
- Tracker resume/reset 合为带 subTest 的一条，仍覆盖两个动作。
- PHC 数值/独立参考/控制器、viewer 回调与完整导入不属本轮部署测试删除范围，原样保留。
- 不改生产代码、模型、场景、配置、脚本、日志、原始验收报告或结果数据。
- 历史报告的 85 项、44 次运行等数字属于第一阶段基线，不改写为精简后的数量。

## 常规安全入口

从仓库根目录运行：

~~~bash
.venv/bin/python -m unittest tests.test_unitree_policy_runner tests.test_unitree_cpp_initial_state tests.test_unitree_policy_reset tests.test_pipeline_motion_resume tests.test_unitree_mujoco_launcher tests.test_unitree_mujoco_runner tests.test_unitree_remote
~~~

不启动真实仿真、DDS、GUI 或输入设备；launcher 生命周期只运行自建 Python stub。
PHC 代码或数据变化时，另跑 tests.test_phc_motionlib、tests.test_phc_reference、tests.test_phc_controllers。
viewer 和导入测试保留供各自模块变更时运行。

## 可重复的本机 G1 闭环

沿用 docs/unitree_policy_deployment.md 的 Unitree 60 秒命令及判定标准。
入口固定私有配置的 lo / DDS domain 0 / G1 HG 并启动自己的官方仿真器。
必须同时检查推进的反馈、有限 29 维目标、姿态/高度、足够仿真时长和真实控制次数。
本次精简不重跑；保留原始 unitree-walk60.json/jsonl 与持久化证据。
替身或中立 RC 回包不能证明闭环成功。

## 本次验证结果

部署测试由 60 项精简为 40 项，包含新增的 2 项 RC packet 与 1 项反馈/目标映射测试。
加上未改动的 25 项 PHC 回归，共 65 项通过（3.774 秒）；Ruff 0.12.7 lint/format 与 git diff --check 通过。
日志保存在原工作区 logs/unitree_policy/test-cleanup-validation-20261026.log。
未重跑真实仿真/真机试验，未修改生产代码或历史验收数据。

## 精确删除清单

### tests/test_unitree_policy_runner.py

- test_event_payloads_are_typed_and_ordered
- test_output_files_cannot_overwrite_each_other
- test_reduced_config_preserves_explicitly_disabled_fk_and_valid_torso
- test_reduced_config_torso_missing_from_native_model_uses_native_default
- test_tracker_overrides_and_keyboard_input
- test_target_monitor_uses_updated_policy_limits_after_switch
- test_progress_serializes_only_whitelisted_finite_scalars
- test_progress_belongs_to_the_policy_that_generated_the_frame
- test_log_flush_stall_is_part_of_control_gap_monitoring
- test_unconsumed_event_does_not_silently_pass
- test_initial_target_is_sent_before_reset_and_safety_is_restored
- test_main_saves_runtime_failure_with_stage

### tests/test_unitree_mujoco_runner.py

- test_correct_motion_with_gravity_bias_passes
- test_static_reversed_and_drifting_feedback_fail
- test_unrelated_oscillation_and_nonfinite_feedback_fail
- test_native_initialization_exit_zero_becomes_nonzero_failure

### tests/test_unitree_mujoco_launcher.py

- test_suspension_preserves_source_joint_actuator_and_sensor_order
- test_missing_free_joint_is_rejected
- test_wrong_motor_count_is_rejected
- test_private_display_stops_on_error_and_does_not_mutate_host_display

### tests/test_unitree_cpp_initial_state.py

- test_feedback_is_available_when_fk_is_explicitly_disabled

### tests/test_pipeline_motion_resume.py

- test_paused_reference_stays_paused_without_resume
