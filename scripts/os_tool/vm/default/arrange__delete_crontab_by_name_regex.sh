#!/bin/bash
set -euo pipefail

PANEL_DIR="/www/server/jh-panel"
CRONTAB_SCRIPT="${PANEL_DIR}/scripts/crontab.py"
COLOR_RESET='\033[0m'
COLOR_TITLE='\033[1;36m'
COLOR_HINT='\033[0;90m'
COLOR_VALUE='\033[1;33m'

echo "================= 按名称正则删除计划任务 ================="
echo "1. 输入名称正则后，先列出全部匹配的计划任务"
echo "2. 输入 y 确认后，才会执行删除"
echo "3. 删除会同步清理面板任务、任务脚本和系统 crontab"
echo "-----------------------"
echo -e "${COLOR_TITLE}正则示例${COLOR_RESET}"
echo -e "${COLOR_HINT}|- 删除 JianghuJS 历史日志任务${COLOR_RESET}"
echo -e "${COLOR_HINT}|  输入值：${COLOR_RESET}${COLOR_VALUE}^(JianghuJS管理器日志清理|\\[勿删\\]项目\\[.+\\]日志清理)\$${COLOR_RESET}"
echo -e "${COLOR_HINT}|- 删除名称以“测试”开头的任务${COLOR_RESET}"
echo -e "${COLOR_HINT}|  输入值：${COLOR_RESET}${COLOR_VALUE}^测试.*${COLOR_RESET}"
echo "========================================================"

echo -ne "${COLOR_VALUE}请输入计划任务名称正则: ${COLOR_RESET}"
read -r name_regex
if [[ -z "${name_regex}" ]]; then
    echo "错误：计划任务名称正则不能为空。"
    exit 2
fi

set +e
python3 "${CRONTAB_SCRIPT}" list_crontab_by_name_regex "${name_regex}"
list_result=$?
set -e

if [[ ${list_result} -eq 1 ]]; then
    echo "没有匹配的计划任务，未执行删除。"
    exit 0
fi
if [[ ${list_result} -ne 0 ]]; then
    echo "读取计划任务失败，请检查输入的正则。"
    exit "${list_result}"
fi

echo "-----------------------"
read -r -p "以上匹配任务将被永久删除，确认执行吗？[y/N] " confirm
if [[ ! "${confirm}" =~ ^[Yy]$ ]]; then
    echo "已取消操作。"
    exit 0
fi

python3 "${CRONTAB_SCRIPT}" delete_crontab_by_name_regex "${name_regex}" --yes
