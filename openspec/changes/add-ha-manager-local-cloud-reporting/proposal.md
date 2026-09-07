## Why

本地版主备管理插件目前只能保存云监控绑定信息，云监控端没有单机归属、鉴权和状态接收能力，运维人员无法集中查看当前机器的角色、自检结果、切换进度和日志。需要先建立面向单台机器的上报闭环，为后续双机聚合保留扩展空间而不提前引入对端依赖。

## What Changes

- 在云监控中新增单机主备管理归属创建能力，为每个唯一 `pair_id` 生成并保存上报密钥。
- 新增本地版插件的注册与状态上报接口，接收当前机器的身份、主备角色、自检摘要及切换状态。
- 新增切换任务摘要持久化和基于任务日志文件的增量日志接收、读取能力，并保证插件重试不会重复写入日志。
- 增加云监控单机归属列表和任务详情展示，使运维人员可查看当前机器状态与切换日志。
- 让 `ha_manager_local` 使用新接口完成注册和周期性状态、任务、日志上报；密钥由插件静默保存。
- 明确 v1 仅按当前机器最新上报计算状态，云监控不下发切换指令、不控制任务，也不读取或判断备用机。

## Capabilities

### New Capabilities
- `ha-manager-local-cloud-reporting`: 云监控创建并管理单机主备归属，接收本地版插件注册、状态、切换任务和增量日志，并提供状态及日志查询。

### Modified Capabilities
- None.

## Impact

- 云监控 SQLite 存储新增 `ha_pair`、`ha_host_state`、`ha_switch_task`，并为主机状态补充当前切换任务关联。
- 云监控新增 `/ha/api/local/pair/create`、`/ha/api/local/register`、`/ha/api/local/report` 和 `/ha/api/local/switch-log` API，以及任务日志目录 `/www/server/jh-monitor/logs/ha_switch/`。
- `plugins/ha_manager_local` 的云监控绑定、状态与切换任务上报逻辑将接入上述 API。
- 不修改 SSH 一键版主备管理的既有协议和流程；不增加第三方依赖。
