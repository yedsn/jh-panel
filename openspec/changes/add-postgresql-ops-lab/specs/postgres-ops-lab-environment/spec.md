## ADDED Requirements

### Requirement: 双节点 PostgreSQL 学习环境
系统 SHALL 在 `/www/wwwroot/postgres-ops-lab` 提供一个 Docker Compose 项目，运行 `pg-node-a` 和 `pg-node-b` 两个 PostgreSQL 节点，并使用包含 pgBackRest 和 PostgreSQL 官方运维工具的同一自定义镜像。

#### Scenario: 构建并启动学习环境
- **WHEN** 用户执行环境构建和启动脚本
- **THEN** 系统成功构建固定版本的自定义镜像并启动学习环境
- **THEN** node-a 可正常提供 PostgreSQL 服务
- **THEN** 尚未初始化复制的 node-b 不得作为第二个可写主库提供服务

### Requirement: 两个节点支持远程访问
系统 SHALL 将 node-a 和 node-b 的 PostgreSQL 端口分别映射到可配置且互不冲突的宿主机端口，默认使用 `15432` 和 `25432`，并使用 SCRAM 密码认证及可配置来源 CIDR。

#### Scenario: 从其他机器分别连接两个节点
- **WHEN** 客户端来自允许的 CIDR 且提供正确账号密码
- **THEN** 客户端可通过服务器 IP 和 `15432` 连接 node-a
- **THEN** 客户端可通过服务器 IP 和 `25432` 连接 node-b

#### Scenario: 端口始终表示节点而非角色
- **WHEN** 主从角色发生切换
- **THEN** `15432` 仍指向 node-a 且 `25432` 仍指向 node-b
- **THEN** 状态输出明确标识每个端口当前对应的角色和可写性

### Requirement: 数据与备份持久化
系统 SHALL 将 Dockerfile、Compose、镜像入口、配置、两个节点的数据目录、逻辑备份、pgBackRest 仓库、spool、日志、恢复验证目录和运行状态统一保存在宿主机项目的 `docker/` 目录，不得仅保存在容器可写层。

#### Scenario: 重建容器后数据仍然存在
- **WHEN** 用户停止、删除并重新创建 Compose 容器但未执行 reset
- **THEN** 原有数据库数据、备份仓库和脚本状态仍然存在
- **THEN** 节点可基于原持久化目录恢复运行

### Requirement: 安全重置实验环境
系统 SHALL 提供显式的环境重置脚本，并在删除数据前验证目标为项目内已知目录、展示绝对路径并要求确认；脚本 MUST 拒绝空路径、根目录、项目上级目录和未识别目录。

#### Scenario: 用户取消重置
- **WHEN** 用户未确认或输入退出指令
- **THEN** 系统不删除任何数据、备份或配置

#### Scenario: 非法删除目标被拒绝
- **WHEN** 重置脚本解析出的目标不在项目允许清单中
- **THEN** 脚本以非零状态退出并显示拒绝原因

### Requirement: 演示数据与环境状态
系统 SHALL 提供创建和追加 Demo 数据的脚本，以及显示容器、端口、节点角色和持久化目录状态的脚本。

#### Scenario: 初始化演示数据
- **WHEN** 用户运行 Demo 数据初始化脚本
- **THEN** 当前主库中创建可重复验证的数据库、表和记录
- **THEN** 重复执行不会无提示地破坏已有演示数据
