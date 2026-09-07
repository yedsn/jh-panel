## ADDED Requirements

### Requirement: 单机主备归属创建
云监控 SHALL 允许管理人员创建唯一的本地版主备管理归属，并为该归属生成认证密钥。

#### Scenario: 创建唯一归属
- **WHEN** 管理人员提交非空且未使用的 `pair_id`
- **THEN** 云监控 SHALL 创建 `ha_pair`，设置 `pair_name=pair_id`、`status=unknown`、`status_text=等待当前机器上报`，生成高熵 `api_secret`，并返回创建结果供受信绑定流程使用。

#### Scenario: 拒绝重复或无效归属
- **WHEN** 管理人员提交空白或已存在的 `pair_id`
- **THEN** 云监控 MUST 返回明确错误，且不得新建或覆盖已有归属及其密钥。

### Requirement: 当前机器注册与认证
云监控 SHALL 只接受已创建归属的、携带有效密钥的本地版机器注册，并持久化当前机器身份。

#### Scenario: 注册当前机器
- **WHEN** 本地插件向 `POST /ha/api/local/register` 提交有效的 `pair_id`、`api_secret`、`host_id`、`host_name`、`host_ip`、角色和本地采集标识
- **THEN** 云监控 SHALL 按 `pair_id + host_id` 新增或更新 `ha_host_state`，保存注册身份及本机状态，并返回确认后的归属信息；插件 SHALL 静默保存密钥，不在本地版页面展示或要求输入该密钥。

#### Scenario: 拒绝未经授权的注册
- **WHEN** 注册请求引用不存在的归属、缺少机器标识或密钥不匹配
- **THEN** 云监控 MUST 拒绝请求，不得写入主机状态，并且不得在响应或普通运行日志中回显密钥。

#### Scenario: 不要求备用机
- **WHEN** 一个归属只有当前机器注册或上报
- **THEN** 云监控 SHALL 接受并展示该机器，且不得要求、等待或验证备用机注册。

### Requirement: 当前机器状态与任务摘要上报
云监控 SHALL 接收本地插件的最新状态快照和可选切换任务摘要，并仅以当前机器状态更新归属状态。

#### Scenario: 上报状态快照
- **WHEN** 已注册机器向 `POST /ha/api/local/report` 提交经认证的角色、在线状态、自检状态、采集状态、`health_detail` 和 `reported_at`
- **THEN** 云监控 SHALL 更新该机器的 `ha_host_state` 与 `last_report_at`，并刷新所属 `ha_pair` 的状态和状态说明。

#### Scenario: 上报切换任务摘要
- **WHEN** 经认证的状态报告包含有效 `switch_task`，其中包含 `switch_task_id`、目标角色、运行状态、状态说明、当前/下一步骤及步骤摘要
- **THEN** 云监控 SHALL 按 `switch_task_id` 新增或更新 `ha_switch_task`，关联该归属和主机，并将该任务 ID 保存为主机当前 `switch_task_id`。

#### Scenario: 接受无任务心跳
- **WHEN** 经认证的状态报告未包含 `switch_task` 或 `logs`
- **THEN** 云监控 SHALL 仍更新机器状态和报告时间，且不得创建空切换任务。

#### Scenario: 拒绝无效状态值或跨归属任务
- **WHEN** 报告包含不受支持的角色、在线、自检、采集或切换状态，或引用属于其他归属/机器的任务
- **THEN** 云监控 MUST 拒绝对应报告，不得用无效数据更新机器、任务或归属状态。

### Requirement: 单机归属状态计算与展示
云监控 SHALL 基于当前机器的最新有效上报生成并展示单机归属状态，而不推断双机拓扑。

#### Scenario: 等待首次上报
- **WHEN** 归属尚没有有效的当前机器状态
- **THEN** 云监控 SHALL 显示 `unknown` 和“等待当前机器上报”。

#### Scenario: 展示切换或故障状态
- **WHEN** 当前机器的切换任务正在运行，或最近切换失败/机器离线
- **THEN** 云监控 SHALL 分别显示 `switching` 及当前步骤，或 `danger` 及最近错误/离线说明。

#### Scenario: 展示自检和正常角色状态
- **WHEN** 当前机器未在切换或失败，且上报自检为 `warning`、`danger` 或角色为 `master`/`standby` 的正常状态
- **THEN** 云监控 SHALL 优先显示自检异常摘要，否则显示当前机器角色或“状态正常”。

#### Scenario: 不进行双机判断或远程控制
- **WHEN** 运维人员查看单机归属列表或详情
- **THEN** 云监控 MUST NOT 显示备用机状态、双主/双备/一主一备判断，且 MUST NOT 提供角色切换、继续、暂停或取消任务的控制入口。

### Requirement: 切换日志增量上报与读取
云监控 SHALL 将本地插件的任务日志增量追加到任务日志文件，并支持按偏移量读取新增内容且防止重试重复写入。

#### Scenario: 追加新日志序号
- **WHEN** 经认证的报告携带关联当前归属和主机的任务日志项，且每项具有该任务内正整数 `seq`、时间、级别、阶段、步骤和消息
- **THEN** 云监控 SHALL 将未接收过的 `(switch_task_id, seq)` 按序追加到该任务日志文件，并更新任务日志索引，不建立日志 SQLite 表。

#### Scenario: 忽略重复或乱序重试
- **WHEN** 插件重试已接收的日志序号，或同批/跨批日志乱序到达
- **THEN** 云监控 SHALL 仅追加尚未记录的序号，不得重复已有日志，且不得因缺失较小序号而丢弃较大序号。

#### Scenario: 读取日志增量
- **WHEN** 管理页面请求 `GET /ha/api/local/switch-log` 并提供有效任务 ID 及非负 `offset`
- **THEN** 云监控 SHALL 返回该任务日志文件从偏移量开始的内容、日志路径和下一次读取的字节偏移量。

#### Scenario: 拒绝无效日志读取
- **WHEN** 日志读取请求引用不存在的任务、非法偏移量或不属于 HA 日志目录的路径
- **THEN** 云监控 MUST 返回明确错误，且不得读取任意文件系统路径。

### Requirement: 本地插件上报集成
`ha_manager_local` SHALL 在云监控绑定可用时注册当前机器并上报本机状态、切换任务摘要和新增步骤日志，但本机切换不依赖云监控响应。

#### Scenario: 绑定后注册并周期上报
- **WHEN** 本地插件已配置云监控地址、归属、受信保存的密钥且启用上报
- **THEN** 插件 SHALL 在首次绑定或身份变化后注册，并按 `report_interval` 及状态变化向云监控报告本机快照。

#### Scenario: 切换过程上报
- **WHEN** 本地插件创建、开始、完成、失败或恢复一个本地切换步骤
- **THEN** 插件 SHALL 上报更新后的任务摘要及尚未上报的步骤日志，并为同一任务日志分配递增序号。

#### Scenario: 云监控不可用时继续本机操作
- **WHEN** 注册或报告因网络、认证或云监控服务错误失败
- **THEN** 插件 MUST 记录可诊断的上报失败信息并保留待重试数据，且 MUST NOT 阻止、回滚或伪造本机切换任务结果。
