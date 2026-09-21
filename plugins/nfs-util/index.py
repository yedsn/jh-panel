# coding:utf-8

import sys
import os
import re
import time
import json
import shlex
import stat
import tempfile
from urllib.parse import unquote
import dictdatabase as DDB

sys.path.append(os.getcwd() + "/class/core")
import mw


FSTAB_PATH = '/etc/fstab'


app_debug = False
if mw.isAppleSystem():
    app_debug = True


def getPluginName():

    return 'nfs-util'


def getPluginDir():
    return mw.getPluginDir() + '/' + getPluginName()


def getServerDir():
    return mw.getServerDir() + '/' + getPluginName()


def getInitDFile():
    if app_debug:
        return '/tmp/' + getPluginName()
    return '/etc/init.d/' + getPluginName()


def getArgs():
    args = sys.argv[2:]
    raw = ' '.join(args).strip()
    if not raw:
        return {}

    for candidate in (raw, unquote(raw)):
        try:
            data = json.loads(candidate)
            if isinstance(data, str):
                data = json.loads(data)
            if isinstance(data, dict):
                return data
        except Exception:
            continue

    tmp = {}
    for item in args:
        item = item.strip().strip('{').strip('}')
        if ':' not in item:
            continue
        key, value = item.split(':', 1)
        tmp[key.strip()] = value.strip()

    return tmp


def checkArgs(data, ck=[]):
    for i in range(len(ck)):
        if not ck[i] in data:
            return (False, mw.returnJson(False, '参数:(' + ck[i] + ')没有!'))
    return (True, mw.returnJson(True, 'ok'))


# https://github.com/mkrd/DictDataBase
def initDb():
    db_dir = getServerDir() + '/data/'
    if not os.path.exists(db_dir):
        mw.execShell('mkdir -p ' + db_dir)
    DDB.config.storage_directory = db_dir

def getDb(table):
    DDB.config.storage_directory = getServerDir() + '/data/'
    if not DDB.at(table).exists():
        DDB.at(table).create({})
    return DDB.at(table)

def saveOne(table, id, data):
    if type(id) is not str:
        id = str(id)
    exist = getOne(table, id)
    if exist:
        data = {'id': id, **exist, **data}
    else:
        data = {'id': id, **data}
    with getDb(table).session() as (session, db):
        db[id] = data
        session.write()

def getAll(table):
    result = getDb(table).read()
    if result:
        return list(result.values())
    return []

def getOne(table, id):
    if type(id) is not str:
        id = str(id)
    for item in getAll(table):
        if item['id'] == id:
            return item
    return None

def deleteOne(table, id):
    if type(id) is not str:
        id = str(id)
    with getDb(table).session() as (session, db):
        del db[id]
        session.write()


def _parseBatchIds(raw_ids):
    if isinstance(raw_ids, list):
        values = raw_ids
    else:
        values = str(raw_ids or '').split(',')

    ids = []
    seen = set()
    for value in values:
        item_id = str(value).strip()
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        ids.append(item_id)
    return ids


def _getBatchMounts(raw_ids):
    ids = _parseBatchIds(raw_ids)
    mounts = []
    missing = []
    for item_id in ids:
        mount = getOne('mount', item_id)
        if mount:
            mounts.append(mount)
        else:
            missing.append(item_id)
    return ids, mounts, missing


def _mountSource(mount):
    return str(mount.get('serverIP', '')) + ':' + str(mount.get('mountServerPath', ''))


def _validateMount(mount):
    if not str(mount.get('serverIP', '')).strip():
        return 'NFS服务器不能为空'
    if not str(mount.get('mountServerPath', '')).strip():
        return '共享目录不能为空'
    mount_path = str(mount.get('mountPath', '')).strip()
    if not mount_path:
        return '挂载路径不能为空'
    if not os.path.isabs(mount_path):
        return '挂载路径必须是绝对路径'
    return ''


def _readFstabLines(path=None):
    path = path or FSTAB_PATH
    with open(path, 'r', encoding='utf-8', errors='surrogateescape') as fp:
        return fp.readlines()


def _fstabEscape(value):
    return str(value).replace('\\', '\\134').replace(' ', '\\040').replace('\t', '\\011')


def _fstabLine(mount):
    source = _fstabEscape(_mountSource(mount))
    target = _fstabEscape(mount.get('mountPath', ''))
    return source + ' ' + target + ' nfs defaults 0 0'


def _fstabLineMatchesMount(line, mount):
    stripped = line.strip()
    if not stripped or stripped.startswith('#'):
        return False
    fields = stripped.split()
    if len(fields) < 3:
        return False
    return (
        fields[0] == _fstabEscape(_mountSource(mount))
        and fields[1] == _fstabEscape(mount.get('mountPath', ''))
        and fields[2] in ('nfs', 'nfs4')
    )


def _fstabHasMount(lines, mount):
    return any(_fstabLineMatchesMount(line, mount) for line in lines)


def _atomicWriteLines(path, lines):
    directory = os.path.dirname(path) or '.'
    original_stat = os.stat(path)
    fd, temp_path = tempfile.mkstemp(prefix='.' + os.path.basename(path) + '.', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', errors='surrogateescape') as fp:
            fp.writelines(lines)
            fp.flush()
            os.fsync(fp.fileno())
            os.fchmod(fp.fileno(), stat.S_IMODE(original_stat.st_mode))
        try:
            os.chown(temp_path, original_stat.st_uid, original_stat.st_gid)
        except PermissionError:
            pass
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _resultItem(mount, reason=''):
    item = {
        'id': str(mount.get('id', '')),
        'name': str(mount.get('name', '')),
    }
    if reason:
        item['reason'] = reason
    return item


def _setAutostartState(mounts, action, path=None):
    path = path or FSTAB_PATH
    if action not in ('enable', 'disable'):
        return False, '不支持的自动挂载操作', {
            'changed': [], 'skipped': [], 'failed': []
        }

    try:
        lines = _readFstabLines(path)
    except Exception as ex:
        return False, '读取自动挂载配置失败: ' + str(ex), {
            'changed': [], 'skipped': [], 'failed': []
        }

    changed = []
    skipped = []
    failed = []

    for mount in mounts:
        error = _validateMount(mount)
        if error:
            failed.append(_resultItem(mount, error))
            continue

        expected_line = _fstabLine(mount)
        matching_indexes = [index for index, line in enumerate(lines) if _fstabLineMatchesMount(line, mount)]

        if action == 'enable':
            if len(matching_indexes) == 1:
                skipped.append(_resultItem(mount, '已经开启自动挂载'))
                continue
            if len(matching_indexes) > 1:
                kept = False
                normalized = []
                for line in lines:
                    if not _fstabLineMatchesMount(line, mount):
                        normalized.append(line)
                    elif not kept:
                        normalized.append(line if line.endswith(('\n', '\r')) else line + '\n')
                        kept = True
                lines = normalized
                changed.append(_resultItem(mount))
                continue
            if lines and not lines[-1].endswith(('\n', '\r')):
                lines[-1] += '\n'
            lines.append(expected_line + '\n')
            changed.append(_resultItem(mount))
            continue

        if not matching_indexes:
            skipped.append(_resultItem(mount, '已经关闭自动挂载'))
            continue
        lines = [
            line for line in lines
            if not _fstabLineMatchesMount(line, mount)
        ]
        changed.append(_resultItem(mount))

    if changed:
        try:
            _atomicWriteLines(path, lines)
        except Exception as ex:
            reason = '写入自动挂载配置失败: ' + str(ex)
            changed_ids = {item['id'] for item in changed}
            failed.extend([
                _resultItem(item, reason)
                for item in mounts
                if str(item.get('id', '')) in changed_ids
            ])
            changed = []
            return False, reason, {
                'changed': changed,
                'skipped': skipped,
                'failed': failed,
            }

    return True, '自动挂载配置处理完成', {
        'changed': changed,
        'skipped': skipped,
        'failed': failed,
    }


def _mountedFilesystems():
    result = mw.execShell('findmnt -J -o TARGET,SOURCE,FSTYPE')
    if len(result) > 2 and result[2] != 0:
        return {}
    try:
        data = json.loads(result[0] or '{}')
    except Exception:
        return {}

    mounted = {}

    def collect(items):
        for item in items or []:
            target = item.get('target')
            if target:
                mounted[os.path.normpath(target)] = {
                    'source': str(item.get('source', '')),
                    'fstype': str(item.get('fstype', '')),
                }
            collect(item.get('children', []))

    collect(data.get('filesystems', []))
    return mounted


def _mountRuntimeState(mount, mounted=None):
    mounted = mounted if mounted is not None else _mountedFilesystems()
    mount_path = os.path.normpath(str(mount.get('mountPath', '')))
    current = mounted.get(mount_path)
    if not current:
        return 'unmounted'
    if current.get('source') == _mountSource(mount) and current.get('fstype') in ('nfs', 'nfs4'):
        return 'mounted'
    return 'conflict'


def _buildMountOperationScript(mount, action):
    if action not in ('mount', 'unmount'):
        raise ValueError('不支持的挂载操作')

    error = _validateMount(mount)
    if error:
        return 'printf "%s\\n" {0}\n'.format(shlex.quote('[失败] ' + str(mount.get('name', '')) + ': ' + error))

    name = str(mount.get('name', '') or mount.get('id', ''))
    source = _mountSource(mount)
    target = str(mount.get('mountPath', ''))
    lines = [
        'mount_name=' + shlex.quote(name),
        'mount_source=' + shlex.quote(source),
        'mount_target=' + shlex.quote(target),
        'printf "\\n[%s] %s\\n" "$mount_name" ' + shlex.quote('开始' + ('挂载' if action == 'mount' else '卸载')),
        'current_source="$(findmnt -M "$mount_target" -n -o SOURCE --raw 2>/dev/null || true)"',
        'current_fstype="$(findmnt -M "$mount_target" -n -o FSTYPE --raw 2>/dev/null || true)"',
    ]

    if action == 'mount':
        lines.extend([
            'if [ -n "$current_source" ]; then',
            '  if [ "$current_source" = "$mount_source" ] && { [ "$current_fstype" = "nfs" ] || [ "$current_fstype" = "nfs4" ]; }; then',
            '    printf "[跳过] %s 已按当前配置挂载\\n" "$mount_name"',
            '  else',
            '    printf "[失败] %s 的目标路径已被 %s (%s) 挂载\\n" "$mount_name" "$current_source" "$current_fstype" >&2',
            '  fi',
            'else',
            '  if mkdir -p -- "$mount_target" && mount -t nfs "$mount_source" "$mount_target"; then',
            '    if chmod 777 -- "$mount_target"; then',
            '      printf "[成功] %s 挂载完成\\n" "$mount_name"',
            '    else',
            '      printf "[警告] %s 已挂载，但设置目录权限失败\\n" "$mount_name" >&2',
            '    fi',
            '  else',
            '    printf "[失败] %s 挂载失败\\n" "$mount_name" >&2',
            '  fi',
            'fi',
        ])
    else:
        lines.extend([
            'if [ -z "$current_source" ]; then',
            '  printf "[跳过] %s 当前未挂载\\n" "$mount_name"',
            'elif [ "$current_source" != "$mount_source" ] || { [ "$current_fstype" != "nfs" ] && [ "$current_fstype" != "nfs4" ]; }; then',
            '  printf "[失败] %s 的目标路径由 %s (%s) 占用，未执行卸载\\n" "$mount_name" "$current_source" "$current_fstype" >&2',
            'elif umount "$mount_target"; then',
            '  printf "[成功] %s 卸载完成\\n" "$mount_name"',
            'else',
            '  printf "[失败] %s 卸载失败，目录可能正在使用\\n" "$mount_name" >&2',
            'fi',
        ])

    return '\n'.join(lines) + '\n'


def _buildBatchScript(ids, mounts, missing, action):
    action_text = '挂载' if action == 'mount' else '卸载'
    mount_map = {str(item.get('id', '')): item for item in mounts}
    missing_set = set(missing)
    parts = [
        '#!/bin/bash',
        'printf "%s\\n" ' + shlex.quote('开始批量' + action_text + '，共 ' + str(len(mounts) + len(missing)) + ' 项'),
    ]
    for item_id in ids:
        if item_id in missing_set:
            parts.append('printf "%s\\n" ' + shlex.quote('[失败] 挂载记录不存在: ' + item_id))
            continue
        parts.append(_buildMountOperationScript(mount_map[item_id], action).rstrip())
    parts.append('printf "\\n%s\\n" ' + shlex.quote('批量' + action_text + '处理完成'))
    return '\n'.join(parts) + '\n'


def status():
    return 'start'

def start():
    initDb()
    mw.restartWeb()
    return 'ok'

def stop():
    return '暂不支持'

def restart():
    return 'ok'

def reload():
    return 'ok'
    
def mountList():
    data = getAll('mount')

    # 根据id倒序排序
    data.sort(key=lambda x: x['id'], reverse=True)

    try:
        fstab_lines = _readFstabLines()
    except Exception:
        fstab_lines = []
    mounted = _mountedFilesystems()
    
    for item in data:
        item['autostartStatus'] = 'start' if _fstabHasMount(fstab_lines, item) else 'stop'
        item['status'] = 'start' if _mountRuntimeState(item, mounted) == 'mounted' else 'stop'

        # 格式化createTime
        createTime = item.get('createTime', 0)
        item['createTime'] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(createTime))

    return mw.returnJson(True, 'ok', data)

def getNfsSharePath():
    args = getArgs()
    data = checkArgs(args, ['serverIP'])
    if not data[0]:
        return data[1]
    serverIP = args['serverIP']
    cmd = "showmount -e " + serverIP
    # 从showmount -e中获取共享目录
    data = mw.execShell(cmd)
    if data[0] == '':
        return mw.returnJson(False, '获取共享目录失败!')
    pattern = r"(/[\w/]+)\s+([\d.,]+)"
    matches = re.findall(pattern, data[0])
    result = [{"path": m[0], "whiteIPs": m[1]} for m in matches]
    return mw.returnJson(True, 'ok', result)


def mountAdd():
    args = getArgs()
    data = checkArgs(args, ['serverIP', 'mountServerPath', 'name', 'mountPath', 'remark'])
    if not data[0]:
        return data[1]
    serverIP = unquote(args['serverIP'], 'utf-8')
    mountServerPath = unquote(args['mountServerPath'], 'utf-8')
    name = unquote(args['name'], 'utf-8')
    mountPath = unquote(args['mountPath'], 'utf-8')
    remark = unquote(args['remark'], 'utf-8')

    id = int(time.time())
    saveOne('mount', id, {
        'serverIP': serverIP,
        'mountServerPath': mountServerPath,
        'name': name,
        'mountPath': mountPath,
        'remark': remark,
        'createTime': int(time.time())
    })
    return mw.returnJson(True, '添加成功!')

def mountEdit():
    args = getArgs()
    data = checkArgs(args, ['id', 'serverIP', 'mountServerPath', 'name', 'mountPath', 'remark'])
    if not data[0]:
        return data[1]
    id = args['id']
    serverIP = unquote(args['serverIP'], 'utf-8')
    mountServerPath = unquote(args['mountServerPath'], 'utf-8')
    name = unquote(args['name'], 'utf-8')
    mountPath = unquote(args['mountPath'], 'utf-8')
    remark = unquote(args['remark'], 'utf-8')
    mount = getOne('mount', id)
    if not mount:
        return mw.returnJson(False, '挂载不存在!')
    saveOne('mount', id, {
        'serverIP': serverIP,
        'mountServerPath': mountServerPath,
        'name': name,
        'mountPath': mountPath,
        'remark': remark,
    })
    
    return mw.returnJson(True, '修改成功!')

def mountDelete():
    args = getArgs()
    data = checkArgs(args, ['id'])
    if not data[0]:
        return data[1]

    id = args['id']    
    deleteOne('mount', id)
    return mw.returnJson(True, '删除成功!')

def getMountScript():
    args = getArgs()
    data = checkArgs(args, ['id'])
    if not data[0]:
        return data[1]
    id = args['id']
    mount = getOne('mount', id)
    if not mount:
        return mw.returnJson(False, '挂载不存在!')
    return _buildMountOperationScript(mount, 'mount')

def getUnMountScript():
    args = getArgs()
    data = checkArgs(args, ['id'])
    if not data[0]:
        return data[1]
    id = args['id']
    mount = getOne('mount', id)
    if not mount:
        return mw.returnJson(False, '挂载不存在!')
    return _buildMountOperationScript(mount, 'unmount')


def getMountBatchScript():
    args = getArgs()
    data = checkArgs(args, ['ids', 'action'])
    if not data[0]:
        return data[1]
    action = str(args.get('action', '')).strip()
    if action not in ('mount', 'unmount'):
        return mw.returnJson(False, '不支持的挂载操作!')
    ids, mounts, missing = _getBatchMounts(args.get('ids'))
    if not ids:
        return mw.returnJson(False, '请至少选择一个挂载项!')
    return mw.returnJson(True, 'ok', _buildBatchScript(ids, mounts, missing, action))


def mountToggleAutostart():
    args = getArgs()
    data = checkArgs(args, ['id'])
    if not data[0]:
        return data[1]
    id = args['id']
    mount = getOne('mount', id)
    if not mount:
        return mw.returnJson(False, '挂载不存在!')

    try:
        fstab_lines = _readFstabLines()
    except Exception as ex:
        return mw.returnJson(False, '读取自动挂载配置失败: ' + str(ex))
    action = 'disable' if _fstabHasMount(fstab_lines, mount) else 'enable'
    success, message, result = _setAutostartState([mount], action)
    if not success:
        return mw.returnJson(False, message, result)
    if result['failed']:
        return mw.returnJson(False, result['failed'][0].get('reason', message), result)
    return mw.returnJson(True, '已关闭自启动!' if action == 'disable' else '已开启自启动!', result)


def mountBatchAutostart():
    args = getArgs()
    data = checkArgs(args, ['ids', 'action'])
    if not data[0]:
        return data[1]
    action = str(args.get('action', '')).strip()
    if action not in ('enable', 'disable'):
        return mw.returnJson(False, '不支持的自动挂载操作!')
    ids, mounts, missing = _getBatchMounts(args.get('ids'))
    if not ids:
        return mw.returnJson(False, '请至少选择一个挂载项!')

    success, message, result = _setAutostartState(mounts, action)
    result['missing'] = [{'id': item_id, 'reason': '挂载记录不存在'} for item_id in missing]
    if not success:
        return mw.returnJson(False, message, result)

    changed_count = len(result['changed'])
    skipped_count = len(result['skipped'])
    failed_count = len(result['failed']) + len(result['missing'])
    summary = '处理完成：变更%d项，跳过%d项，失败%d项' % (changed_count, skipped_count, failed_count)
    return mw.returnJson(True, summary, result)

if __name__ == "__main__":
    func = sys.argv[1]
    if func == 'status':
        print(status())
    elif func == 'start':
        print(start())
    elif func == 'stop':
        print(stop())
    elif func == 'reload':
        print(reload())
    elif func == 'restart':
        print(restart())
    elif func == 'mount_list':
        print(mountList())
    elif func == 'get_nfs_share_path':
        print(getNfsSharePath())
    elif func == 'mount_add':
        print(mountAdd())
    elif func == 'mount_edit':
        print(mountEdit())
    elif func == 'mount_delete':
        print(mountDelete())
    elif func == 'get_mount_script':
        print(getMountScript())
    elif func == 'get_unmount_script':
        print(getUnMountScript())
    elif func == 'get_mount_batch_script':
        print(getMountBatchScript())
    elif func == 'mount_toggle_autostart':
        print(mountToggleAutostart())
    elif func == 'mount_batch_autostart':
        print(mountBatchAutostart())
    else:
        print('error')
