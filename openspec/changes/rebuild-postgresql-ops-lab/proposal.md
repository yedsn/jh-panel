## Why

现有 `/www/wwwroot/postgres-ops-lab` 是一个已经多次演进的 PostgreSQL Demo，目录、Compose、脚本和运行数据混合了早期 pgBackRest、自动角色判断及多场景实验，已经不适合继续作为单一、易学的主从复制学习项目。现在需要明确授权一次破坏性重建：清理旧项目文件和旧运行数据，按已经确认的“两个独立 Docker 节点 + 固定方向 + 单一职责脚本”方案从零建立可重复的学习环境。

## What Changes

- **BREAKING** 清空 `/www/wwwroot/postgres-ops-lab` 旧项目代码、Compose、配置、脚本、日志、状态、备份和 PostgreSQL 数据，重新生成项目。
- **BREAKING** 不再沿用旧的单 Compose 双实例结构；改为 `docker/pg-node-a/` 和 `docker/pg-node-b/` 两个独立 Docker Compose 目录，每个目录对应一个 PostgreSQL 容器和自己的持久化数据目录。
- 新建两个独立、可读写的 PostgreSQL 空白实例；`1-1.environment-init.sh` 只负责环境和节点初始化，不创建复制关系。
- 将物理复制流程拆成独立脚本：主库准备、从库 `pg_basebackup`、从库启动验证。
- 提供固定方向的主写从读验证脚本，清楚观察 WAL 物理复制结果。
- 将计划内切换拆成明确的“停止旧主/提升从库”学习流程，并将主库故障模拟与故障转移拆成不同脚本。
- 将从库完整重建和旧主 `pg_rewind` 重接拆成两个独立修复脚本；不做自动角色发现、自动故障转移或复杂编排。
- 在原生 WAL 主从学习流程之外增加独立的 pgBackRest 学习分支：仓库/stanza 与 WAL 归档初始化、归档检查、实例 Full、实例 Incremental、备份信息查看和隔离恢复验证。
- 普通 Full 备份直接作为后续 Incremental 的基础，不设置“实例增量-全量备份”这种重复入口；Incremental 缺少有效 Full 时明确停止并指导先执行 Full。
- pgBackRest 恢复只写入隔离恢复目录并启动独立验证容器，不覆盖 pg-node-a 或 pg-node-b。
- 逻辑备份、单库备份、单表备份及多余高级实验不进入本次重建范围，避免干扰物理复制和实例物理备份两条学习主线。
- 重新生成与脚本编号一致的 `.vscode/launch.json`、README、`.env.example`、公共脚本和基础自检。

## Capabilities

### New Capabilities

- `postgres-lab-clean-rebuild`: 清理旧项目并重建两个独立 Docker 节点、持久化目录、环境配置和远程端口。
- `postgres-physical-replication-learning`: 通过复制账号、`pg_hba.conf`、复制槽、`pg_basebackup`、`standby.signal` 和 WAL Receiver 建立并验证物理主从。
- `postgres-replication-switching`: 分别演示计划内切换、主库停止、从库提升，避免把多个角色变化场景合成黑盒脚本。
- `postgres-replication-repair`: 提供从库 `pg_basebackup` 重建和旧主 `pg_rewind` 重接两条清晰修复路径。
- `postgres-pgbackrest-learning`: 使用 pgBackRest 学习 WAL 归档、实例 Full/Incremental 备份、依赖链查看和隔离恢复验证。
- `postgres-lab-learning-interface`: 提供编号脚本、中文教学日志、固定端口、持久化路径、VS Code 分组和最小公共脚本约定。

### Modified Capabilities

无。

## Impact

- 影响 `/www/wwwroot/postgres-ops-lab` 的全部项目文件和项目内运行数据；该目录会被重建，旧数据不保留。
- 依赖 Docker、Docker Compose 和基于 PostgreSQL 17 官方镜像构建的固定版本学习镜像；镜像额外安装 pgBackRest，使 PostgreSQL 的 `archive_command` 和备份命令能在数据库容器内执行。
- 两个节点分别发布宿主机 `15432`、`25432` 端口，隔离恢复验证实例默认只绑定宿主机回环地址的 `35432` 端口。
- 新增 `scripts/`、`docker/pg-node-a/`、`docker/pg-node-b/`、`docker/network/`、`.vscode/launch.json` 等项目结构。
- 新增 `docker/image/`、`docker/pgbackrest/config/`、`docker/pgbackrest/repository/`、节点独立 spool、隔离恢复数据与日志目录；备份仓库和恢复结果在容器重建后仍保留。
- 不修改江湖面板、1Panel 或其他项目，不操作项目目录之外的容器、镜像、卷、网络和数据库。
- 重建后的项目是单机教学 Demo，不代表生产 HA；不包含 Patroni、VIP、自动选主、自动故障转移或面板集成。
