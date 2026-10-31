## ADDED Requirements

### Requirement: WAL 物理复制初始化
系统 SHALL 使用 PostgreSQL 原生物理流复制将 node-b 初始化为 node-a 的从库，包括复制账号、访问规则、基础数据、上游连接、复制槽和 `standby.signal`。

#### Scenario: 初始化主从复制
- **WHEN** node-a 是健康可写主库且 node-b 尚未初始化
- **THEN** 系统从 node-a 为 node-b 准备一致的基础数据
- **THEN** node-b 以 recovery 模式启动并连接 node-a 接收和回放 WAL
- **THEN** 系统等待两个节点追平并输出验证结果

#### Scenario: 拒绝覆盖当前主库
- **WHEN** 初始化目标节点被识别为当前可写主库
- **THEN** 脚本拒绝清空或覆盖目标数据目录并以非零状态退出

### Requirement: 复制状态可观测
系统 SHALL 提供复制状态脚本，显示节点角色、可写性、主库发送状态、从库接收和回放 LSN、延迟、复制槽、时间线和 WAL Receiver 状态。

#### Scenario: 复制健康且追平
- **WHEN** 主从复制正常且从库已经回放主库测试写入
- **THEN** 状态脚本显示单一主库、单一从库和零或可接受延迟
- **THEN** 同时提供成功退出码和可选 JSON 输出

#### Scenario: 复制中断
- **WHEN** 从库无法连接主库或所需 WAL 不可用
- **THEN** 状态脚本标识异常节点、断开状态和最后接收/回放位置
- **THEN** 脚本不得把容器运行等同于复制健康

### Requirement: 主从数据复制验证
系统 SHALL 提供在当前主库写入唯一测试记录并在当前从库读取该记录的验证脚本。

#### Scenario: 测试写入复制成功
- **WHEN** 用户运行复制读写验证且拓扑健康
- **THEN** 系统只向当前主库写入记录
- **THEN** 系统在超时范围内从从库读取到相同记录

### Requirement: 从主库重建从库
系统 SHALL 提供使用 `pg_basebackup` 从当前主库完整重建指定从库的脚本，并在操作前确认目标角色和数据目录。

#### Scenario: 损坏从库从主库重建
- **WHEN** 从库数据被实验脚本破坏且当前主库健康
- **THEN** 系统停止从库、隔离旧数据、重新获取基础数据并配置 standby
- **THEN** 重建后的从库重新连接并追平当前主库

### Requirement: 从 pgBackRest 重建从库
系统 SHALL 提供从有效 pgBackRest 物理备份恢复指定从库并通过归档及流复制追平当前主库的脚本。

#### Scenario: 使用备份修复损坏从库
- **WHEN** 存在已验证的物理备份和所需 WAL
- **THEN** 系统停止从库、隔离旧数据、恢复备份并配置为 standby
- **THEN** 从库从归档或当前主库补齐 WAL 后恢复健康复制

### Requirement: 分叉旧主重新加入
系统 SHALL 提供使用 `pg_rewind` 将旧主对齐到当前新主并重新配置为从库的脚本；`pg_rewind` 失败时 SHALL 停止并指导使用完整重建，MUST NOT 使用 `pg_resetwal` 或跳过 WAL。

#### Scenario: pg_rewind 成功重接旧主
- **WHEN** 旧主与新主发生时间线分叉且满足 `pg_rewind` 前置条件
- **THEN** 系统停止旧主、对齐数据目录、创建 standby 配置并连接新主
- **THEN** 旧主以 recovery 模式启动并追平新主

#### Scenario: pg_rewind 无法完成
- **WHEN** WAL、前置配置或源连接不足以执行 rewind
- **THEN** 脚本保持目标节点停止或处于安全状态并返回非零状态
- **THEN** 日志明确推荐从主库或 pgBackRest 完整重建

### Requirement: 安全故障模拟
系统 SHALL 提供仅针对已确认从库的损坏模拟脚本，用于教学验证修复流程，并明确显示将破坏的对象。

#### Scenario: 模拟从库损坏
- **WHEN** 用户明确确认损坏当前从库
- **THEN** 系统只破坏或隔离从库实验数据，不修改当前主库和备份仓库
