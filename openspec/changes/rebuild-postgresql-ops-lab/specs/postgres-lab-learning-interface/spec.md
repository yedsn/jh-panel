## ADDED Requirements

### Requirement: 用户入口脚本使用统一编号命名
系统 SHALL 仅提供十六个主学习入口脚本，文件名使用 `<组号>-<序号>.<功能域>-<动作>-<补充>.sh`，共享文件位于 `scripts/common/` 且不带编号和 `common-` 前缀。

#### Scenario: 通过编号定位脚本
- **WHEN** 学习者从 README 或 VS Code 看到编号 `2-2`
- **THEN** 可以直接定位到 `scripts/2-2.replication-standby-basebackup.sh`，且不存在同编号的其他主入口

### Requirement: 每个脚本保持单一职责和线性流程
每个用户入口脚本 SHALL 只执行其名称所描述的一个学习步骤，采用从上到下可读的固定流程，并避免自动角色发现、通用状态机、复杂 JSON 输出或把计划切换与故障转移合并。

#### Scenario: 阅读切换相关脚本
- **WHEN** 学习者分别打开 `4-1`、`4-2` 和 `4-3`
- **THEN** 可以分别看到计划切换、只停止主库、只提升从库的线性操作，而不是同一脚本中的隐藏分支

### Requirement: 教学日志解释动作和原理
每个入口脚本 SHALL 用中文输出任务目标、核心原理、编号步骤、固定目标、实际动作、验证依据和结果；PostgreSQL 核心命令 SHALL 在源码附近包含解释性注释。

#### Scenario: 执行基础备份或提升脚本
- **WHEN** 学习者从终端运行脚本
- **THEN** 无需先阅读实现即可知道当前在操作哪个节点、为什么执行该动作以及如何判断成功

### Requirement: VS Code 入口与真实脚本一致
`.vscode/launch.json` SHALL 为十六个主入口各提供一个 `node-terminal` 配置，显示名称以脚本编号开头，并按环境、复制初始化、复制测试、切换/故障、修复、pgBackRest 分组；配置级 MUST NOT 使用 `description` 字段。

#### Scenario: 从 VS Code 运行脚本
- **WHEN** 学习者选择任一调试配置
- **THEN** 配置在项目根目录执行编号一致的真实脚本，危险操作保持交互确认且不默认传递 `--yes`

### Requirement: README 是可执行的实验手册
README SHALL 说明架构、固定端口、密码来源、持久化目录、任意网段访问风险、脚本索引、初始复制流程、计划切换分支、故障转移分支、两种修复路径、pgBackRest 的 stanza/WAL/Full/Incremental/隔离恢复流程和预期状态，并明确单机 Demo 不等同于生产 HA。

#### Scenario: 学习者按手册从零实验
- **WHEN** 学习者从 `1-1` 开始按 README 顺序执行初始复制实验
- **THEN** 所有命令和文件路径真实存在，且每一步都有预期观察结果和失败后的下一步提示

### Requirement: 项目提供最小静态验证
系统 SHALL 提供 Shell 语法检查、两个节点 Compose 与恢复验证 Compose 配置检查，并验证 README、launch.json 与实际脚本编号和路径一致。

#### Scenario: 完成重建后运行静态检查
- **WHEN** 实施者执行项目测试
- **THEN** 所有入口脚本语法有效且可执行，两个节点 Compose 与恢复验证 Compose 均可解析，VS Code 和 README 不引用不存在的脚本
