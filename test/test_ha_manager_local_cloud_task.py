# coding: utf-8

import importlib.util
import json
import os
import shutil
import sys
import tempfile


ROOT = '/www/server/jh-panel'
PLUGIN_PATH = os.path.join(ROOT, 'plugins/ha_manager_local/index.py')


def write_json(path, data):
    with open(path, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False)


def main():
    runtime_dir = tempfile.mkdtemp(prefix='ha-manager-local-cloud-task-')
    old_runtime_dir = os.environ.get('HA_MANAGER_LOCAL_RUNTIME_DIR')
    module_name = 'ha_manager_local_cloud_task_test'
    try:
        os.environ['HA_MANAGER_LOCAL_RUNTIME_DIR'] = runtime_dir
        os.makedirs(os.path.join(runtime_dir, 'data'))
        os.makedirs(os.path.join(runtime_dir, 'logs', 'steps'))
        sys.path[:0] = [os.path.join(ROOT, 'class/core'), os.path.join(ROOT, 'class/plugin')]
        spec = importlib.util.spec_from_file_location(module_name, PLUGIN_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        task_id = 'TASK_FLOW_TEST'
        cfg = module._default_config()
        cfg.update({
            'cloud_active_task_id': task_id,
            'desired_role': 'standby',
            'role': 'master',
            'switch_status': 'idle',
            'last_action': '步骤完成: close_external',
        })
        flow_steps = module._step_list('standby')
        first_step = flow_steps[0]['key']
        write_json(module.STEP_STATE_PATH, {
            'standby': {
                first_step: {
                    'state': 'done',
                    'run_id': 'FLOW_TEST_LOCAL_001',
                    'updated_at': '2026-09-08 18:00:00',
                }
            }
        })
        partial = module._cloud_task_summary(cfg, {})
        assert partial['status'] == 'running', partial
        assert partial['next_step'], partial
        assert any(item['status'] == 'pending' for item in partial['step_summary']), partial

        write_json(module.STEP_STATE_PATH, {
            'standby': {
                step['key']: {
                    'state': 'done',
                    'run_id': 'FLOW_TEST_LOCAL_{0}'.format(index),
                    'updated_at': '2026-09-08 18:00:00',
                }
                for index, step in enumerate(flow_steps, 1)
            }
        })
        completed = module._cloud_task_summary(cfg, {})
        assert completed['status'] == 'success', completed
        assert not completed['next_step'], completed
        print('ok')
    finally:
        sys.modules.pop(module_name, None)
        if old_runtime_dir is None:
            os.environ.pop('HA_MANAGER_LOCAL_RUNTIME_DIR', None)
        else:
            os.environ['HA_MANAGER_LOCAL_RUNTIME_DIR'] = old_runtime_dir
        shutil.rmtree(runtime_dir, ignore_errors=True)


if __name__ == '__main__':
    main()
