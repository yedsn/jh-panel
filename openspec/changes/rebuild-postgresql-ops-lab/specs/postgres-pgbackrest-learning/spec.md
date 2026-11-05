## ADDED Requirements

### Requirement: 数据库镜像内置 pgBackRest
系统 SHALL 使用基于固定 PostgreSQL 17 官方镜像构建的共享学习镜像，并在构建阶段安装固定版本 pgBackRest，使 PostgreSQL 进程可在容器内执行 `archive-push`、`archive-get`、备份、检查和恢复相关命令。

#### Scenario: 重建数据库容器后工具仍存在
- **WHEN** 学习者删除并重新创建 pg-node-a 或 pg-node-b 容器
- **THEN** 容器内仍可执行固定版本 pgBackRest，且不需要运行时临时安装软件

### Requirement: pgBackRest 仓库和 spool 显式持久化
系统 SHALL 将共享 pgBackRest 仓库、配置、恢复验证数据、恢复日志和操作状态映射到 `docker/pgbackrest/`，并为 pg-node-a 与 pg-node-b 使用各自独立的 spool 目录。普通容器停止或重建 MUST NOT 删除这些内容。

#### Scenario: 容器重建后备份仍存在
- **WHEN** 已创建 Full 或 Incremental 后重建数据库容器
- **THEN** `pgbackrest info` 仍能从宿主机仓库读取原有备份元数据和备份集

### Requirement: stanza 初始化是独立学习步骤
`6-1.pgbackrest-init-stanza.sh` SHALL 接受显式 `--node pg-node-a|pg-node-b`，默认使用 pg-node-a；脚本 SHALL 验证指定节点是可写主库且另一节点属于同一物理集群，再创建或检查 `lab` stanza、触发 WAL switch 并解释 stanza 与复制槽的区别。

#### Scenario: 在初始物理主从建立后创建 stanza
- **WHEN** pg-node-a 为主、pg-node-b 是由其基础备份建立的从库且学习者执行 `6-1`
- **THEN** `lab` stanza 被创建并通过基本检查，仓库开始记录该 PostgreSQL 集群的备份和 WAL

#### Scenario: 两个节点仍是不同独立集群
- **WHEN** 两个节点具有不同 system identifier
- **THEN** stanza 初始化脚本 MUST 在写入仓库前停止，并提示先执行 `2-1`、`2-2`、`2-3` 建立物理主从

### Requirement: WAL 归档检查是独立学习步骤
`6-2.pgbackrest-check-archive.sh` SHALL 检查指定主库的 `pg_stat_archiver`、执行 pgBackRest check、触发新的 WAL 切换并验证对应 WAL 可在仓库中取得。

#### Scenario: 证明 WAL 已归档
- **WHEN** stanza 已初始化且归档配置正常
- **THEN** 脚本显示最近成功归档信息，并以 pgBackRest 检查结果或仓库证据证明新 WAL 已进入仓库

#### Scenario: 归档失败
- **WHEN** 仓库不可写、配置错误或 `archive_command` 执行失败
- **THEN** 脚本 MUST 返回失败，显示 PostgreSQL 归档统计与 pgBackRest 原生错误，不得误报归档健康

### Requirement: Full 备份作为增量链基础
`6-3.pgbackrest-backup-full.sh` SHALL 在显式指定且已验证可写的节点上创建实例级 Full 备份，并显示备份 label、类型、时间和大小。该普通 Full SHALL 同时可独立恢复并作为后续 Incremental 的基础，不得再创建“增量专用 Full”入口。

#### Scenario: 创建首个实例 Full
- **WHEN** stanza 与 WAL 归档健康且学习者执行 Full 脚本
- **THEN** 仓库新增一个有效 Full 备份，脚本显示其 label 和可供后续 Incremental 依赖的含义

### Requirement: Incremental 备份依赖已有 Full
`6-4.pgbackrest-backup-incremental.sh` SHALL 在创建实例级 Incremental 前确认仓库存在有效 Full，成功后显示新备份 label、类型和依赖基础。

#### Scenario: 基于普通 Full 创建 Incremental
- **WHEN** 仓库存在 `6-3` 创建的有效 Full 且数据库发生新变化
- **THEN** 脚本创建 Incremental，并明确它只保存相对已有备份链发生变化的数据块

#### Scenario: 缺少 Full
- **WHEN** 仓库没有有效 Full
- **THEN** Incremental 脚本 MUST 不创建备份，并提示先执行 `6-3.pgbackrest-backup-full.sh`

### Requirement: 备份信息脚本显示恢复依赖
`6-5.pgbackrest-show-info.sh` SHALL 以只读方式显示仓库中的 Full 和 Incremental 备份，包括类型、label、开始/结束时间、大小、数据库版本和依赖关系。

#### Scenario: 查看 Full 与 Incremental 链
- **WHEN** 仓库同时存在 Full 和后续 Incremental
- **THEN** 学习者能从输出识别每个备份的类型以及 Incremental 所依赖的基础备份

### Requirement: 恢复在隔离实例中验证
`6-6.pgbackrest-restore-verify.sh` SHALL 恢复最新或显式 label 的备份到 `docker/pgbackrest/restore-verify/data`，使用独立验证容器启动恢复结果并执行 SQL 数据验证。脚本 MUST NOT 覆盖或挂载 pg-node-a、pg-node-b 的数据目录。

#### Scenario: 恢复 Incremental 备份
- **WHEN** 学习者选择一个有效 Incremental label
- **THEN** pgBackRest 自动解析 Full 与增量依赖链完成恢复，验证容器可启动且能查询到备份时的教学数据

#### Scenario: 恢复目标越界
- **WHEN** 恢复目标解析到 node-a、node-b、项目根目录、项目外路径或其他非白名单位置
- **THEN** 恢复脚本 MUST 在清理或写入前失败

### Requirement: pgBackRest 操作不泄露敏感信息
pgBackRest 配置、脚本和日志 SHALL 使用权限受限的本地环境文件或配置传递必要凭据，MUST NOT 在 VS Code 命令、README 示例或普通日志中输出数据库密码、仓库密钥或完整认证连接串。

#### Scenario: 检查备份和恢复日志
- **WHEN** 学习者执行 `6-1` 至 `6-6`
- **THEN** 日志包含 stanza、节点、label、路径和验证结果，但敏感凭据被省略或遮盖

