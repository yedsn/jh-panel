# coding: utf-8

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types


ROOT = '/www/server/jh-panel'
JIANGHUJS_PATH = os.path.join(ROOT, 'plugins/jianghujs/index.py')
HA_MANAGER_PATH = os.path.join(ROOT, 'plugins/ha_manager_local/index.py')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def return_json(status, msg, data=None):
    return {'status': bool(status), 'msg': msg, 'data': data if data is not None else {}}


def test_jianghujs_tasks():
    work_dir = tempfile.mkdtemp(prefix='jianghujs-service-task-test-')
    try:
        module = load_module('jianghujs_service_task_test', JIANGHUJS_PATH)
        module.mw.returnJson = return_json

        records = {
            'legacy-single': {'id': 'legacy-single', 'name': '旧任务项目', 'path': os.path.join(work_dir, 'legacy-single')},
            'duplicate-a': {'id': 'duplicate-a', 'name': '同名项目', 'path': os.path.join(work_dir, 'duplicate-a')},
            'duplicate-b': {'id': 'duplicate-b', 'name': '同名项目', 'path': os.path.join(work_dir, 'duplicate-b')},
        }

        def get_all(table):
            return list(records.values()) if table == 'project' else []

        def get_one(table, record_id):
            return records.get(str(record_id)) if table == 'project' else None

        def save_one(table, record_id, data):
            records[str(record_id)].update(data)

        module.getAll = get_all
        module.getOne = get_one
        module.saveOne = save_one

        class EmptyCronQuery:
            def where(self, *args):
                return self

            def field(self, *args):
                return self

            def find(self):
                return []

        class EmptyCronDb:
            def M(self, table):
                assert table == 'crontab'
                return EmptyCronQuery()

        original_mw = module.mw
        try:
            module.mw = EmptyCronDb()
            assert module.getCronTask(module.PROJECT_PREHEAT_TASK_NAME) is None
        finally:
            module.mw = original_mw

        module.legacyLogCleanTasks = lambda: [
            {'id': 1, 'name': '[勿删]项目[旧任务项目]日志清理', 'project_name': '旧任务项目', 'enabled': True},
            {'id': 2, 'name': '[勿删]项目[同名项目]日志清理', 'project_name': '同名项目', 'enabled': True},
        ]

        assert module.normalizeProjectLogCleanState(records['legacy-single'])['log_clean_enabled'] is True
        assert module.normalizeProjectLogCleanState(records['duplicate-a'])['log_clean_enabled'] is False
        assert module.normalizeProjectLogCleanState(records['duplicate-b'])['log_clean_enabled'] is False

        preheat_dir = os.path.join(work_dir, 'preheat-ok')
        no_lock_dir = os.path.join(work_dir, 'preheat-no-lock')
        logs_dir = os.path.join(preheat_dir, 'logs')
        os.makedirs(logs_dir)
        os.makedirs(no_lock_dir)
        with open(os.path.join(preheat_dir, 'package-lock.json'), 'w', encoding='utf-8') as fp:
            fp.write('{"lockfileVersion": 3}\n')
        records.update({
            'preheat-ok': {'id': 'preheat-ok', 'name': '有锁文件项目', 'path': preheat_dir, 'log_clean_enabled': True},
            'preheat-no-lock': {'id': 'preheat-no-lock', 'name': '无锁文件项目', 'path': no_lock_dir, 'log_clean_enabled': False},
            'preheat-missing': {'id': 'preheat-missing', 'name': '缺失目录项目', 'path': os.path.join(work_dir, 'missing'), 'log_clean_enabled': True},
        })
        commands = []

        class ProcessResult:
            returncode = 0
            stdout = 'npm ci ok'

        def fake_run(command, **kwargs):
            commands.append((command, kwargs))
            return ProcessResult()

        module.subprocess.run = fake_run
        preheat = module.projectPreheatAll()
        assert preheat['status'] is True
        assert preheat['data']['success'] == ['有锁文件项目']
        assert {item['reason'] for item in preheat['data']['skipped']} == {'未找到 package-lock.json', '项目目录不存在'}
        assert commands == [
            (['bash', '-lc', 'source /root/.bashrc >/dev/null 2>&1 || true; npm ci'], {
                'cwd': preheat_dir,
                'stdout': module.subprocess.PIPE,
                'stderr': module.subprocess.STDOUT,
                'text': True,
                'timeout': 3600,
            })
        ]

        cleaned_paths = []
        clean_tool = types.ModuleType('clean_tool')
        clean_tool.cleanPath = lambda path, rules, pattern: cleaned_paths.append((path, rules, pattern))
        original_clean_tool = sys.modules.get('clean_tool')
        sys.modules['clean_tool'] = clean_tool
        try:
            module.getArgs = lambda: {'saveAllDay': '2', 'saveOther': '0', 'saveMaxDay': '15'}
            clean_result = module.projectLogCleanAll()
        finally:
            if original_clean_tool is None:
                sys.modules.pop('clean_tool', None)
            else:
                sys.modules['clean_tool'] = original_clean_tool
        assert clean_result['status'] is True
        assert cleaned_paths == [(logs_dir, {'saveAllDay': 2, 'saveOther': 0, 'saveMaxDay': 15}, '*')]
        assert len(clean_result['data']['skipped']) == 2

        deleted_ids = []
        cron_module = types.ModuleType('crontab_api')

        class CronApi:
            def delete(self, task_id):
                deleted_ids.append(task_id)
                return True, 'OK'

        cron_module.crontab_api = CronApi
        original_crontab_api = sys.modules.get('crontab_api')
        sys.modules['crontab_api'] = cron_module
        try:
            module.getCronTask = lambda name: {'id': 100} if name == module.PROJECT_LOG_CLEAN_TASK_NAME else None
            module.legacyLogCleanTasks = lambda: [
                {'id': 11, 'name': '[勿删]项目[有锁文件项目]日志清理', 'project_name': '有锁文件项目', 'enabled': True},
                {'id': 12, 'name': '[勿删]项目[无锁文件项目]日志清理', 'project_name': '无锁文件项目', 'enabled': False},
                {'id': 13, 'name': '[勿删]项目[同名项目]日志清理', 'project_name': '同名项目', 'enabled': True},
                {'id': 14, 'name': '[勿删]项目[不存在项目]日志清理', 'project_name': '不存在项目', 'enabled': True},
            ]
            migration = module.migrateLegacyLogCleanTasks()
            assert migration['status'] is True
            assert deleted_ids == [11, 12]
            assert records['preheat-ok']['log_clean_enabled'] is True
            assert records['preheat-no-lock']['log_clean_enabled'] is False
            assert len(migration['data']['skipped']) == 2

            module.getCronTask = lambda name: None
            no_global_task = module.migrateLegacyLogCleanTasks()
            assert no_global_task['status'] is False
            assert deleted_ids == [11, 12]
        finally:
            if original_crontab_api is None:
                sys.modules.pop('crontab_api', None)
            else:
                sys.modules['crontab_api'] = original_crontab_api
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def test_ha_preheat_policy():
    runtime_dir = tempfile.mkdtemp(prefix='ha-manager-preheat-task-test-')
    old_runtime_dir = os.environ.get('HA_MANAGER_LOCAL_RUNTIME_DIR')
    try:
        os.environ['HA_MANAGER_LOCAL_RUNTIME_DIR'] = runtime_dir
        module = load_module('ha_manager_preheat_task_test', HA_MANAGER_PATH)
        item = next(item for item in module.HA_CHECK_DEFS if item.get('name') == module.JIANGHUJS_PREHEAT_TASK_NAME)
        assert item['master'] == 'disabled'
        assert item['standby'] == 'enabled'
        assert "closeCrontab 'JianghuJS管理器项目预备'" in module._step_script_body('close_jianghujs_preheat', 'master')
        assert "openCrontab 'JianghuJS管理器项目预备'" in module._step_script_body('open_jianghujs_preheat', 'standby')

        class Query:
            def __init__(self, task):
                self.task = task

            def where(self, *args):
                return self

            def field(self, *args):
                return self

            def find(self):
                return self.task

        class PanelDb:
            def __init__(self, task):
                self.task = task

            def M(self, table):
                return Query(self.task)

        original_mw = module.mw
        try:
            module.mw = PanelDb({'id': 1, 'status': 1})
            assert module._run_health_check_item(item, 'standby')['status'] == 'pass'
            assert module._run_health_check_item(item, 'master')['status'] == 'fail'

            module.mw = PanelDb({'id': 1, 'status': 0})
            assert module._run_health_check_item(item, 'master')['status'] == 'pass'
            assert module._run_health_check_item(item, 'standby')['status'] == 'fail'

            module.mw = PanelDb(None)
            assert module._run_health_check_item(item, 'master')['status'] == 'warning'
            assert module._run_health_check_item(item, 'standby')['status'] == 'warning'
        finally:
            module.mw = original_mw

        missing_name = 'Codex-验证-不存在计划任务'
        switch_result = subprocess.run(
            ['python3', os.path.join(ROOT, 'scripts/switch.py'), 'openCrontab', missing_name],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
        )
        assert switch_result.returncode == 0

        original_args = sys.argv[:]
        original_return = module._return
        original_run_script_content = module._run_script_content
        try:
            module._return = lambda status, msg, data=None: {'status': bool(status), 'msg': msg, 'data': data or {}}
            executed_scripts = []
            module._run_script_content = lambda script, title, run_id, timeout=1800: executed_scripts.append(script)
            for target_role, step_key, action in [
                ('master', 'close_jianghujs_preheat', 'closeCrontab'),
                ('standby', 'open_jianghujs_preheat', 'openCrontab'),
            ]:
                sys.argv = [HA_MANAGER_PATH, 'run_step', json.dumps({
                    'target_role': target_role,
                    'step_key': step_key,
                    'run_id': 'TEST_' + step_key,
                })]
                result = module.run_step()
                assert result['status'] is True
                assert action in executed_scripts[-1]
                assert module.JIANGHUJS_PREHEAT_TASK_NAME in executed_scripts[-1]
        finally:
            sys.argv = original_args
            module._return = original_return
            module._run_script_content = original_run_script_content
    finally:
        if old_runtime_dir is None:
            os.environ.pop('HA_MANAGER_LOCAL_RUNTIME_DIR', None)
        else:
            os.environ['HA_MANAGER_LOCAL_RUNTIME_DIR'] = old_runtime_dir
        shutil.rmtree(runtime_dir, ignore_errors=True)


def main():
    test_jianghujs_tasks()
    test_ha_preheat_policy()
    print('ok')


if __name__ == '__main__':
    main()
