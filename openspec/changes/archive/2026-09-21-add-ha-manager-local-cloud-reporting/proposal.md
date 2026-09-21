## Why

本地版主备管理插件目前只能保存云监控绑定信息，云监控端没有主备关系和状态接收能力，运维人员无法集中查看当前机器的角色、自检结果、切换进度和日志。需要先建立面向单台机器的上报闭环，为后续双机聚合保留扩展空间而不提前引入对端依赖。

## What Changes

- 在云监控中新增主备关系创建和删除能力，运维人员填写关系名称，系统生成唯一 `pair_id`，列表直接展示该 ID。
- 新增本地版插件的注册与状态上报接口，接收当前机器的身份、主备角色、自检摘要及切换状态。
- 新增切换任务摘要持久化和基于任务日志文件的增量日志接收、读取能力，并保证插件重试不会重复写入日志。
- 增加云监控主备关系列表和任务详情展示，使运维人员可查看当前机器状态与切换日志。
- 让 `ha_manager_local` 仅使用云监控地址和主备关系 ID 完成注册和周期性状态、任务、日志上报。
- 明确 v1 仅按当前机器最新上报计算状态，云监控不下发切换指令、不控制任务，也不读取或判断备用机。

## Capabilities

### New Capabilities
- `ha-manager-local-cloud-reporting`: 云监控创建并管理主备关系，接收本地版插件注册、状态、切换任务和增量日志，并提供状态及日志查询。

### Modified Capabilities
- None.

## Impact

- 云监控 SQLite 存储新增 `ha_pair`、`ha_host_state`、`ha_switch_task`，并为主机状态补充当前切换任务关联。
- 云监控新增 `/ha/api/local/pair/create`、`/ha/api/local/pair/delete`、`/ha/api/local/register`、`/ha/api/local/report` 和 `/ha/api/local/switch-log` API，以及任务日志目录 `/www/server/jh-monitor/logs/ha_switch/`。
- `plugins/ha_manager_local` 的云监控绑定、状态与切换任务上报逻辑将接入上述 API。
- 不兼容 SSH 一键版云监控协议；不影响本地版本机切换流程；不增加第三方依赖。
