## Why

团队计划为江湖面板及未来的 1Panel 迁移建设 PostgreSQL 运维能力，但目前缺少一个可安全反复演练的环境，用来验证 pg_dump、pgBackRest、WAL 物理复制、从库修复和计划内主从切换的完整流程。先建设一个独立的 Docker Compose 学习项目，可以在不影响现有业务数据库的情况下形成经过实际验证的操作方法和后续 CLI 设计基础。

## What Changes

- 在 `/www/wwwroot/postgres-ops-lab` 建立独立的 PostgreSQL 运维学习项目，通过 Docker Compose 启动两个带 pgBackRest 和运维脚本的 PostgreSQL 节点。
- 将两个固定节点端口发布到宿主机，允许从其他机器分别连接节点、查看数据并观察主从角色切换。
- 提供单数据库的逻辑备份、恢复和恢复验证，不提供单表备份。
- 提供 pgBackRest stanza 初始化、WAL 归档检查、实例 Full/Incremental 物理备份、备份信息查看及隔离恢复验证；普通 Full 直接作为后续 Incremental 的基础，不设置“增量专用全量”脚本。
- 提供 PostgreSQL 内置 WAL 物理流复制初始化、状态查看、同步等待和读写验证。
- 提供从库损坏模拟、从主库重建、从 pgBackRest 重建，以及旧主通过 pg_rewind 或完整重建重新加入的修复演练。
- 提供计划内主从切换的就绪检查、执行和验证，切换后旧主作为新主的从库重新加入。
- 所有面向用户的脚本采用清晰的功能前缀命名，并输出目标、原理、步骤、动作和验证结果；高风险操作支持确认、教学暂停、非交互和试运行模式。
- 数据目录、备份仓库、配置、日志和状态均持久化到宿主机目录，重建容器不得导致数据或备份丢失。

## Capabilities

### New Capabilities

- `postgres-ops-lab-environment`: 双节点 Docker Compose 学习环境、远程端口、持久化目录、初始化数据和统一环境操作。
- `postgres-database-logical-backup`: 使用 pg_dump/pg_restore 完成单数据库逻辑备份、恢复和隔离验证。
- `postgres-pgbackrest-backup`: 使用 pgBackRest 完成实例 Full/Incremental 备份、WAL 归档、备份检查和隔离恢复验证。
- `postgres-physical-replication`: 使用 PostgreSQL WAL 物理复制完成主从初始化、状态观测、故障模拟、从库修复和旧主重新加入。
- `postgres-planned-switchover`: 执行带追平检查、防双主保护和切换后验证的计划内主从切换。
- `postgres-ops-learning-experience`: 统一脚本命名、教学式步骤日志、原理说明、交互确认及自动化参数约定。

### Modified Capabilities

无。

## Impact

- 新增独立项目目录 `/www/wwwroot/postgres-ops-lab`，不修改江湖面板现有 PostgreSQL 插件或 1Panel 源码。
- 依赖服务器现有 Docker 与 Docker Compose，并新增两个可配置的宿主机 PostgreSQL 访问端口。
- 需要构建包含 PostgreSQL、pgBackRest、pg_dump、pg_restore、pg_basebackup 和 pg_rewind 的固定版本镜像。
- 会占用宿主机磁盘保存两个节点的数据、逻辑备份、pgBackRest 仓库、WAL、恢复验证目录和日志。
- 产出的镜像布局、脚本接口和演练结论将作为后续江湖面板/1Panel 运维 CLI 与管理页面的验证基础，但本变更不包含面板集成、自动故障转移、VIP、Patroni 或生产部署。
