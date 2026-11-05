## 1. 安全清理旧项目

- [x] 1.1 检查旧项目的 Git 状态、旧 Compose 配置、容器名称和项目内持久化路径，形成准确清理目标清单
- [x] 1.2 停止并移除旧 `/www/wwwroot/postgres-ops-lab/docker/docker-compose.yml` 管理的容器，只处理属于该项目的资源
- [x] 1.3 保留项目根目录和 `.git/`，删除其余旧工作树、PostgreSQL 数据、备份、WAL/spool、日志、配置和状态，并验证未触碰项目外路径

## 2. 重建双节点 Docker 结构

- [x] 2.1 创建根目录 README、`.env.example`、gitignored `.env`、`.gitignore`、`.vscode/`、`scripts/common/` 和 `tests/` 骨架
- [x] 2.2 创建 `docker/pg-node-a/` 和 `docker/pg-node-b/`，每个节点包含独立 Compose、config、data、logs、spool 和 state 目录
- [x] 2.3 创建 `docker/image/Dockerfile`，以固定 PostgreSQL 17 官方镜像为基础安装固定版本 pgBackRest，并让两个节点复用同一学习镜像
- [x] 2.4 创建 `docker/pgbackrest/config`、`repository`、`state` 和 `restore-verify` 数据/日志/Compose 目录，确保仓库与恢复结果持久化
- [x] 2.5 为两个节点编写独立 Compose，使用共享学习镜像、稳定容器名、节点端口 `15432`/`25432`、pgBackRest 挂载和共享外部网络
- [x] 2.6 为两个节点编写 PostgreSQL/`pg_hba.conf` 配置，启用远程监听、SCRAM、WAL 物理复制参数、`wal_log_hints`、archive/restore command 和学习环境任意网段访问
- [x] 2.7 创建 `postgres-ops-lab-network` 的明确初始化方式，并验证两个独立 Compose 均能连接该外部网络、通过节点名互相解析

## 3. 最小公共脚本和环境初始化

- [x] 3.1 实现 `scripts/common/config.sh`，只加载项目绝对路径、`.env`、两个节点固定信息和白名单数据目录
- [x] 3.2 实现 `scripts/common/log.sh`、`docker.sh` 和 `postgresql.sh`，仅提供教学日志、两个 Compose 调用、等待就绪和 SQL 执行等必要函数
- [x] 3.3 实现 `1-1.environment-init.sh`，确认后清空两个节点数据/日志/状态、pgBackRest 仓库/spool/state 和隔离恢复目录，创建网络，依次启动节点并验证两个节点均独立可写且不在 recovery
- [x] 3.4 验证初始化脚本不创建复制账号、复制槽、stanza、`standby.signal`、`primary_conninfo` 或任何主从关系
- [x] 3.5 从宿主机和可用远程客户端验证 `15432`、`25432` 使用 `.env` 密码均可独立连接，并记录任意网段开放的安全提示

## 4. 建立和验证初始物理复制

- [x] 4.1 实现 `2-1.replication-primary-prepare.sh`，固定在 pg-node-a 创建复制账号、复制授权和 `slot_pg_node_b`，不修改 node-b 数据
- [x] 4.2 实现 `2-2.replication-standby-basebackup.sh`，停止并清空 pg-node-b 后执行带 `-X stream -R -S slot_pg_node_b -P -c fast` 的 `pg_basebackup`，逐项注释和解释参数
- [x] 4.3 实现复制凭据文件及权限设置，使 `primary_conninfo` 可认证但日志和示例不泄露密码
- [x] 4.4 实现 `2-3.replication-standby-start-verify.sh`，启动 pg-node-b 并验证 recovery、WAL Receiver streaming 和主库 WAL sender
- [x] 4.5 实现 `3-1.replication-test-write-read.sh`，固定 node-a 写入唯一记录、node-b 读取相同记录，并在角色不匹配时明确失败
- [x] 4.6 从空白环境完整执行 `1-1`、`2-1`、`2-2`、`2-3`、`3-1`，保存初始复制验证结果

## 5. 拆分计划切换与故障提升

- [x] 5.1 实现 `4-1.replication-planned-switchover.sh`，等待 node-b 回放到目标 LSN、停止 node-a、提升 node-b 并验证可写，不自动重接旧主
- [x] 5.2 从干净初始主从状态执行计划切换，验证 node-b 为唯一运行中的可写节点且 node-a 保持停止
- [x] 5.3 实现 `4-2.replication-simulate-primary-failure.sh`，只停止 node-a 并证明 node-b 不会自动提升
- [x] 5.4 实现 `4-3.replication-failover-promote-standby.sh`，仅在 node-a 已停止时提升 node-b，验证 recovery=false 和写入成功
- [x] 5.5 重新建立干净初始主从后依次执行故障模拟与故障提升，验证脚本职责分离和双主保护

## 6. 拆分两种主从修复路径

- [x] 6.1 实现 `5-1.replication-rebuild-standby-from-primary.sh` 的 `--primary`/`--target` 参数验证、目标确认、目标清理、目标 slot、`pg_basebackup` 和复制验证
- [x] 6.2 构造可丢弃从库后分别验证 node-a → node-b 以及 node-b → node-a 的完整重建方向，不修改显式主库数据
- [x] 6.3 实现 `5-2.replication-rejoin-old-primary-with-pg-rewind.sh`，按显式参数执行停止、slot 准备、`pg_rewind`、standby 配置、启动和追平验证
- [x] 6.4 在计划切换或故障提升后用 `--primary pg-node-b --target pg-node-a` 验证旧主成功作为从库重接
- [x] 6.5 模拟 `pg_rewind` 不可完成的失败路径，验证旧主保持停止、不调用 `pg_resetwal` 并提示使用 `5-1` 完整重建

## 7. pgBackRest WAL 与实例物理备份

- [x] 7.1 编写共享 pgBackRest 配置，为两个节点挂载同一仓库/配置和各自 spool，并验证两个节点属于同一物理集群后才允许创建 stanza
- [x] 7.2 实现 `6-1.pgbackrest-init-stanza.sh`，支持显式 `--node`，创建/检查 stanza、触发 WAL switch 并解释 stanza 与复制槽区别
- [x] 7.3 实现 `6-2.pgbackrest-check-archive.sh`，检查 `pg_stat_archiver`、pgBackRest check 和新 WAL 仓库可达性
- [x] 7.4 实现 `6-3.pgbackrest-backup-full.sh`，创建实例 Full 并显示 label、类型、时间、大小及其作为 Incremental 基础的含义
- [x] 7.5 实现 `6-4.pgbackrest-backup-incremental.sh`，在已有 Full 时创建 Incremental，缺少 Full 时明确停止并指导执行 `6-3`
- [x] 7.6 实现 `6-5.pgbackrest-show-info.sh`，只读显示 Full/Incremental 的 label、时间、大小、版本和依赖链
- [x] 7.7 实现 `6-6.pgbackrest-restore-verify.sh`，将最新或指定 label 恢复到白名单隔离目录，用独立容器和 `127.0.0.1:35432` 验证数据
- [x] 7.8 在数据库写入变化前后依次完成 stanza、归档检查、Full、Incremental、信息查看和隔离恢复实验，证明恢复链可用且两个运行节点未被覆盖
- [x] 7.9 验证缺少 Full、仓库不可写、错误 label 和恢复目标越界等失败路径均安全停止且不泄露凭据

## 8. VS Code、文档与静态测试

- [x] 8.1 重写 `.vscode/launch.json`，只保留十六个编号一致的 `node-terminal` 入口，并按六个功能组排序且不使用配置级 `description`
- [x] 8.2 重写 README，说明架构、目录、端口、密码、远程访问风险、初始复制步骤、两条切换分支、两种修复路径、pgBackRest 实验、文件变化和预期状态
- [x] 8.3 在 README 明确普通 Full 就是 Incremental 基础，Incremental 恢复由 pgBackRest 解析依赖链；逻辑/单库/单表备份、自动选主、VIP、Patroni 和生产 HA 不属于本项目
- [x] 8.4 实现 `tests/all-shell-syntax-test.sh` 和 `tests/compose-config-test.sh`，检查脚本语法/权限、两个节点 Compose、恢复验证 Compose、README 和 launch 引用
- [x] 8.5 执行全部静态测试，检查 `.env`、数据、仓库、恢复目录、日志和凭据未进入 Git，检查运行日志不泄露密码

## 9. 最终从零验收

- [x] 9.1 再次执行 `1-1.environment-init.sh`，确认节点数据、pgBackRest 仓库和恢复状态均被清除，且两个独立可写实例可重复得到
- [x] 9.2 按 README 完整完成初始复制、主写从读和 pgBackRest Full/Incremental/隔离恢复实验，确认命令、编号、VS Code 入口与实际文件一致
- [x] 9.3 分别从干净初始拓扑完成计划切换 + pg_rewind 重接、故障模拟 + 提升 + 修复两个分支
- [x] 9.4 重建容器但不清理数据，验证节点数据、角色相关文件、pgBackRest 仓库和恢复记录仍在宿主机持久化目录
- [x] 9.5 记录固定 PostgreSQL/pgBackRest 版本、最终节点角色、备份链、已执行实验、单机 Demo 限制和项目外资源未被操作的最终验收摘要
