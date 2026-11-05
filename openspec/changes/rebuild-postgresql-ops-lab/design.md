## Context

`/www/wwwroot/postgres-ops-lab` 当前包含一个单 Compose 双节点项目，以及逻辑备份、pgBackRest、自动角色发现、损坏模拟、切换状态和多套公共函数。它已经完成过复杂实验，但与当前“先把 PostgreSQL 原生 WAL 物理复制流程学清楚”的目标不一致。用户已经明确授权清掉旧项目代码和运行数据，从空白状态重建，不需要迁移旧数据库、备份或日志。

新项目仍运行在一台宿主机上，用两个容器模拟两台数据库节点。节点身份固定为 `pg-node-a` 和 `pg-node-b`，宿主机端口固定为 `15432` 和 `25432`；角色会因提升和重接发生变化。教学主线采用固定方向，初始化复制时 `pg-node-a` 是主库、`pg-node-b` 是从库，脚本不通过复杂代码猜测操作者意图。

## Goals / Non-Goals

**Goals:**

- 从零重建两个目录、两个 Compose 项目、两个独立 PostgreSQL 数据目录。
- `1-1.environment-init.sh` 完成后两个节点都是独立、可读写实例，`pg_is_in_recovery()` 均为 `false`。
- 用拆分脚本展示复制账号、`pg_hba.conf`、物理复制槽、`pg_basebackup`、`standby.signal`、`primary_conninfo`、WAL Receiver 的关系。
- 分开演示计划内切换和故障转移，避免把停止、提升、重接全部封装成看不清的黑盒。
- 分开演示从库完整重建与旧主 `pg_rewind` 重接。
- 用独立的 pgBackRest 脚本学习 stanza、WAL 归档、实例 Full/Incremental 备份、备份依赖链和隔离恢复。
- 每个脚本按执行顺序输出目标、原理、步骤、关键命令含义和验证结果，并在源码中对 PostgreSQL 核心命令逐项注释。
- 两个节点端口允许其他机器直接连接观察；数据库数据、pgBackRest 仓库、恢复目录、配置和日志都通过宿主机挂载持久化。

**Non-Goals:**

- 不迁移或保留旧项目数据库、备份、WAL、日志、状态和旧脚本。
- 不提供 pg_dump、单库备份或单表备份；本次备份学习只覆盖 pgBackRest 的实例级物理 Full 和 Incremental。
- 不实现 Patroni、etcd/Consul、VIP、HAProxy、自动选主、自动故障转移、脑裂仲裁或生产 HA。
- 不自动发现任意拓扑并替用户决定主库、从库和修复方向。
- 不修改江湖面板、1Panel 或项目目录外的 PostgreSQL 服务。

## Decisions

### 1. 删除工作区旧内容，但保留项目根目录和 Git 元数据

实施时先停止旧项目 Compose 管理的容器，再删除 `/www/wwwroot/postgres-ops-lab` 下旧的工作树内容和运行数据，然后写入新结构。保留根目录本身与 `.git/`，使旧版本仍可从 Git 历史恢复；不保留旧数据库数据、备份、日志或额外归档副本。

删除操作只允许解析到该项目目录下的已知路径，不能使用未校验变量、宽泛通配符或项目上级目录。项目外同名容器、网络、卷和镜像不在清理范围。相比直接删除整个目录，这个方案既满足重建工作区，又避免无必要地销毁版本历史。

### 2. 每个 PostgreSQL 节点拥有独立 Docker Compose 目录

新结构为：

```text
postgres-ops-lab/
├── README.md
├── .env.example
├── .env
├── .gitignore
├── .vscode/launch.json
├── docker/
│   ├── network/
│   ├── image/
│   │   └── Dockerfile
│   ├── pgbackrest/
│   │   ├── config/
│   │   ├── repository/
│   │   ├── restore-verify/
│   │   │   ├── docker-compose.yml
│   │   │   ├── data/
│   │   │   └── logs/
│   │   └── state/
│   ├── pg-node-a/
│   │   ├── docker-compose.yml
│   │   ├── config/
│   │   ├── data/
│   │   ├── logs/
│   │   ├── spool/
│   │   └── state/
│   └── pg-node-b/
│       ├── docker-compose.yml
│       ├── config/
│       ├── data/
│       ├── logs/
│       ├── spool/
│       └── state/
├── scripts/
│   ├── 1-1.environment-init.sh
│   ├── 2-1.replication-primary-prepare.sh
│   ├── 2-2.replication-standby-basebackup.sh
│   ├── 2-3.replication-standby-start-verify.sh
│   ├── 3-1.replication-test-write-read.sh
│   ├── 4-1.replication-planned-switchover.sh
│   ├── 4-2.replication-simulate-primary-failure.sh
│   ├── 4-3.replication-failover-promote-standby.sh
│   ├── 5-1.replication-rebuild-standby-from-primary.sh
│   ├── 5-2.replication-rejoin-old-primary-with-pg-rewind.sh
│   ├── 6-1.pgbackrest-init-stanza.sh
│   ├── 6-2.pgbackrest-check-archive.sh
│   ├── 6-3.pgbackrest-backup-full.sh
│   ├── 6-4.pgbackrest-backup-incremental.sh
│   ├── 6-5.pgbackrest-show-info.sh
│   ├── 6-6.pgbackrest-restore-verify.sh
│   └── common/
│       ├── config.sh
│       ├── docker.sh
│       ├── log.sh
│       └── postgresql.sh
└── tests/
    ├── all-shell-syntax-test.sh
    └── compose-config-test.sh
```

两个 Compose 项目连接同一个显式外部网络 `postgres-ops-lab-network`，容器内使用稳定名称 `pg-node-a:5432`、`pg-node-b:5432` 通信。独立目录让学习者可以清楚看到每个节点的配置和数据，不通过一个 Compose 文件同时控制两个实例。

### 3. 两个节点使用同一自定义学习镜像

两个节点统一使用一个基于固定 PostgreSQL 17 官方镜像构建的学习镜像。官方镜像已经包含 `psql`、`pg_basebackup`、`pg_ctl` 和 `pg_rewind`，Dockerfile 只额外安装固定版本 pgBackRest，不增加自定义数据库管理进程。两个独立 Compose 指向同一构建上下文和同一镜像名称。

必须把 pgBackRest 安装到数据库镜像内，因为 PostgreSQL 的 `archive_command` 由数据库容器中的 postgres 进程执行，不能依赖宿主机临时安装。相比另建没有常驻职责的工具 sidecar，这一结构更直接，也保证容器重建后归档命令仍然存在。宿主机教学脚本通过对应 Compose 项目的 `exec` 调用原生命令。

### 4. 初始化脚本明确重建两个独立可写实例

`1-1.environment-init.sh` 是本项目的显式“回到起点”入口：显示将清理的两个节点数据目录、日志/状态、pgBackRest repository/spool/state 和隔离恢复目录，确认后停止两个节点及恢复验证 Compose 并清空这些实验状态，再创建外部网络并分别启动节点。它不创建复制账号、复制槽、stanza 或 `standby.signal`。必须清空旧 pgBackRest 仓库，因为重新初始化数据库会产生新的 system identifier，旧 stanza 不能安全复用。

初始化验证固定执行：

```sql
SELECT pg_is_in_recovery();
```

两个节点都必须返回 `false`，并各自完成一次写入/读取验证。该设计比“node-b 空目录等待复制”更符合用户要求，也让 `2-*` 脚本完整展示从独立数据库变为物理从库的过程。

### 5. 基础配置预置复制能力，复制关系仍由教学脚本建立

两个节点都预置以下 PostgreSQL 参数：

```text
listen_addresses = '*'
wal_level = replica
max_wal_senders = 10
max_replication_slots = 10
wal_log_hints = on
hot_standby = on
password_encryption = scram-sha-256
archive_mode = on
archive_command = 'pgbackrest --stanza=lab archive-push %p'
restore_command = 'pgbackrest --stanza=lab archive-get %f %p'
```

普通数据库远程访问按用户要求允许任意 IPv4/IPv6 网段并使用 SCRAM 密码；README 明确说明这只适用于隔离学习环境，公网部署必须收紧防火墙和 CIDR。复制专用访问规则由主库准备或修复脚本写入对应节点的 `pg_hba.conf` 并 reload，使学习者能看到复制连接的独立授权。

`wal_log_hints=on` 是 `pg_rewind` 的前置条件之一；预置在两个节点可避免切换后才发现旧主无法 rewind。

`archive_command` 在 stanza 创建前可能暂时报告归档失败，这是 pgBackRest 尚未初始化的可观察状态；它不会阻止数据库启动。README 将指导先完成主从初始化，再进入 `6-1` 创建 stanza 和验证归档。

### 6. 复制初始化拆成三个固定方向脚本

初始方向固定为 `pg-node-a` → `pg-node-b`：

1. `2-1.replication-primary-prepare.sh` 只在 node-a 创建/更新 `replicator`、增加复制访问规则并创建 `slot_pg_node_b`。
2. `2-2.replication-standby-basebackup.sh` 只停止 node-b、清空 node-b 数据目录，再从 node-a 执行 `pg_basebackup`。核心参数为 `-X stream -R -S slot_pg_node_b -P -c fast`，脚本源码和运行日志逐项解释它们。
3. `2-3.replication-standby-start-verify.sh` 只启动 node-b 并验证 `pg_is_in_recovery()=true`、`pg_stat_wal_receiver.status=streaming` 及主库对应复制连接。

复制密码保存在 gitignored `.env` 和 node-b 的只读凭据文件中，不在日志显示。`primary_conninfo` 使用凭据文件而不是把明文密码写入可打印的连接串；`standby.signal` 和 `primary_slot_name` 保留在 node-b 的持久化数据目录。

### 7. 测试脚本固定主写从读

`3-1.replication-test-write-read.sh` 固定在 node-a 创建教学表、写入带唯一标识的记录，再在 node-b 查询相同标识。脚本不动态找主库；如果角色已切换，应明确失败并提示先重新执行 `1-1` 和 `2-*` 回到初始拓扑，或者按 README 进入对应切换后的验证步骤。

### 8. 计划内切换与故障转移是两条分支实验

`4-1.replication-planned-switchover.sh` 固定处理 node-a 主、node-b 从的计划内切换：停止外部教学写入、记录 node-a 当前 WAL LSN、等待 node-b 回放到该位置、停止 node-a、提升 node-b、验证 node-b 可写。脚本不自动把旧主重接为从；重接由 `5-2` 单独演示。

故障转移拆成：

- `4-2.replication-simulate-primary-failure.sh` 只停止 node-a，并显示 node-b 仍处于 recovery、不会自动提升。
- `4-3.replication-failover-promote-standby.sh` 确认 node-a 已停止后，通过 `SELECT pg_promote(true, 60)` 提升 node-b 并验证可写。

这两条是不同实验分支。执行故障转移实验前，应重新运行 `1-1`、`2-1`、`2-2`、`2-3` 恢复初始拓扑，不把上一条计划切换的结果隐式带入下一条实验。

### 9. 修复使用显式 source/target 参数，不做自动角色发现

`5-1.replication-rebuild-standby-from-primary.sh` 接收 `--primary` 和 `--target`，只允许 `pg-node-a`、`pg-node-b` 两个值且禁止相同。它在显式主库上准备复制规则与目标专用 slot，停止目标、清空目标数据，通过 `pg_basebackup` 完整重建并启动验证。典型调用为：

```bash
./scripts/5-1.replication-rebuild-standby-from-primary.sh \
  --primary pg-node-a --target pg-node-b
```

`5-2.replication-rejoin-old-primary-with-pg-rewind.sh` 同样使用显式参数。它停止旧主目标，在新主上准备 slot，执行 `pg_rewind --source-server=... --target-pgdata=...`，再写入 `standby.signal`、新的 `primary_conninfo` 和 `primary_slot_name` 后启动目标。典型调用为：

```bash
./scripts/5-2.replication-rejoin-old-primary-with-pg-rewind.sh \
  --primary pg-node-b --target pg-node-a
```

如果 `pg_rewind` 失败，脚本保持目标停止并提示使用 `5-1` 完整重建；禁止调用 `pg_resetwal` 或跳过 WAL 一致性。

### 10. pgBackRest 作为独立实例物理备份实验

两个节点挂载同一个宿主机备份仓库和同一份 pgBackRest 配置，但使用各自独立的 spool 目录。两个节点的容器内 `PGDATA` 路径保持一致，因此主从切换后仍可使用同一个 stanza；在初始两个独立集群阶段不得让两套不同 system identifier 的数据库同时写入这个 stanza。pgBackRest 实验应在 `2-*` 已把 node-b 重建为 node-a 的物理从库之后进行。

pgBackRest 脚本不自动发现主库，而是接受显式 `--node pg-node-a|pg-node-b`，默认使用初始主库 pg-node-a，并在执行备份前验证该节点可写。这样既保持学习流程明确，也允许切换后手动指定 pg-node-b。脚本拆分为：

1. `6-1.pgbackrest-init-stanza.sh`：在指定主库创建/检查 stanza、触发 WAL switch，并解释 stanza 是“数据库集群与备份仓库的登记关系”，不是复制槽。
2. `6-2.pgbackrest-check-archive.sh`：检查 `pg_stat_archiver`、执行 pgBackRest check，并证明新 WAL 已进入仓库。
3. `6-3.pgbackrest-backup-full.sh`：创建实例级 Full，输出 backup label、开始/结束时间和大小。
4. `6-4.pgbackrest-backup-incremental.sh`：创建 Incremental；执行前检查存在有效 Full，缺失则停止。普通 `6-3` Full 就是增量链基础，不增加“增量专用 Full”脚本。
5. `6-5.pgbackrest-show-info.sh`：只读显示 Full/Incremental 类型、label、时间、大小和依赖关系。
6. `6-6.pgbackrest-restore-verify.sh`：选择最新或明确 label，将完整依赖链恢复到 `docker/pgbackrest/restore-verify/data`，用独立验证容器启动并执行 SQL 验证。

恢复验证默认绑定 `127.0.0.1:35432`，不覆盖 pg-node-a、pg-node-b，也不复用它们的容器名称或数据目录。恢复脚本应清楚解释：Incremental 不是单独可恢复的“差异文件”，pgBackRest 会根据元数据组合对应 Full 和后续增量链完成恢复。删除恢复验证目录需要确认，但普通停止验证容器不删除恢复数据和日志。只有显式执行 `1-1.environment-init.sh` 回到全新实验起点时，才会在同一次确认中清除数据库数据、备份仓库、spool 和恢复验证状态。

### 11. 脚本保持教学性，但不堆叠复杂框架

公共脚本只提供路径/环境加载、清晰日志、两个 Compose 入口和少量 SQL 调用函数。主脚本保持从上到下可读，不实现通用拓扑发现器、状态机、JSON 协议、自动回滚和多层抽象。

涉及清空数据、停止主库、提升和 rewind 的脚本必须显示固定目标并要求确认；VS Code 默认入口不传 `--yes`。真正的 PostgreSQL 错误直接输出，避免为了“友好”吞掉有学习价值的原生诊断。

### 12. VS Code 与 README 完全对应真实脚本

`.vscode/launch.json` 只包含上述 16 个脚本入口，名称以相同编号开头，按 `01-environment`、`02-replication-init`、`03-replication-test`、`04-switchover-failover`、`05-repair`、`06-pgbackrest` 分组。配置项不使用无效的 `description` 字段；仅参数输入可使用 `inputs[].description`。

README 将实验写成分支流程图和逐步手册，列出固定端口、默认账号、密码来源、预期角色、文件变化、关键 SQL、恢复方式和单机 Demo 限制。

## Risks / Trade-offs

- [旧实验数据与未提交代码会被删除] → 用户已明确授权；实施前仅展示准确目标并停止旧容器，保留 `.git` 作为代码历史恢复手段，但不额外保留数据库数据。
- [允许任意网段访问会扩大攻击面] → 使用 SCRAM 和非空密码，README 明确要求仅在隔离网络使用，并提示通过宿主机防火墙限制来源。
- [两个容器位于同一宿主机，无法证明生产 HA] → 文档明确其只用于学习 PostgreSQL 角色和 WAL 流程。
- [固定方向脚本不适合任意生产拓扑] → 这是有意的教学取舍；修复脚本通过显式参数支持反向重接，但不自动猜测。
- [复制槽在从库长期离线时可能保留大量 WAL] → README 解释 slot 的作用和风险，初始化脚本重建前清理同名旧 slot；不增加复杂自动清理守护逻辑。
- [计划内切换期间无可写主库] → 这是无 VIP、无代理 Demo 的预期停写窗口；脚本输出停写开始和新主可写验证。
- [`pg_rewind` 可能因 WAL 缺失或前置条件失败] → 预置 `wal_log_hints=on`，失败时保持旧主停止并使用完整 `pg_basebackup` 重建。
- [主库故障后提升可能丢失未回放事务] → 故障转移脚本明确显示这是异步复制风险，不声称零数据丢失。
- [共享 pgBackRest 仓库是单点] → 学习环境接受此取舍；README 说明生产环境应使用独立仓库主机、对象存储或其他冗余存储。
- [两个独立集群不能共享一个 stanza] → pgBackRest 实验放在物理复制建立之后，确保两个节点具有相同 system identifier；初始化脚本明确拒绝在两个独立集群状态下建 stanza。
- [Incremental 依赖 Full 和前序链] → 增量脚本先检查 Full，信息脚本显示依赖链，隔离恢复实验实际证明整条链可恢复。
- [恢复实验误覆盖运行节点] → 恢复目标固定为白名单隔离目录和独立容器，拒绝把 node-a/node-b 的数据目录作为目标。

## Migration Plan

1. 记录并停止旧 `docker/docker-compose.yml` 所管理的容器，确认目标全部属于 `/www/wwwroot/postgres-ops-lab`。
2. 保留 `.git/` 和项目根目录，删除其余旧工作树、数据、备份、日志和配置。
3. 创建新目录、环境模板、共享学习镜像、两个独立 Compose、pgBackRest 仓库/恢复验证目录、节点配置、公共脚本、16 个教学脚本、VS Code 入口和 README。
4. 执行静态校验：Shell 语法、可执行权限、Compose 配置、launch/README 路径和编号一致性。
5. 执行 `1-1`，证明两个节点独立可写且可通过 `15432`、`25432` 连接。
6. 执行 `2-1`、`2-2`、`2-3`、`3-1`，证明 node-a → node-b 物理复制。
7. 执行 `6-1` 至 `6-6`，完成 stanza/WAL、Full、数据变化、Incremental、信息查看和隔离恢复验证。
8. 分别从干净初始拓扑演练计划切换分支和故障转移分支，再用 `5-2` 重接旧主。
9. 演练 `5-1` 完整重建从库，并保存简短验证记录。

回滚不恢复旧数据库数据；如新方案失败，可从保留的 Git 历史恢复旧代码，但旧运行数据按用户授权已删除。

## Open Questions

无。PostgreSQL 17 与 pgBackRest 固定小版本在实施时根据官方软件源可用组合确定，并同时写入 Dockerfile、Compose 与 README。
