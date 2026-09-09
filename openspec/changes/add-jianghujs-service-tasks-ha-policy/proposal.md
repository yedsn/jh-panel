## Why

JianghuJS 管理器目前通过每个项目独立的计划任务清理日志，任务数量会随项目增长而增加，清理时间和保留规则也难以统一维护。同时，备用机需要周期性安装所有已登记项目的依赖，以便主备切换后能尽快恢复服务。

## What Changes

- 在 JianghuJS 管理器中新增“服务配置”面板，用于管理全局计划任务。
- 新增唯一的依赖预热任务 `JianghuJS管理器项目预备`；任务执行时遍历所有已登记项目，仅对存在 `package-lock.json` 的项目逐个运行 `npm ci`。
- 新增唯一的日志清理任务 `JianghuJS管理器日志清理`；项目仅保存是否参与清理，任务时间和日志保留规则统一配置。
- 移除 JianghuJS 管理器为每个项目分别创建日志清理计划任务的行为，并在升级时迁移旧任务状态。
- 扩展本地主备管理插件：备用机启用依赖预热任务，主机停用依赖预热任务，并将该状态纳入自检。

## Capabilities

### New Capabilities
- `jianghujs-service-task-management`: JianghuJS 管理器统一管理项目依赖预热与日志清理计划任务，并保存项目日志清理参与状态。
- `ha-jianghujs-preheat-policy`: 本地主备管理插件按角色调整并校验 JianghuJS 管理器依赖预热任务。

### Modified Capabilities
- 无。

## Impact

- 修改 `plugins/jianghujs/index.html`、`plugins/jianghujs/js/jianghujs.js` 和 `plugins/jianghujs/index.py`，增加服务配置界面、计划任务运行入口、项目日志清理标记和旧任务迁移。
- 修改 `plugins/ha_manager_local/index.py` 与 `plugins/ha_manager_local/flow_config.json`，增加依赖预热任务的主备切换步骤与自检项。
- 使用现有计划任务接口 `/crontab/add`、`/crontab/modify_crond`、`/crontab/get`、`/crontab/del` 和现有 `scripts/switch.py` 开关任务，不增加第三方依赖。
