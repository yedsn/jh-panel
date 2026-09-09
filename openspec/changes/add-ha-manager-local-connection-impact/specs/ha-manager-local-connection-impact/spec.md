## ADDED Requirements

### Requirement: 采集本机 OpenResty 连接快照
本地主备管理插件 SHALL 在 OpenResty 运行时采集仅本机可访问的 `stub_status` 页面，并返回结构化连接快照。快照 SHALL 包含活动连接数、Reading、Writing、Waiting、采集时间和可用状态；插件 MUST 根据实际 OpenResty 配置定位状态页监听端口，而不是假定端口为 80。

#### Scenario: 状态页可正常访问
- **WHEN** OpenResty 正在运行且本机 `stub_status` 返回有效状态文本
- **THEN** 插件返回 `available=true`，并包含 `active`、`reading`、`writing`、`waiting` 和采集时间

#### Scenario: 状态页监听端口不是 80
- **WHEN** OpenResty 配置中的状态 server 使用非 80 监听端口
- **THEN** 插件从实际配置定位该端口并成功获取对应连接快照

#### Scenario: 状态页不可用或返回异常内容
- **WHEN** OpenResty 未运行、状态页无法访问、端口无法定位或响应不符合 `stub_status` 格式
- **THEN** 插件返回 `available=false` 和可展示的原因摘要，且不将普通 HTML 或异常文本解析为连接指标

### Requirement: 总览展示当前连接影响范围
本地主备管理插件 SHALL 在总览页的对外服务信息中展示最新连接快照。界面 MUST 将 `active` 标识为“当前活动连接”，并展示 Reading、Writing、Waiting 和采集时间；界面 MUST 不将任何连接指标标识为真实用户人数。

#### Scenario: 当前连接快照可用
- **WHEN** 总览状态包含可用的连接快照
- **THEN** 对外服务区域展示当前活动连接数、Reading、Writing、Waiting 和采集时间

#### Scenario: 当前连接快照不可用
- **WHEN** 总览状态包含不可用的连接快照
- **THEN** 对外服务区域展示“当前连接数暂时无法获取”及原因摘要，同时继续展示 OpenResty 的服务状态

### Requirement: 连接详情说明 keep-alive 留存机制
本地主备管理插件 SHALL 在连接详情中说明，已完成网页请求的 TCP 连接可能因 HTTP keep-alive 暂时保持。插件 MUST 从当前 OpenResty 配置读取 `keepalive_timeout` 并展示解析后的空闲超时时间；读取或解析失败时 MUST 显示未知状态，不得用写死的超时时间替代。

#### Scenario: 配置了 keepalive 超时
- **WHEN** 当前 OpenResty 配置包含可解析的 `keepalive_timeout 60;`
- **THEN** 连接详情说明空闲连接通常会在约 60 秒后断开，并说明客户端可能提前断开或重新建立连接

#### Scenario: keepalive 超时无法读取
- **WHEN** 当前 OpenResty 配置不存在、未设置或包含无法解析的 `keepalive_timeout`
- **THEN** 连接详情仍可展示，并将超时时间标识为未能识别

### Requirement: 关闭前提示连接中断风险
本地主备管理插件 SHALL 在操作员关闭对外服务前获取连接快照并显示确认弹窗。确认弹窗 MUST 告知操作员关闭 OpenResty 可能中断当前连接，展示活动连接与分类指标；操作员 MUST 明确确认后，系统才可执行关闭操作。

#### Scenario: 有活动连接时确认关闭
- **WHEN** 操作员点击“关闭对外服务”且预览快照显示一个或多个活动连接
- **THEN** 系统显示连接分类和中断风险提示，且仅在操作员确认后停止 OpenResty

#### Scenario: 当前没有活动连接时确认关闭
- **WHEN** 操作员点击“关闭对外服务”且预览快照显示活动连接为零
- **THEN** 系统显示零连接快照和关闭风险提示，且仍要求操作员确认

#### Scenario: 预览快照不可用时确认关闭
- **WHEN** 操作员点击“关闭对外服务”但连接快照无法获取
- **THEN** 系统显示“当前连接数暂时无法获取”和原因摘要，仍允许操作员明确确认并继续关闭

### Requirement: 记录实际关闭前连接快照
本地主备管理插件 SHALL 在实际开始停止 OpenResty 前重新采集连接快照，并将该执行前快照或采集失败原因包含在关闭操作结果和本地操作日志中。连接快照采集失败 MUST 不阻断既有关闭对外服务逻辑。

#### Scenario: 成功关闭并记录快照
- **WHEN** 操作员确认关闭且 OpenResty 在停止前可提供连接快照
- **THEN** 关闭结果和操作日志包含执行前活动连接与连接分类，随后报告 OpenResty 的关闭结果

#### Scenario: 连接快照失败仍执行关闭
- **WHEN** 操作员确认关闭但执行前无法获取连接快照
- **THEN** 操作日志记录连接快照不可用原因，系统仍执行既有 OpenResty 停止、禁用和 mask 流程并报告关闭结果
