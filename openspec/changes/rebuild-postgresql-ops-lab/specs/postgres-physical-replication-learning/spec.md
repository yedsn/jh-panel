## ADDED Requirements

### Requirement: 主库准备是独立教学步骤
`2-1.replication-primary-prepare.sh` SHALL 固定操作 `pg-node-a`，创建或设置复制账号、在 `pg_hba.conf` 增加复制连接授权、reload 配置并创建 `slot_pg_node_b` 物理复制槽；它 MUST NOT 清理或修改 pg-node-b 数据目录。

#### Scenario: 准备复制源端
- **WHEN** 两个节点处于独立可写状态且学习者执行主库准备脚本
- **THEN** pg-node-a 具备复制账号、授权和物理复制槽，pg-node-b 仍是原来的独立实例

### Requirement: 基础备份是独立教学步骤
`2-2.replication-standby-basebackup.sh` SHALL 固定以 `pg-node-a` 为源、`pg-node-b` 为目标，停止目标节点、显示并清理目标数据目录，再使用 `pg_basebackup` 和 `-X stream -R -S slot_pg_node_b -P -c fast` 建立从库数据。

#### Scenario: 从独立实例重建为备用节点数据
- **WHEN** 主库准备完成且学习者确认执行基础备份脚本
- **THEN** pg-node-b 原独立集群数据被替换为 pg-node-a 的基础备份，数据目录中包含 `standby.signal` 和连接恢复配置

#### Scenario: 教学输出解释核心参数
- **WHEN** 基础备份脚本运行
- **THEN** 源码注释或运行日志解释 `-h`、`-X stream`、`-R`、`-S`、`-P` 和 `-c fast` 的作用，且不打印复制密码

### Requirement: 从库启动与验证是独立教学步骤
`2-3.replication-standby-start-verify.sh` SHALL 启动 pg-node-b，等待 PostgreSQL 可用，并分别验证 pg-node-b 处于 recovery、WAL Receiver 为 `streaming`、pg-node-a 能观察到对应复制连接。

#### Scenario: 从库成功连接主库
- **WHEN** 基础备份已完成且学习者执行启动验证脚本
- **THEN** pg-node-b 的 `pg_is_in_recovery()` 返回 `true`，WAL Receiver 报告 `streaming`，主库显示到该从库的发送连接

### Requirement: 测试固定展示主写从读
`3-1.replication-test-write-read.sh` SHALL 固定在 pg-node-a 写入唯一测试记录并在 pg-node-b 查询该记录，且 SHALL 明确展示写入位置、读取位置和验证值。

#### Scenario: WAL 复制传递测试数据
- **WHEN** pg-node-a 为主库、pg-node-b 为从库且复制正常
- **THEN** 测试记录先在 pg-node-a 写入，随后可在 pg-node-b 读取到相同唯一标识和内容

#### Scenario: 初始角色已不匹配
- **WHEN** pg-node-a 不可写或 pg-node-b 不处于 recovery
- **THEN** 测试脚本 MUST 失败并提示恢复初始拓扑，不得动态改为向另一个节点写入

### Requirement: 复制凭据不在教学日志泄露
系统 SHALL 从 gitignored `.env` 和权限受限的凭据文件读取数据库及复制密码，日志、README 示例和 VS Code 命令 MUST NOT 展示明文密码或完整带密钥连接串。

#### Scenario: 查看脚本运行日志
- **WHEN** 学习者执行任一复制脚本
- **THEN** 日志可显示用户、节点、端口、slot 和操作，但复制密码被省略或遮盖

