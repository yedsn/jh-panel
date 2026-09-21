# coding: utf-8

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import quote


ROOT = '/www/server/jh-panel'
NFS_UTIL_PATH = os.path.join(ROOT, 'plugins/nfs-util/index.py')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def return_json(status, msg, data=None):
    return {'status': bool(status), 'msg': msg, 'data': data}


def write_executable(path, content):
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(content)
    os.chmod(path, 0o755)


def test_nfs_util_batch_operations():
    work_dir = tempfile.mkdtemp(prefix='nfs-util-batch-test-')
    original_argv = sys.argv[:]
    try:
        module = load_module('nfs_util_batch_test', NFS_UTIL_PATH)
        module.mw.returnJson = return_json

        records = {}
        module.getOne = lambda table, record_id: records.get(str(record_id)) if table == 'mount' else None

        def save_one(table, record_id, data):
            assert table == 'mount'
            item_id = str(record_id)
            records[item_id] = {'id': item_id, **records.get(item_id, {}), **data}

        deleted_ids = []
        module.saveOne = save_one
        module.deleteOne = lambda table, record_id: deleted_ids.append((table, str(record_id)))

        sys.argv = [NFS_UTIL_PATH, 'test', json.dumps({'ids': '1,2', 'action': 'mount'})]
        assert module.getArgs() == {'ids': '1,2', 'action': 'mount'}
        encoded_args = quote(json.dumps({'ids': '1,2', 'action': 'mount'}))
        sys.argv = [NFS_UTIL_PATH, 'test', encoded_args]
        assert module.getArgs() == {'ids': '1,2', 'action': 'mount'}
        sys.argv = [NFS_UTIL_PATH, 'test', '{"mountPath":"%2Fmnt%2Fencoded"}']
        assert module.getArgs()['mountPath'] == '%2Fmnt%2Fencoded'
        sys.argv = [NFS_UTIL_PATH, 'test', 'id:1', 'action:mount:test']
        assert module.getArgs() == {'id': '1', 'action': 'mount:test'}
        assert module._parseBatchIds('1,2,1,,3') == ['1', '2', '3']

        fstab_path = os.path.join(work_dir, 'fstab')
        mount_a = {
            'id': '1',
            'name': '共享 A',
            'serverIP': '10.0.0.1',
            'mountServerPath': '/srv/share a',
            'mountPath': '/mnt/share a',
        }
        mount_b = {
            'id': '2',
            'name': '共享 B',
            'serverIP': '10.0.0.2',
            'mountServerPath': '/srv/share-b',
            'mountPath': '/mnt/share-b',
        }
        records.update({'1': mount_a, '2': mount_b})
        line_a = module._fstabLine(mount_a)
        with open(fstab_path, 'w', encoding='utf-8') as fp:
            fp.write('# keep this comment\n')
            fp.write(line_a.replace(' defaults ', ' rw,_netdev ') + '\n')
            fp.write(line_a + '\n')
            fp.write('/dev/sda1 / ext4 defaults 0 1\n')
        os.chmod(fstab_path, 0o640)

        success, message, result = module._setAutostartState([mount_a, mount_b], 'enable', fstab_path)
        assert success is True, message
        assert [item['id'] for item in result['changed']] == ['1', '2']
        with open(fstab_path, 'r', encoding='utf-8') as fp:
            enabled_content = fp.read()
        assert enabled_content.count('10.0.0.1:/srv/share\\040a /mnt/share\\040a nfs') == 1
        assert enabled_content.count(module._fstabLine(mount_b)) == 1
        assert '# keep this comment' in enabled_content
        assert '/dev/sda1 / ext4 defaults 0 1' in enabled_content
        assert stat.S_IMODE(os.stat(fstab_path).st_mode) == 0o640

        success, message, result = module._setAutostartState([mount_a, mount_b], 'enable', fstab_path)
        assert success is True, message
        assert result['changed'] == []
        assert len(result['skipped']) == 2

        success, message, result = module._setAutostartState([mount_a], 'disable', fstab_path)
        assert success is True, message
        assert [item['id'] for item in result['changed']] == ['1']
        with open(fstab_path, 'r', encoding='utf-8') as fp:
            disabled_content = fp.read()
        assert '10.0.0.1:/srv/share\\040a' not in disabled_content
        assert module._fstabLine(mount_b) in disabled_content
        assert '# keep this comment' in disabled_content

        module.FSTAB_PATH = fstab_path
        module.getArgs = lambda: {'ids': '1,2,1,missing', 'action': 'enable'}
        batch_autostart = module.mountBatchAutostart()
        assert batch_autostart['status'] is True
        assert len(batch_autostart['data']['changed']) == 1
        assert len(batch_autostart['data']['skipped']) == 1
        assert batch_autostart['data']['missing'] == [{'id': 'missing', 'reason': '挂载记录不存在'}]

        module.getArgs = lambda: {'id': '1'}
        toggle_result = module.mountToggleAutostart()
        assert toggle_result['status'] is True
        assert toggle_result['msg'] == '已关闭自启动!'

        module.getArgs = lambda: {'ids': '1,missing,2', 'action': 'mount'}
        batch_script_result = module.getMountBatchScript()
        assert batch_script_result['status'] is True
        assert batch_script_result['data'].index('挂载记录不存在: missing') < batch_script_result['data'].index('共享 B')

        module.getArgs = lambda: {'ids': '1', 'action': 'invalid'}
        assert module.getMountBatchScript()['status'] is False
        assert module.mountBatchAutostart()['status'] is False

        module.getArgs = lambda: {'id': '1'}
        assert module.getMountScript() == module._buildMountOperationScript(mount_a, 'mount')
        assert module.getUnMountScript() == module._buildMountOperationScript(mount_a, 'unmount')

        module.getArgs = lambda: {
            'serverIP': '10.0.0.8',
            'mountServerPath': '%2Fsrv%2Fnew',
            'name': '%E6%96%B0%E6%8C%82%E8%BD%BD',
            'mountPath': '%2Fmnt%2Fnew',
            'remark': 'created',
        }
        add_result = module.mountAdd()
        assert add_result['status'] is True
        added = next(item for item in records.values() if item.get('serverIP') == '10.0.0.8')
        assert added['mountServerPath'] == '/srv/new'
        assert added['name'] == '新挂载'

        module.getArgs = lambda: {
            'id': added['id'],
            'serverIP': '10.0.0.9',
            'mountServerPath': '%2Fsrv%2Fedited',
            'name': '%E7%BC%96%E8%BE%91%E6%8C%82%E8%BD%BD',
            'mountPath': '%2Fmnt%2Fedited',
            'remark': 'edited',
        }
        edit_result = module.mountEdit()
        assert edit_result['status'] is True
        assert records[added['id']]['mountPath'] == '/mnt/edited'
        assert records[added['id']]['name'] == '编辑挂载'

        module.getArgs = lambda: {'id': added['id']}
        delete_result = module.mountDelete()
        assert delete_result['status'] is True
        assert deleted_ids[-1] == ('mount', added['id'])

        mounted = {
            '/mnt/a': {'source': '10.0.0.1:/srv/a', 'fstype': 'nfs4'},
            '/mnt/conflict': {'source': '/dev/sdb1', 'fstype': 'ext4'},
        }
        assert module._mountRuntimeState({
            'serverIP': '10.0.0.1', 'mountServerPath': '/srv/a', 'mountPath': '/mnt/a'
        }, mounted) == 'mounted'
        assert module._mountRuntimeState({
            'serverIP': '10.0.0.1', 'mountServerPath': '/srv/a', 'mountPath': '/mnt/conflict'
        }, mounted) == 'conflict'
        assert module._mountRuntimeState({
            'serverIP': '10.0.0.1', 'mountServerPath': '/srv/a', 'mountPath': '/mnt/missing'
        }, mounted) == 'unmounted'

        bin_dir = os.path.join(work_dir, 'bin')
        os.makedirs(bin_dir)
        command_log = os.path.join(work_dir, 'commands.log')
        write_executable(os.path.join(bin_dir, 'findmnt'), '''#!/bin/sh
target=""
column=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -M) target="$2"; shift 2 ;;
    -o) column="$2"; shift 2 ;;
    *) shift ;;
  esac
done
case "$target:$column" in
  */already:SOURCE) printf '%s\n' '10.0.0.1:/srv/already' ;;
  */already:FSTYPE) printf '%s\n' 'nfs4' ;;
  */conflict:SOURCE) printf '%s\n' '/dev/sdb1' ;;
  */conflict:FSTYPE) printf '%s\n' 'ext4' ;;
esac
''')
        write_executable(os.path.join(bin_dir, 'mount'), '''#!/bin/sh
printf 'mount:%s:%s\n' "$3" "$4" >> "$COMMAND_LOG"
case "$4" in
  *fail*) exit 1 ;;
esac
exit 0
''')
        write_executable(os.path.join(bin_dir, 'umount'), '''#!/bin/sh
printf 'umount:%s\n' "$1" >> "$COMMAND_LOG"
case "$1" in
  *busy*) exit 1 ;;
esac
exit 0
''')

        injection_marker = os.path.join(work_dir, 'injected')
        mounts = [
            {'id': 'already', 'name': '已经挂载', 'serverIP': '10.0.0.1', 'mountServerPath': '/srv/already', 'mountPath': os.path.join(work_dir, 'already')},
            {'id': 'conflict', 'name': '冲突挂载', 'serverIP': '10.0.0.2', 'mountServerPath': '/srv/conflict', 'mountPath': os.path.join(work_dir, 'conflict')},
            {'id': 'fail', 'name': '失败后继续', 'serverIP': '10.0.0.3', 'mountServerPath': '/srv/fail', 'mountPath': os.path.join(work_dir, 'fail')},
            {'id': 'quoted', 'name': '带特殊字符', 'serverIP': '10.0.0.4', 'mountServerPath': '/srv/a;touch ' + injection_marker, 'mountPath': os.path.join(work_dir, 'quoted path')},
        ]
        script = module._buildBatchScript(
            ['already', 'missing', 'conflict', 'fail', 'quoted'],
            mounts,
            ['missing'],
            'mount',
        )
        syntax_check = subprocess.run(['bash', '-n'], input=script, text=True, capture_output=True)
        assert syntax_check.returncode == 0, syntax_check.stderr
        result = subprocess.run(
            ['bash'],
            input=script,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={**os.environ, 'PATH': bin_dir + ':' + os.environ.get('PATH', ''), 'COMMAND_LOG': command_log},
        )
        assert result.returncode == 0
        assert '[跳过] 已经挂载' in result.stdout
        assert '[失败] 挂载记录不存在: missing' in result.stdout
        assert '[失败] 冲突挂载' in result.stdout
        assert '[失败] 失败后继续' in result.stdout
        assert '[成功] 带特殊字符' in result.stdout
        assert not os.path.exists(injection_marker)
        with open(command_log, 'r', encoding='utf-8') as fp:
            command_content = fp.read()
        assert '/srv/a;touch ' + injection_marker in command_content
        assert 'quoted path' in command_content

        unmount_mounts = [
            {'id': 'already', 'name': '正常卸载', 'serverIP': '10.0.0.1', 'mountServerPath': '/srv/already', 'mountPath': os.path.join(work_dir, 'already')},
            {'id': 'busy', 'name': '占用目录', 'serverIP': '10.0.0.5', 'mountServerPath': '/srv/busy', 'mountPath': os.path.join(work_dir, 'busy')},
            {'id': 'not-mounted', 'name': '未挂载目录', 'serverIP': '10.0.0.7', 'mountServerPath': '/srv/not-mounted', 'mountPath': os.path.join(work_dir, 'not-mounted')},
            {'id': 'after', 'name': '失败后继续卸载', 'serverIP': '10.0.0.6', 'mountServerPath': '/srv/after', 'mountPath': os.path.join(work_dir, 'after')},
        ]
        findmnt_path = os.path.join(bin_dir, 'findmnt')
        with open(findmnt_path, 'a', encoding='utf-8') as fp:
            fp.write('''
case "$target:$column" in
  */busy:SOURCE) printf '%s\n' '10.0.0.5:/srv/busy' ;;
  */busy:FSTYPE) printf '%s\n' 'nfs' ;;
  */after:SOURCE) printf '%s\n' '10.0.0.6:/srv/after' ;;
  */after:FSTYPE) printf '%s\n' 'nfs' ;;
esac
''')
        unmount_script = module._buildBatchScript(
            ['already', 'busy', 'not-mounted', 'after'],
            unmount_mounts,
            [],
            'unmount',
        )
        assert 'umount -f' not in unmount_script
        assert 'umount -l' not in unmount_script
        unmount_result = subprocess.run(
            ['bash'],
            input=unmount_script,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={**os.environ, 'PATH': bin_dir + ':' + os.environ.get('PATH', ''), 'COMMAND_LOG': command_log},
        )
        assert unmount_result.returncode == 0
        assert '[成功] 正常卸载' in unmount_result.stdout
        assert '[失败] 占用目录' in unmount_result.stdout
        assert '[跳过] 未挂载目录' in unmount_result.stdout
        assert '[成功] 失败后继续卸载' in unmount_result.stdout
    finally:
        sys.argv = original_argv
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == '__main__':
    test_nfs_util_batch_operations()
    print('ok')
