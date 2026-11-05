## ADDED Requirements

### Requirement: 完整重建从库使用显式源和目标
`5-1.replication-rebuild-standby-from-primary.sh` SHALL 要求 `--primary` 和 `--target` 参数，值只能是 `pg-node-a` 或 `pg-node-b` 且不能相同。脚本 SHALL 从显式主库准备目标 slot，停止并清理显式目标数据目录，通过 `pg_basebackup` 完整重建目标并验证复制。

#### Scenario: 从当前主库重建损坏从库
- **WHEN** 学习者指定一个可写主库和另一个目标节点并确认执行
- **THEN** 只有目标节点数据被替换，目标以 recovery 模式启动并从指定主库接收 WAL

#### Scenario: 参数指向同一节点
- **WHEN** `--primary` 与 `--target` 相同或包含未知节点名
- **THEN** 脚本 MUST 在修改数据前失败并显示合法用法

### Requirement: 旧主重接使用 pg_rewind
`5-2.replication-rejoin-old-primary-with-pg-rewind.sh` SHALL 要求显式新主和旧主参数，保持旧主停止，使用 `pg_rewind` 将旧主数据目录对齐到新主时间线，再写入 `standby.signal`、`primary_conninfo` 和目标专用 `primary_slot_name`，最后启动并验证旧主成为从库。

#### Scenario: 切换后旧主成功重接
- **WHEN** pg-node-b 已提升为主库、pg-node-a 保持停止且所需 WAL 可用
- **THEN** 执行 `--primary pg-node-b --target pg-node-a` 后，pg-node-a 以 recovery 模式启动并追随 pg-node-b

#### Scenario: pg_rewind 无法完成
- **WHEN** `pg_rewind` 因 WAL 缺失、数据校验前置条件或连接错误失败
- **THEN** 脚本 MUST 保持目标节点停止，不得调用 `pg_resetwal`，并提示改用完整重建脚本

### Requirement: 修复操作只修改明确目标
两个修复脚本 SHALL 显示源节点、目标节点和目标数据目录，在删除、覆盖、rewind 或启动前要求确认，并 MUST NOT 自动选择或交换节点。

#### Scenario: 用户取消修复
- **WHEN** 学习者在确认提示中取消
- **THEN** 脚本不修改目标数据目录、不改变节点角色并返回可辨识的取消结果

