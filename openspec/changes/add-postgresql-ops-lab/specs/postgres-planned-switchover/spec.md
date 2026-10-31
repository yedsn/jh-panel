## ADDED Requirements

### Requirement: 主从切换就绪检查
系统 SHALL 在计划内切换前确认拓扑恰好包含一个可写主库和一个 recovery 从库，并检查复制连接、WAL 接收/回放、延迟、归档状态、磁盘状态和 `pg_rewind` 前置条件。

#### Scenario: 拓扑满足切换条件
- **WHEN** 单主单从健康、从库追平且所有前置检查通过
- **THEN** 就绪检查成功并输出当前主库、目标新主和切换计划

#### Scenario: 存在异常或角色不明确
- **WHEN** 检测到双主、双从、复制中断、延迟未追平或节点不可达
- **THEN** 就绪检查失败并阻止切换执行
- **THEN** 日志指出未满足的具体条件

### Requirement: 受控计划内切换
系统 SHALL 提供受控切换脚本，依次暂停 Demo 写入、等待从库追平、正常停止旧主、提升原从库、对齐旧主并将其作为新主的从库启动。

#### Scenario: 完成主从角色互换
- **WHEN** 就绪检查通过且用户确认执行切换
- **THEN** 原从库使用 PostgreSQL 原生提升功能成为唯一可写主库
- **THEN** 原主库经 `pg_rewind` 或等价安全对齐后以 recovery 模式重新加入
- **THEN** 整个过程中不得同时保留两个允许写入的节点

#### Scenario: 切换中途失败
- **WHEN** 停止旧主、提升新主或重接旧主任一步骤失败
- **THEN** 脚本停止自动推进、保持 Demo 写入暂停并返回非零状态
- **THEN** 日志输出两个节点实际角色、已完成步骤和人工恢复建议

### Requirement: 切换后验证
系统 SHALL 验证新主可写、旧主只读且处于 recovery，并验证写入新主的数据能够复制到旧主。

#### Scenario: 切换验证成功
- **WHEN** 切换流程完成
- **THEN** 新主 `pg_is_in_recovery()` 返回 false 且能够接受测试写入
- **THEN** 旧主 `pg_is_in_recovery()` 返回 true 且能够读取该测试写入
- **THEN** 状态输出显示节点端口不变但角色已经互换

### Requirement: 防止以普通只读代替降级
系统 MUST NOT 将设置 `default_transaction_read_only`、撤销业务权限或其他普通只读参数视为旧主已降级为物理从库。

#### Scenario: 旧主尚未进入 recovery
- **WHEN** 旧主只是被设置为只读但 `pg_is_in_recovery()` 仍返回 false
- **THEN** 切换验证失败并指出该节点仍是主库身份
