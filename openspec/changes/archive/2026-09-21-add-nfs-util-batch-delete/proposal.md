## Why

`nfs-util` 已支持列表多选和多种批量操作，但清理多条废弃挂载记录仍需逐项删除。增加批量删除可以减少重复操作，同时必须明确它只删除插件管理记录，不会自动卸载目录或清理 `/etc/fstab`。

## What Changes

- 在已有批量操作区增加“批量删除”按钮。
- 批量删除前使用数据安全确认，展示选择数量和条目名称，并明确提示不会卸载或取消自动挂载。
- 新增后端批量删除接口，对 ID 去重，删除仍存在的挂载记录，并返回已删除与不存在记录摘要。
- 删除完成后清空已删除选择并刷新挂载列表。

## Capabilities

### New Capabilities

无。

### Modified Capabilities
- `nfs-mount-batch-operations`: 将原先“不提供批量删除”的要求改为支持经过高风险确认、仅删除管理记录的批量删除流程。

## Impact

- 前端：`plugins/nfs-util/js/nfs-util.js` 的批量按钮、删除确认和结果处理。
- 插件入口：`plugins/nfs-util/index.html` 的脚本缓存版本。
- 后端：`plugins/nfs-util/index.py` 的批量删除接口和命令分发。
- 数据：删除 DictDataBase 中的所选挂载记录；不执行挂载、卸载或 `/etc/fstab` 修改。
