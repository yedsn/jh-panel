## Why

本地主备管理插件在总览页仅展示 OpenResty 是否运行，操作员在切换或关闭对外服务前无法判断当前可能受影响的访问规模。关闭动作会直接停止入口服务，应在执行前提供当前连接快照和明确风险提示，帮助操作员判断操作时机。

## What Changes

- 在本地主备管理插件总览中展示 OpenResty 当前活动连接数，以及 Reading、Writing、Waiting 连接分类和采集时间。
- 在“关闭对外服务”前采集最新连接快照，在确认弹窗中提示该操作可能中断当前连接；操作员确认后才停止 OpenResty。
- 在关闭操作结果和本地操作日志中保留关闭前的连接快照，便于事后判断影响范围。
- 在连接详情中说明 HTTP keep-alive 可能保留已完成请求的 TCP 连接，并展示从当前 OpenResty 配置读取的空闲超时时间。
- 增加可靠的本机 OpenResty `stub_status` 采集与解析：从实际配置识别本机状态页监听端口，校验响应格式，并在服务未运行、状态页不可用或响应异常时返回可展示的不可用状态。
- 不将连接数表述为真实用户人数；界面统一使用“当前活动连接”或“连接快照”。

## Capabilities

### New Capabilities
- `ha-manager-local-connection-impact`: 本地主备管理插件采集、展示和记录 OpenResty 当前连接快照，并在关闭对外服务前提示潜在连接中断影响。

### Modified Capabilities
- 无。

## Impact

- 修改 `/www/server/jh-panel/plugins/ha_manager_local/index.py`，在状态和关闭服务接口中提供 OpenResty 连接快照。
- 修改 `/www/server/jh-panel/plugins/ha_manager_local/js/ha_manager_local.js`，在总览页展示快照并增加关闭前确认弹窗。
- 可能修改 `/www/server/jh-panel/plugins/ha_manager_local/index.html` 的局部样式，以适配连接统计和不可用提示。
- 可选择修复 `/www/server/jh-panel/plugins/openresty/index.py` 既有 `run_info` 的端口发现与响应解析问题；不引入第三方依赖，不开放 `nginx_status` 到外网。
