# coding: utf-8
# -----------------------------
# 计划任务维护工具
# -----------------------------

import os
import re
import sys


PANEL_DIR = '/www/server/jh-panel'

if sys.platform != 'darwin':
    os.chdir(PANEL_DIR)

sys.path.append(os.path.join(PANEL_DIR, 'class/core'))

import mw
import crontab_api


def findCrontabByNameRegex(name_regex):
    try:
        pattern = re.compile(name_regex)
    except re.error as exc:
        raise ValueError('计划任务名称正则无效: {0}'.format(exc))

    tasks = mw.M('crontab').field('id,name,status').select() or []
    matches = []
    for task in tasks:
        name = str(task.get('name') or '')
        if pattern.search(name):
            matches.append(task)
    return sorted(matches, key=lambda item: int(item.get('id') or 0))


def listCrontabByNameRegex(name_regex):
    matches = findCrontabByNameRegex(name_regex)
    if not matches:
        print('未找到匹配的计划任务。')
        return 1

    print('匹配到 {0} 个计划任务：'.format(len(matches)))
    for task in matches:
        status = '启用' if str(task.get('status')) == '1' else '停用'
        print('|- ID: {0}，状态: {1}，名称: {2}'.format(task.get('id'), status, task.get('name')))
    return 0


def deleteCrontabByNameRegex(name_regex, confirmed=False):
    matches = findCrontabByNameRegex(name_regex)
    if not matches:
        print('未找到匹配的计划任务。')
        return 0

    print('匹配到 {0} 个计划任务：'.format(len(matches)))
    for task in matches:
        print('|- ID: {0}，名称: {1}'.format(task.get('id'), task.get('name')))

    if not confirmed:
        print('预览完成，未执行删除。确认删除请追加 --yes。')
        return 0

    api = crontab_api.crontab_api()
    failed = []
    for task in matches:
        try:
            success, message = api.delete(task['id'])
        except Exception as exc:
            success, message = False, str(exc)
        if success:
            print('|- 已删除: {0}'.format(task.get('name')))
        else:
            failed.append(task.get('name'))
            print('|- 删除失败: {0}，原因: {1}'.format(task.get('name'), message))

    if failed:
        print('计划任务删除完成，但有 {0} 个任务删除失败。'.format(len(failed)))
        return 1
    print('计划任务删除完成，共删除 {0} 个。'.format(len(matches)))
    return 0


def showUsage():
    print('用法:')
    print('  python3 /www/server/jh-panel/scripts/crontab.py list_crontab_by_name_regex <正则>')
    print('  python3 /www/server/jh-panel/scripts/crontab.py delete_crontab_by_name_regex <正则> [--yes]')
    print('说明: 正则使用包含匹配；精确匹配请使用 ^名称$。')


def main():
    if len(sys.argv) < 3:
        showUsage()
        return 2

    action = sys.argv[1]
    name_regex = sys.argv[2]
    try:
        if action == 'list_crontab_by_name_regex':
            return listCrontabByNameRegex(name_regex)
        if action == 'delete_crontab_by_name_regex':
            return deleteCrontabByNameRegex(name_regex, '--yes' in sys.argv[3:])
        showUsage()
        return 2
    except ValueError as exc:
        print('错误: {0}'.format(exc))
        return 2


if __name__ == '__main__':
    sys.exit(main())
