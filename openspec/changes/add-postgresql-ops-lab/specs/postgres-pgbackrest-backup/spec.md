## ADDED Requirements

### Requirement: pgBackRest stanza 与 WAL 归档
系统 SHALL 为学习实例配置一个持久化 pgBackRest 仓库和 stanza，并配置当前主库通过 `archive_command` 持续归档 WAL。

#### Scenario: 初始化 stanza
- **WHEN** 用户运行 stanza 初始化脚本且当前拓扑有效
- **THEN** 系统创建或验证 stanza
- **THEN** 系统触发 WAL 切换并证明新 WAL 已进入仓库

#### Scenario: WAL 归档失败
- **WHEN** 仓库不可写、配置错误或归档命令失败
- **THEN** 归档检查脚本以非零状态退出
- **THEN** 日志显示 PostgreSQL 归档状态、最近失败和建议检查项

### Requirement: 实例 Full 物理备份
系统 SHALL 提供从当前主库执行 pgBackRest Full 备份的脚本。该 Full SHALL 同时是可独立恢复的实例备份和后续 Incremental 的有效基础，不得另设“增量专用 Full”格式或脚本。

#### Scenario: 创建 Full 备份
- **WHEN** stanza、WAL 归档和当前主库检查通过
- **THEN** 系统创建整个 PostgreSQL 实例的 Full 物理备份
- **THEN** 备份信息中记录有效的 Full 标签、时间、大小和数据库系统标识

### Requirement: 实例 Incremental 物理备份
系统 SHALL 提供 pgBackRest Incremental 备份脚本，并在执行前确认同一仓库和 stanza 中存在有效 Full 基础。

#### Scenario: 在 Full 后创建 Incremental
- **WHEN** 有有效 Full 且实例发生数据变化
- **THEN** 系统创建依赖现有备份链的 Incremental
- **THEN** 备份信息明确显示该 Incremental 及其 Full 依赖关系

#### Scenario: 没有 Full 时请求 Incremental
- **WHEN** 仓库中不存在有效 Full
- **THEN** 教学脚本不依赖 pgBackRest 静默改做 Full
- **THEN** 脚本停止并指导用户先运行 `3-3.pgbackrest-backup-full.sh`

### Requirement: 备份链信息与检查
系统 SHALL 提供人类可读的备份链信息，并提供适合后续自动化消费的 JSON 状态输出。

#### Scenario: 查看备份链
- **WHEN** 用户运行备份信息脚本
- **THEN** 输出每个 Full 和 Incremental 的标签、类型、时间、大小、依赖和有效状态

### Requirement: 隔离物理恢复验证
系统 SHALL 将指定标签或最新 pgBackRest 备份恢复到独立验证目录和临时 PostgreSQL 实例，不得覆盖当前主库或从库。

#### Scenario: 恢复最新 Incremental
- **WHEN** 用户选择最新备份执行恢复验证
- **THEN** pgBackRest 自动解析所需 Full、Incremental 和 WAL
- **THEN** 临时实例成功启动并通过数据库、表和演示数据检查
- **THEN** 当前主从节点在验证过程中保持不变

#### Scenario: 备份链不可恢复
- **WHEN** 依赖文件、WAL 或备份元数据损坏
- **THEN** 验证脚本以非零状态退出并保留诊断日志
- **THEN** 不把该备份标记为已验证可恢复
