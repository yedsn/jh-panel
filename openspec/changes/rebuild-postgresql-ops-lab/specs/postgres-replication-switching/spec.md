## ADDED Requirements

### Requirement: 计划内切换停止旧主后提升从库
`4-1.replication-planned-switchover.sh` SHALL 固定处理 pg-node-a 主、pg-node-b 从的拓扑，记录切换目标 WAL 位置、等待 pg-node-b 回放到目标、停止 pg-node-a、提升 pg-node-b 并验证 pg-node-b 可写。它 MUST NOT 在同一脚本中自动重接旧主。

#### Scenario: 正常计划切换
- **WHEN** pg-node-a 为主、pg-node-b 为健康且已追平的从库，学习者确认执行计划切换
- **THEN** pg-node-a 被停止，pg-node-b 被提升为可写主库，旧主重接留给独立修复脚本

#### Scenario: 从库尚未追平
- **WHEN** pg-node-b 未回放到脚本记录的 pg-node-a WAL 位置
- **THEN** 脚本 MUST 不提升 pg-node-b，并显示当前发送或回放位置

### Requirement: 故障模拟不自动触发提升
`4-2.replication-simulate-primary-failure.sh` SHALL 只停止 pg-node-a 并验证它处于停止状态；它 MUST NOT 提升 pg-node-b 或修改 pg-node-b 的恢复配置。

#### Scenario: 观察 PostgreSQL 不会自动选主
- **WHEN** 初始主从健康且学习者执行主库故障模拟脚本
- **THEN** pg-node-a 停止，pg-node-b 仍处于 recovery，教学输出说明原生物理复制不会自动提升从库

### Requirement: 故障提升是单独操作
`4-3.replication-failover-promote-standby.sh` SHALL 在确认 pg-node-a 已停止后，通过 PostgreSQL 原生提升能力将 pg-node-b 提升为主库，并验证 `pg_is_in_recovery()` 为 `false` 且节点可写。

#### Scenario: 主库停止后提升从库
- **WHEN** pg-node-a 已停止且 pg-node-b 是可用从库，学习者确认执行故障提升脚本
- **THEN** pg-node-b 被提升为主库并能够接受新的写入

#### Scenario: 旧主仍在运行
- **WHEN** pg-node-a 仍在运行
- **THEN** 故障提升脚本 MUST 拒绝提升 pg-node-b，以避免产生两个可写节点

### Requirement: 提升后的旧主保持隔离
任一切换或故障提升脚本 SHALL 在成功提升 pg-node-b 后保持 pg-node-a 停止，直到学习者显式执行旧主重接或完整重建脚本。

#### Scenario: 提升完成后查看两个节点
- **WHEN** pg-node-b 已成功提升
- **THEN** pg-node-b 为唯一运行中的可写节点，pg-node-a 不会被切换脚本自动启动

