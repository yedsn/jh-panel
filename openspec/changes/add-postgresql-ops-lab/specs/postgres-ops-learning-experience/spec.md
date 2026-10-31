## ADDED Requirements

### Requirement: 清晰一致的脚本命名
系统 SHALL 使用 `<组号>-<组内序号>.<功能域>-<动作>-<补充说明>.sh` 命名所有用户入口脚本，并让编号与 `.vscode/launch.json` 的调试入口一致；脚本主体继续使用 `environment-`、`backup-database-`、`pgbackrest-`、`replication-` 和 `switchover-` 前缀区分用途。

#### Scenario: 用户按名称查找脚本
- **WHEN** 用户列出 `scripts/` 第一层文件
- **THEN** 相同功能域的脚本按编号和名称自然聚合
- **THEN** 用户可通过调试入口编号直接定位对应脚本文件
- **THEN** 用户无需打开脚本即可大致判断用途和动作

### Requirement: 教学式过程日志
每个用户脚本 SHALL 输出任务目标、相关原理、前置条件、编号步骤、当前动作、验证依据和最终结果；日志 SHALL 解释关键 PostgreSQL 概念而不只回显底层命令。

#### Scenario: 执行复制初始化教学流程
- **WHEN** 用户运行 `4-1.replication-init.sh --pause`
- **THEN** 每个关键步骤执行前显示该步骤的动作及原理
- **THEN** 用户确认后才继续下一关键步骤
- **THEN** 完成后显示主从角色、LSN 和同步验证摘要

### Requirement: 交互与自动化模式
查询类脚本 SHALL 支持直接执行；初始化、恢复、修复、切换和清空脚本 SHALL 支持 `--pause`、`--yes`、`--verbose`、`--dry-run` 和 `--help` 中适用的参数。

#### Scenario: 试运行高风险操作
- **WHEN** 用户对修复或切换脚本使用 `--dry-run`
- **THEN** 系统显示计划、目标和检查项但不修改容器、数据目录或数据库状态

#### Scenario: 非交互自动执行
- **WHEN** 自动化调用者使用 `--yes` 且所有前置条件满足
- **THEN** 脚本不等待人工输入并通过稳定退出码报告结果

### Requirement: 敏感信息保护
系统 SHALL 在日志中遮盖密码、完整认证连接串和敏感环境变量，并避免把密码作为可被进程列表直接读取的命令行参数。

#### Scenario: 显示数据库连接信息
- **WHEN** 脚本输出远程连接示例或执行带认证的数据库操作
- **THEN** 日志中的密码显示为掩码或通过受限凭据文件提供

### Requirement: 可验证的失败结果
所有脚本 SHALL 对失败返回非零退出码，并输出失败阶段、实际状态和安全的下一步建议；状态类脚本 SHALL 支持可选 JSON 输出。

#### Scenario: 前置检查失败
- **WHEN** 备份、修复或切换的前置条件不满足
- **THEN** 脚本停止在修改动作之前并返回非零退出码
- **THEN** 日志明确区分“未执行”和“执行后失败”

### Requirement: 学习手册按实验组织
系统 SHALL 提供 README，按照环境启动、复制初始化、单库备份、Full/Incremental、恢复验证、从库修复和主从切换组织可复制执行的实验。

#### Scenario: 新用户完成主线实验
- **WHEN** 用户按 README 顺序在干净环境执行命令
- **THEN** 每个实验说明目标、预期状态、命令、观察点和清理方式
- **THEN** 用户可从远程客户端观察两个固定端口在切换前后的数据和角色变化
