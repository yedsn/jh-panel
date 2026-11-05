## ADDED Requirements

### Requirement: 旧项目可被限定范围地彻底重建
系统 SHALL 在实施时停止旧项目管理的容器，并删除 `/www/wwwroot/postgres-ops-lab` 内除项目根目录和 `.git/` 之外的旧代码、配置、脚本、数据库数据、备份、日志和状态，然后写入新项目。系统 MUST NOT 删除项目目录之外的容器、卷、网络、镜像或文件。

#### Scenario: 清理旧项目工作树和运行数据
- **WHEN** 实施者应用本变更
- **THEN** 旧 Compose、旧脚本和旧运行数据被移除，新项目从空白状态生成，并保留 Git 历史供代码追溯

#### Scenario: 拒绝越界清理
- **WHEN** 任一待删除目标解析为空、根目录、项目上级目录或项目目录之外的位置
- **THEN** 清理操作 MUST 失败并保持该目标不变

### Requirement: 两个节点使用独立 Compose 项目
系统 SHALL 为 `pg-node-a` 和 `pg-node-b` 分别提供 `docker/pg-node-a/docker-compose.yml` 和 `docker/pg-node-b/docker-compose.yml`，每个 Compose 项目 SHALL 只管理对应的一个 PostgreSQL 节点。

#### Scenario: 检查节点目录和 Compose 边界
- **WHEN** 学习者查看 `docker/pg-node-a` 和 `docker/pg-node-b`
- **THEN** 每个目录包含自己的 Compose、配置、数据、日志和状态路径，且不会通过一个 Compose 文件同时启动两个数据库节点

### Requirement: 节点身份、网络和端口稳定
系统 SHALL 创建共享外部 Docker 网络 `postgres-ops-lab-network`，容器内节点 SHALL 通过 `pg-node-a:5432` 和 `pg-node-b:5432` 通信；宿主机 SHALL 分别发布 `15432` 和 `25432`，端口只表示节点身份而不表示当前角色。

#### Scenario: 从宿主机或其他机器连接两个节点
- **WHEN** 客户端使用正确账号和 `.env` 中的密码连接宿主机 `15432` 与 `25432`
- **THEN** 客户端分别连接到 pg-node-a 与 pg-node-b，并可通过 SQL 查询实际恢复状态

### Requirement: 环境初始化产生两个独立可写实例
`1-1.environment-init.sh` SHALL 显式清理两个新节点的数据/日志/状态、pgBackRest 仓库/spool/state 和隔离恢复目录，创建共享网络，分别启动两个 Compose 项目并等待就绪；它 MUST NOT 创建复制账号、复制槽、stanza、`standby.signal` 或上游连接配置。

#### Scenario: 初始化后的起始状态
- **WHEN** 学习者成功执行 `1-1.environment-init.sh`
- **THEN** 两个节点的 `pg_is_in_recovery()` 都返回 `false`，两个节点都能独立写入和读取自己的验证数据，旧备份仓库和恢复实验状态为空

### Requirement: 数据目录随容器重建持久化
系统 SHALL 将每个节点的 PostgreSQL 数据、日志和教学状态绑定到该节点 Docker 目录下的显式宿主机路径，并将 pgBackRest 仓库、spool、恢复验证数据和日志绑定到明确的项目内宿主机路径；普通停止、启动或容器重建 MUST NOT 自动删除这些数据。

#### Scenario: 普通容器重建保留数据
- **WHEN** 学习者在不执行 `1-1.environment-init.sh` 清理步骤的情况下重建某个节点容器
- **THEN** 该节点原有数据库文件和教学记录仍然存在

#### Scenario: 普通容器重建保留物理备份
- **WHEN** 学习者重建两个数据库容器但没有执行环境清理
- **THEN** pgBackRest 仓库、备份集和隔离恢复结果仍保留在宿主机目录
