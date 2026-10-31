## Context

现有江湖面板已经具备成熟的 MySQL 备份与主从运维流程，但 PostgreSQL 相关能力仍处于方案验证阶段。团队需要先通过一个与业务隔离、可重复销毁和重建的学习项目，实际观察 PostgreSQL 物理备份、WAL 归档、物理流复制、时间线、`pg_rewind` 和计划内主从切换，而不是直接把未经验证的流程写入面板插件。

项目部署在 `/www/wwwroot/postgres-ops-lab`，运行在单台学习服务器上。两个 PostgreSQL 容器模拟两个节点，因此可以验证数据库层流程和时间线变化，但不能验证真实双机环境下的网络分区、宿主机故障、共享存储故障或仲裁。两个节点都发布固定宿主机端口，便于从其他机器分别连接并观察数据。

本项目同时承担两个角色：一是教学 Demo，所有脚本必须解释正在做什么及其原理；二是未来江湖面板/1Panel PostgreSQL 运维 CLI 的技术试验场，因此脚本必须具备明确退出码、非交互参数和可复用的角色发现逻辑。

## Goals / Non-Goals

**Goals:**

- 用一个 Docker Compose 项目启动两个可远程访问、数据持久化的 PostgreSQL 节点。
- 演示单数据库逻辑备份与恢复，以及整个 PostgreSQL 实例的 pgBackRest Full/Incremental 物理备份和隔离恢复验证。
- 演示 PostgreSQL 内置 WAL 物理流复制的初始化、状态观测、追平验证、损坏模拟和两种从库重建路径。
- 演示计划内、暂停写入、先检查追平、再提升并重接旧主的主从切换。
- 让每个操作脚本同时适合人工学习和后续自动化调用。
- 保证容器停止、删除和重建后，宿主机上的数据库数据、备份仓库、配置和日志仍然存在。

**Non-Goals:**

- 不提供单表备份。
- 不实现 Patroni、etcd、Consul、VIP、HAProxy、自动选主或无人值守故障转移。
- 不模拟两台真实服务器、网络分区、宿主机断电或存储故障。
- 不修改江湖面板或 1Panel 源码，也不提供面板页面。
- 不把该 Demo 直接定义为生产 PostgreSQL 高可用方案。
- 不支持从物理备份只恢复单个数据库；单库恢复使用逻辑备份。

## Decisions

### 1. 使用一个自定义 PostgreSQL 镜像承载数据库与运维工具

两个节点使用同一个基于官方 PostgreSQL 17 镜像构建的镜像，并在构建阶段安装 pgBackRest。镜像同时包含 PostgreSQL 官方客户端工具和只在容器内运行的薄封装脚本。宿主机脚本通过 `docker compose exec` 或一次性容器调用这些工具。

选择该方案是因为 `archive_command` 由 PostgreSQL 进程在容器内执行，pgBackRest 客户端必须存在于数据库容器中。运行时临时安装工具会在容器重建后丢失，单独 sidecar 也不能自然满足 `archive_command` 的执行环境要求。

### 2. 节点名和端口固定，角色动态发现

- `pg-node-a` 发布到宿主机端口 `15432`。
- `pg-node-b` 发布到宿主机端口 `25432`。
- 容器内均监听 `5432`。
- 允许访问的 CIDR、端口和密码通过 `.env` 配置；默认配置应提示用户限制来源网段。

端口始终代表节点，不代表主从角色。所有备份、修复和切换脚本在执行前通过 `SELECT pg_is_in_recovery()` 识别当前主库与从库，不硬编码 node-a 永远是主库。状态脚本同时输出“节点、端口、角色、可写性、时间线和复制进度”，避免切换后误连旧端口写入。

### 3. 所有持久状态使用宿主机 bind mount

项目根目录只保留 README、环境变量、用户脚本和测试；所有容器构建与运行资产统一放在 `docker/`。项目至少持久化以下目录：

```text
docker/data/pg-node-a
docker/data/pg-node-b
docker/data/restore-verify
docker/backup/database
docker/backup/pgbackrest
docker/spool/pg-node-a
docker/spool/pg-node-b
docker/config
docker/image
docker/logs
docker/state
```

镜像只保存软件和脚本；数据库数据、备份、配置和运行状态不得只存在于容器可写层。普通的 `docker compose down` 和强制重建不得删除这些目录。只有显式的 `environment-reset.sh` 才可清除实验数据，并且必须显示目标绝对路径、要求二次确认，不得接受空路径、根目录或工作区上级目录。

### 4. 从库容器在复制初始化前保持等待状态

初次启动时 node-a 按官方入口初始化为独立主库。node-b 在数据目录为空时进入可观察的等待状态，不自动初始化成第二个独立主库。`replication-init.sh` 负责创建复制账号、准备访问规则、从 node-a 获取基础数据、写入 `standby.signal` 与连接配置，然后重启 node-b 进入恢复模式。

这避免 Compose 首次启动时出现两个可写主库，也让学习者能够清楚看到“基础备份 + standby 标记 + 上游连接”组成物理从库的过程。

### 5. 逻辑备份只覆盖单数据库

`backup-database-create.sh` 使用 `pg_dump --format=custom` 备份指定数据库；`backup-database-restore.sh` 使用 `pg_restore`，默认恢复到新建的目标数据库，不覆盖源库。`backup-database-verify.sh` 对比 schema、表数量和教学数据。

单表备份不在范围内。逻辑备份不能作为 pgBackRest 增量备份的基础，也不宣称能完整保存实例级角色、表空间和物理状态。

### 6. pgBackRest 使用一个共享仓库和一个 stanza

两个节点挂载同一个宿主机 pgBackRest 仓库，但各自使用独立 spool 目录。两边的 PostgreSQL 数据目录在容器中保持相同路径，使同一份 stanza 配置能够随角色切换继续使用。主库配置 `archive_mode=on`，通过 `archive_command` 持续执行 `pgbackrest archive-push`；从库通过流复制和 `restore_command` 在必要时从仓库补取 WAL。

备份脚本始终动态选择当前主库执行。第一版提供：

- `pgbackrest-backup-full.sh`：创建普通 Full，既可独立恢复，也是后续 Incremental 的基础。
- `pgbackrest-backup-incremental.sh`：创建 Incremental；脚本在执行前明确检查存在有效 Full，否则停止并指导先执行 Full。

不设置“增量专用全量”脚本。第一版也不提供 Differential，避免扩大教学范围。

### 7. 物理恢复通过隔离验证实例完成

`pgbackrest-restore-verify.sh` 不覆盖正在运行的 node-a 或 node-b，而是恢复到 `data/restore-verify`，使用独立的一次性验证容器启动并执行 SQL 检查。需要人工远程检查时，可以发布单独的可配置验证端口；默认验证完成后停止验证实例，但保留日志和结果摘要。

恢复目标可以是最新备份或指定备份标签。脚本只要求用户选择目标，pgBackRest 根据元数据自动解析 Full 和 Incremental 依赖链，用户无需手工逐层拼接。

### 8. 主从修复提供三条明确路径

1. `replication-rebuild-standby-from-primary.sh` 使用 `pg_basebackup` 从当前主库重新建立从库，流程直接但会读取主库全量数据。
2. `replication-repair-standby-from-pgbackrest.sh` 从 pgBackRest 恢复物理备份，再通过归档和流复制追平，接近生产环境中的低主库压力修复方式。
3. `replication-rejoin-old-primary-with-pg-rewind.sh` 用于主从切换或时间线分叉后的旧主重接；先执行 `pg_rewind`，失败时停止并指导使用完整重建，不使用 `pg_resetwal` 或跳过 WAL。

初始化时启用数据校验和或 `wal_log_hints=on`，确保 `pg_rewind` 具备前置条件。修复脚本必须确认目标节点不是当前可写主库，并在替换数据目录前保留可识别的旧目录或明确执行可恢复的隔离步骤。

### 9. 计划内切换使用“检查、切换、验证”三段式

`switchover-check-readiness.sh` 检查单主单从拓扑、复制连接、WAL 接收/回放、延迟、归档和备份仓库。`switchover-execute.sh` 暂停 Demo 写入、执行检查点、等待从库追平、正常停止旧主、提升原从库，并用 `pg_rewind` 将旧主对齐后配置为新主的从库。`switchover-verify.sh` 验证新主可写、旧主处于 recovery、新写入能够复制到旧主。

提升操作会使被提升节点自动移除自身的 `standby.signal`。旧主不得仅通过设置普通只读参数来假装从库；它必须经过数据对齐、写入 standby 配置并以恢复模式启动。切换脚本在任一步失败时保持业务写入暂停并输出当前状态与人工处理建议，不得在拓扑不确定时自动继续。

### 10. 统一脚本命名与教学日志协议

用户脚本采用 `<功能域>-<动作>-<补充>.sh`，例如：

- `environment-start.sh`
- `backup-database-create.sh`
- `pgbackrest-backup-full.sh`
- `replication-init.sh`
- `replication-repair-standby-from-pgbackrest.sh`
- `switchover-execute.sh`

共享库放在 `scripts/common/`，由目录表达其公共属性，文件使用 `config.sh`、`docker.sh`、`postgresql.sh` 等简洁名称且不作为用户入口。每个用户脚本至少支持 `--help`；涉及初始化、清空、恢复、修复和切换的脚本支持 `--pause`、`--yes`、`--verbose` 和 `--dry-run`。

统一日志包含：任务目标、原理、前置条件、编号步骤、执行动作、验证依据、结果和失败后的下一步。密码、完整连接字符串和敏感环境变量不得出现在日志。所有失败必须返回非零退出码。

## Risks / Trade-offs

- [同一宿主机不能证明真正高可用] → README 明确说明这是数据库层学习 Demo；后续生产验证必须使用两台独立主机并加入客户端流量切换和仲裁。
- [远程端口暴露带来安全风险] → 默认要求配置访问 CIDR、使用 SCRAM 密码、提示配置宿主机防火墙，文档禁止将弱密码数据库直接暴露到公网。
- [共享 pgBackRest 仓库是单点] → 学习环境接受该取舍；生产设计再迁移到独立仓库主机、NFS 或 S3 兼容存储。
- [误执行修复或 reset 会删除实验数据] → 动态识别角色、验证绝对路径、显示目标、二次确认，并保留 `--dry-run`；禁止脚本对未识别目录执行递归删除。
- [Incremental 依赖链损坏会影响恢复] → 每次备份后运行校验/信息检查，并通过隔离恢复实际证明备份可用，而不是只检查命令退出码。
- [切换中断会留下无主或旧主未重接状态] → 每一步持久记录状态，失败时停止自动推进并输出两个节点的实际角色和恢复指引；不承诺自动回滚提升操作。
- [复制槽可能因从库离线导致 WAL 堆积] → 状态脚本显示 slot 状态和保留量；重建、切换和 reset 流程负责创建、复用或清理节点对应的物理复制槽。
- [脚本教学输出可能影响自动化解析] → 人类日志写入标准输出/错误输出，同时保留稳定退出码；状态类脚本提供可选 JSON 输出供未来 CLI 和面板适配。

## Migration Plan

1. 在 `/www/wwwroot/postgres-ops-lab` 创建项目骨架，将 Dockerfile、Compose、配置、镜像入口和运行数据统一收纳到 `docker/`，用户脚本保留在根目录的 `scripts/`。
2. 构建镜像并启动 node-a，确认 node-b 处于等待初始化而非可写状态。
3. 初始化 Demo 数据和 pgBackRest stanza，验证 WAL 能进入持久化仓库。
4. 初始化物理从库，验证两个远程端口、角色识别和数据复制。
5. 依次执行单库备份恢复、Full、Incremental 和隔离恢复验证。
6. 执行从库损坏模拟，并分别验证 pg_basebackup 与 pgBackRest 重建路径。
7. 执行计划内切换和旧主 `pg_rewind` 重接，再执行反向写入复制验证。
8. 执行容器删除与重建验证，确认数据和备份仍在。

如实施失败，可停止并删除 Compose 容器；由于项目与面板隔离，不影响现有服务。是否删除 `/www/wwwroot/postgres-ops-lab` 中的数据和备份必须由用户显式决定。

## Open Questions

- 实施时需要根据宿主机实际可用镜像确定 PostgreSQL 17 和 pgBackRest 的固定小版本，并在 README 记录。
- 默认允许远程访问的 CIDR 应由部署时环境决定；模板不得假设 `0.0.0.0/0` 是安全默认值。
- 隔离恢复验证端口是否默认发布，可以在实施阶段根据端口冲突检查决定；两个主节点端口必须发布。
