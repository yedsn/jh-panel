## 1. 项目骨架与安全基线

- [x] 1.1 在 `/www/wwwroot/postgres-ops-lab` 创建项目骨架：根目录放 README、环境变量、scripts/tests，`docker/` 统一放 Dockerfile、Compose、image、config、data、backup、spool、logs 和 state
- [x] 1.2 固定 PostgreSQL 17 与 pgBackRest 镜像/软件版本，构建包含 pgBackRest、pg_dump、pg_restore、pg_basebackup 和 pg_rewind 的自定义镜像
- [x] 1.3 定义 `.env.example`，包含节点端口、验证端口、数据库密码、复制密码、允许访问 CIDR、stanza 和数据目录等参数，并确保实际 `.env` 不进入版本控制
- [x] 1.4 编写 PostgreSQL 基础配置与 `pg_hba.conf` 模板，启用 SCRAM、远程监听、WAL 复制、归档、复制槽所需参数以及 pg_rewind 前置条件
- [x] 1.5 编写 Compose 编排：node-a 正常初始化、node-b 空数据时等待复制初始化，两个节点使用固定名称和持久化 bind mount
- [x] 1.6 增加启动前检查，验证 Docker/Compose、端口冲突、目录权限、架构、磁盘空间和必要环境变量

## 2. 脚本公共能力与教学输出

- [x] 2.1 实现 `scripts/common/config.sh`，安全加载项目绝对路径、环境变量、节点/端口和已知持久化目录
- [x] 2.2 实现统一教学日志库，支持标题、目标、原理、编号步骤、动作、验证、成功、警告、失败和敏感信息遮盖
- [x] 2.3 实现统一参数与确认库，支持适用脚本的 `--pause`、`--yes`、`--verbose`、`--dry-run` 和 `--help`
- [x] 2.4 实现 Docker/PostgreSQL 公共函数，包括容器状态、SQL 执行、节点角色发现、主从唯一性检查、LSN/时间线读取和稳定退出码
- [x] 2.5 为状态类公共函数实现人类可读输出和 `--json` 输出，并为关键错误路径增加可执行的自检脚本

## 3. 环境生命周期与远程连接

- [x] 3.1 实现 `1-1.environment-build.sh`、`1-2.environment-start.sh` 和 `1-7.environment-stop.sh`，输出构建/启动原理和节点连接信息
- [x] 3.2 实现 `1-3.environment-show-status.sh`，显示容器、节点端口、数据库可达性、角色、可写性和持久化目录
- [x] 3.3 实现 `1-4.environment-seed-demo-data.sh`，可幂等创建 Demo 数据并支持追加唯一测试记录
- [x] 3.4 实现 node-a/node-b 连接辅助脚本或等价清晰入口，打印本机和远程 `psql` 示例但不泄露密码
- [x] 3.5 实现 `1-8.environment-reset.sh`，仅允许清理项目内白名单目录，拒绝危险路径并要求显式确认
- [x] 3.6 构建并启动初始环境，验证 node-a 可用、node-b 不会在复制初始化前成为第二个可写主库
- [x] 3.7 从另一网络命名空间或远程客户端路径验证 `15432` 和 `25432` 的独立访问、CIDR 限制与 SCRAM 认证

## 4. 单数据库逻辑备份

- [x] 4.1 实现 `2-1.backup-database-create.sh`，动态选择当前主库并用 pg_dump custom 格式保存指定数据库及元数据
- [x] 4.2 实现 `2-2.backup-database-list.sh`，显示逻辑备份文件、数据库、时间、大小和验证状态
- [x] 4.3 实现 `2-3.backup-database-restore.sh`，默认恢复到新数据库，对已存在目标执行安全拒绝或明确确认
- [x] 4.4 实现 `2-4.backup-database-verify.sh`，比较 schema、表数量和 Demo 记录，并说明逻辑备份不能作为 pgBackRest Incremental 基础
- [x] 4.5 实际执行单库备份、恢复到新库和一致性验证，并验证源库保持不变及失败退出码正确

## 5. pgBackRest、WAL 与物理备份

- [x] 5.1 创建 pgBackRest 配置，挂载共享持久化仓库与每节点独立 spool，并确保切换后任一当前主库均可执行归档和备份
- [x] 5.2 实现 `3-1.pgbackrest-init-stanza.sh`，创建/验证 stanza、触发 WAL switch 并证明 WAL 已归档
- [x] 5.3 实现 `3-2.pgbackrest-check-archive.sh`，检查 PostgreSQL archiver、仓库权限、最近成功/失败和 WAL 可达性
- [x] 5.4 实现 `3-3.pgbackrest-backup-full.sh`，从动态发现的当前主库创建普通 Full 并显示标签、大小和基础备份含义
- [x] 5.5 实现 `3-4.pgbackrest-backup-incremental.sh`，预先验证存在有效 Full，缺失时停止并指导执行 Full
- [x] 5.6 实现 `3-5.pgbackrest-show-info.sh`，输出 Full/Incremental 标签、依赖链、时间、大小和可选 JSON
- [x] 5.7 实现 `3-6.pgbackrest-restore-verify.sh`，恢复最新或指定标签到隔离目录，用临时实例验证数据库、表和 Demo 数据
- [x] 5.8 实际完成 stanza/WAL 检查、Full、数据变化、Incremental 和隔离恢复验证，并确认主从节点未被覆盖
- [x] 5.9 模拟缺失 Full、仓库不可写或恢复链不完整，验证脚本安全停止、诊断日志和非零退出码

## 6. WAL 物理复制初始化与状态

- [x] 6.1 实现 `4-1.replication-init.sh`，依次创建复制账号/槽、准备 base backup、写入连接配置和 `standby.signal`、启动 node-b 并等待追平
- [x] 6.2 实现 `4-2.replication-show-status.sh`，显示节点、固定端口、角色、可写性、发送/接收/回放 LSN、延迟、slot、时间线和 WAL Receiver，并支持 JSON
- [x] 6.3 实现 `4-3.replication-wait-until-synced.sh`，按超时等待从库回放到目标 LSN，并区分接收与回放进度
- [x] 6.4 实现 `4-4.replication-test-write-and-read.sh`，只向动态发现的主库写入唯一记录并从从库验证读取
- [x] 6.5 实际初始化 node-a → node-b 复制，验证 node-b 为 recovery 状态、远程只读、WAL 流复制和归档补取均正常
- [x] 6.6 验证复制断开时状态脚本不会把“容器运行”误报为“复制健康”

## 7. 从库损坏模拟与修复

- [x] 7.1 实现 `5-1.replication-simulate-standby-damage.sh`，只允许针对已确认从库执行并保护主库与备份仓库
- [x] 7.2 实现 `5-2.replication-rebuild-standby-from-primary.sh`，隔离旧数据并通过 pg_basebackup 从当前主库重建从库
- [x] 7.3 实现 `5-3.replication-repair-standby-from-pgbackrest.sh`，从物理备份恢复从库并通过归档及流复制追平当前主库
- [x] 7.4 实现 `5-4.replication-rejoin-old-primary-with-pg-rewind.sh`，安全执行 pg_rewind、写 standby 配置并重新加入；失败时引导完整重建
- [x] 7.5 实际破坏从库并验证 pg_basebackup 重建路径恢复复制和数据一致性
- [x] 7.6 再次破坏从库并验证 pgBackRest 恢复路径能够补齐 WAL、恢复复制和数据一致性
- [x] 7.7 构造可控时间线分叉并验证 pg_rewind 重接；同时验证不满足前置条件时不会调用 pg_resetwal 或跳过 WAL

## 8. 计划内主从切换

- [x] 8.1 实现 `6-1.switchover-check-readiness.sh`，检查单主单从、复制/回放、延迟、归档、磁盘和 pg_rewind 前置条件
- [x] 8.2 实现 `6-2.switchover-execute.sh`，暂停 Demo 写入、等待追平、停止旧主、提升从库、对齐并以 standby 方式启动旧主
- [x] 8.3 实现切换状态持久化与失败处理，任一步失败时停止自动推进、保持写入暂停并显示两个节点实际状态和恢复建议
- [x] 8.4 实现 `6-3.switchover-verify.sh`，确认新主可写、旧主处于 recovery、测试写入可反向复制且节点端口保持不变
- [x] 8.5 以 `--pause` 教学模式完成 node-a → node-b 切换，记录每一步角色、LSN、时间线和远程端口观察结果
- [x] 8.6 再执行一次反向切换或等价演练，验证脚本不依赖固定主库节点并始终防止双主
- [x] 8.7 验证仅设置普通只读参数的节点不会被切换验证误判为物理从库

## 9. 文档、重建验证与最终验收

- [x] 9.1 编写 README 快速开始，说明架构、固定端口、角色动态变化、安全警告、目录持久化和完整脚本索引
- [x] 9.2 编写七个循序渐进的实验：环境、复制、单库备份、Full、Incremental/恢复、从库修复、主从切换
- [x] 9.3 为每个实验记录目标、原理、命令、预期输出、远程观察点、失败排查和清理方式
- [x] 9.4 删除并重建两个容器，验证数据库数据、主从关系、逻辑备份和 pgBackRest 仓库未丢失
- [x] 9.5 执行所有脚本的 `--help`、`--dry-run`、确认取消、错误输入和敏感信息检查，修复不一致行为
- [x] 9.6 从干净 reset 状态按 README 完整执行所有实验，保存最终验证日志并确认全部规格场景通过
- [x] 9.7 在 README 明确标注该项目为单机学习 Demo，不等同于生产 HA，且不包含 Patroni、VIP、自动故障转移或面板集成
