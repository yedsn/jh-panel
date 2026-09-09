# coding: utf-8

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile


ROOT = '/www/server/jh-panel'
PLUGIN_PATH = os.path.join(ROOT, 'plugins/ha_manager_local/index.py')
SCRIPT_PATH = os.path.join(ROOT, 'plugins/ha_manager_local/js/ha_manager_local.js')


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_connection_snapshot_backend():
    runtime_dir = tempfile.mkdtemp(prefix='ha-manager-local-connection-test-')
    config_dir = tempfile.mkdtemp(prefix='ha-manager-local-openresty-conf-')
    config_path = os.path.join(config_dir, 'nginx.conf')
    vhost_dir = os.path.join(config_dir, 'vhost')
    old_runtime_dir = os.environ.get('HA_MANAGER_LOCAL_RUNTIME_DIR')
    module_name = 'ha_manager_local_connection_impact_test'
    try:
        os.environ['HA_MANAGER_LOCAL_RUNTIME_DIR'] = runtime_dir
        module = load_module(module_name)
        module.OPENRESTY_CONF = config_path
        module._systemctl_active = lambda service: service == 'openresty'
        with open(config_path, 'w', encoding='utf-8') as fp:
            fp.write('''http {
  keepalive_timeout 60;
  server {
    listen 82;
    server_name 127.0.0.1;
    location /nginx_status {
      stub_status on;
    }
  }
}
''')
        assert module._openresty_status_ports() == (['82'], '')

        os.makedirs(vhost_dir)
        included_status_path = os.path.join(vhost_dir, 'status.conf')
        with open(config_path, 'w', encoding='utf-8') as fp:
            fp.write('http { include vhost/*.conf; }\n')
        with open(included_status_path, 'w', encoding='utf-8') as fp:
            fp.write('''server {
  listen 8181;
  location /nginx_status { stub_status; }
}
''')
        assert module._openresty_status_ports() == (['8181'], '')

        with open(config_path, 'w', encoding='utf-8') as fp:
            fp.write('''http {
  keepalive_timeout 60;
  server {
    listen 82;
    server_name 127.0.0.1;
    location /nginx_status {
      stub_status on;
    }
  }
}
''')
        status_text = '''Active connections: 12
server accepts handled requests
 43 43 147
Reading: 1 Writing: 2 Waiting: 9
'''
        module._read_openresty_status = lambda port: status_text
        snapshot = module._openresty_connection_snapshot()
        assert snapshot == {
            'active': 11,
            'reading': 1,
            'writing': 1,
            'waiting': 9,
            'accepts': 43,
            'handled': 43,
            'requests': 147,
            'raw_active': 12,
            'available': True,
            'port': '82',
            'collected_at': snapshot['collected_at'],
            'reason': '',
        }

        module._read_openresty_status = lambda port: '<html><title>404</title></html>'
        unavailable = module._openresty_connection_snapshot()
        assert unavailable['available'] is False
        assert unavailable['port'] == '82'
        assert '缺少 active 指标' in unavailable['reason']

        with open(config_path, 'w', encoding='utf-8') as fp:
            fp.write('''http {
  server {
    listen 80;
    location /nginx_status { stub_status on; }
  }
}
''')
        requested_ports = []
        module._read_openresty_status = lambda port: requested_ports.append(port) or status_text
        port_80_snapshot = module._openresty_connection_snapshot()
        assert port_80_snapshot['available'] is True
        assert requested_ports == ['80']

        with open(config_path, 'w', encoding='utf-8') as fp:
            fp.write('http { server { listen 82; } }\n')
        module._openresty_listen_ports = lambda: ([], '未发现 OpenResty 监听端口')
        module._read_openresty_status = lambda port: (_ for _ in ()).throw(RuntimeError('不可访问'))
        no_status_page = module._openresty_connection_snapshot()
        assert no_status_page['available'] is False
        assert no_status_page['reason'] == '未找到包含 /nginx_status 和 stub_status 的监听端口'
        assert no_status_page['port'] == ''

        module._openresty_listen_ports = lambda: (['80'], '')
        module._read_openresty_status = lambda port: status_text
        fallback_probe = module._openresty_connection_snapshot()
        assert fallback_probe['available'] is True
        assert fallback_probe['port'] == '80'

        with open(config_path, 'w', encoding='utf-8') as fp:
            fp.write('''http {
  server {
    listen 80 proxy_protocol;
    location /nginx_status { stub_status on; }
  }
}
''')
        module._read_openresty_status = lambda port: (_ for _ in ()).throw(RuntimeError('Remote end closed connection without response'))
        module._read_openresty_status_with_proxy_protocol = lambda port: status_text
        proxy_protocol_snapshot = module._openresty_connection_snapshot()
        assert proxy_protocol_snapshot['available'] is True
        assert proxy_protocol_snapshot['port'] == '80'

        with open(config_path, 'w', encoding='utf-8') as fp:
            fp.write('''http {
  server {
    listen 80;
    location /nginx_status { stub_status on; }
  }
}
''')
        module._read_openresty_status = lambda port: (_ for _ in ()).throw(RuntimeError('Remote end closed connection without response'))
        closed_connection = module._openresty_connection_snapshot()
        assert '端口 80: 本机服务提前关闭了状态页连接' in closed_connection['reason']

        module._systemctl_active = lambda service: False
        stopped = module._openresty_connection_snapshot()
        assert stopped['available'] is False
        assert stopped['reason'] == 'OpenResty 未运行'
        module._health_checks = lambda role: []
        module._health_summary = lambda checks: ('normal', '正常')
        module._external_closed = lambda: True
        module._step_list = lambda target_role: []
        module._step_state = lambda: {}
        module._read_logs = lambda: []
        stopped_state = module._state(module._default_config())
        assert stopped_state['external_closed'] is True
        assert 'connection_snapshot' not in stopped_state
        assert stopped_state['checks'] == []
        initial_state = module._state(module._default_config(), include_health=False)
        assert 'checks' not in initial_state
        assert 'health_status' not in initial_state

        module._return = lambda status, msg, data=None: {'status': bool(status), 'msg': msg, 'data': data or {}}
        module._systemctl_active = lambda service: service == 'openresty'
        with open(config_path, 'w', encoding='utf-8') as fp:
            fp.write('''http {
  keepalive_timeout 60;
  server {
    listen 82;
    location /nginx_status { stub_status on; }
  }
}
''')
        module._read_openresty_status = lambda port: status_text
        module._openresty_standby = lambda: '停止 OpenResty'
        module._external_closed = lambda: True
        module._queue_cloud_report = lambda reason: None
        module._state = lambda cfg: {'external_closed': True}
        success = module.close_external_service()
        assert success['status'] is True
        assert success['data']['connection_snapshot']['active'] == 11
        with open(module.ACTION_LOG_PATH, 'r', encoding='utf-8') as fp:
            action_log = fp.read()
        assert '关闭对外服务前连接快照：当前活动连接 11' in action_log

        module._openresty_standby = lambda: (_ for _ in ()).throw(RuntimeError('模拟停止失败'))
        failed = module.close_external_service()
        assert failed['status'] is False
        assert failed['data']['connection_snapshot']['available'] is True
        with open(module.ACTION_LOG_PATH, 'r', encoding='utf-8') as fp:
            action_log = fp.read()
        assert '关闭对外服务失败: 模拟停止失败' in action_log

        module._openresty_listen_ports = lambda: (['82'], '')
        module.mw.execShell = lambda command: ('ESTAB 0 7 127.0.0.1:82 192.168.3.8:54321\nESTAB 1 0 127.0.0.1:9999 192.168.3.8:54322\n', '', 0)
        details = module._openresty_connection_details()
        assert details['available'] is True
        assert details['total'] == 1
        assert details['connections'] == [{
            'local_port': '82',
            'remote_address': '192.168.3.8:54321',
            'recv_q': '0',
            'send_q': '7'
        }]
        assert details['keepalive_timeout'] == {
            'available': True,
            'value': '60',
            'text': '约 60 秒',
            'reason': ''
        }
    finally:
        sys.modules.pop(module_name, None)
        if old_runtime_dir is None:
            os.environ.pop('HA_MANAGER_LOCAL_RUNTIME_DIR', None)
        else:
            os.environ['HA_MANAGER_LOCAL_RUNTIME_DIR'] = old_runtime_dir
        shutil.rmtree(runtime_dir, ignore_errors=True)
        shutil.rmtree(config_dir, ignore_errors=True)


def test_close_confirmation_frontend():
    script = r'''
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync(process.argv[2], 'utf8');
const jquery = function() { return {}; };
jquery.extend = function(deep, target, source) { return Object.assign(target, source || {}); };
let renderedHtml = '';
const context = {console: console, window: {}, $: function() {
  return {
    html: function(value) { if (value !== undefined) renderedHtml = value; return this; },
    removeClass: function() { return this; },
    addClass: function() { return this; }
  };
}};
context.$.extend = jquery.extend;
vm.createContext(context);
vm.runInContext(source, context);
const realRenderOverview = context.hmlRenderOverview;

function setCommonStubs() {
  context.hmlLog = function() {};
  context.hmlRender = function() {};
  context.hmlRenderOverview = function() {};
  context.hmlRefreshBrowserTitle = function() {};
  context.layer = {msg: function() {}};
  context.hmlState.external_closed = false;
}

setCommonStubs();
{
  let completeStateLoad = null;
  context.hmlState.overview_loading = true;
  context.hmlRenderOverview = realRenderOverview;
  context.hmlRender = function() { context.hmlRenderOverview(); };
  context.hmlPost = function(method, args, success) {
    if (method === 'get_state') completeStateLoad = success;
  };
  context.hmlBoot();
  if (!completeStateLoad || renderedHtml.indexOf('hml-overview-skeleton') === -1 || renderedHtml.indexOf('hml-skeleton-button') === -1 || renderedHtml.indexOf('hml-skeleton-connection') === -1) throw new Error('基础状态加载期间未展示总览骨架屏');
}

setCommonStubs();
{
  let bootCalls = [];
  let renderCount = 0;
  let completeConnectionLoad = null;
  let completeHealthLoad = null;
  context.hmlEnsureFlowConfig = function(callback) { bootCalls.push('flow_config'); callback(); };
  context.hmlRender = function() { renderCount += 1; };
  context.hmlPost = function(method, args, success) {
    bootCalls.push(method);
    if (method === 'get_state') success({role: 'master', external_closed: false, checks: []});
    if (method === 'get_connection_snapshot') completeConnectionLoad = success;
    if (method === 'health_check') completeHealthLoad = success;
  };
  context.hmlBoot();
  if (bootCalls.join(',') !== 'get_state,flow_config,get_connection_snapshot,health_check' || renderCount !== 2 || context.hmlState.overview_loading || !context.hmlState.connection_snapshot.loading || !context.hmlState.health_loading || !completeConnectionLoad || !completeHealthLoad) throw new Error('总览基础数据未同步加载完成');
  completeConnectionLoad({connection_snapshot: {available: true, active: 2, reading: 0, writing: 1, waiting: 1}});
  completeHealthLoad({checks: [{status: 'fail'}], health_status: 'warning', health_text: '自检异常 1 项', external_closed: false});
  if (context.hmlState.connection_snapshot.active !== 2 || context.hmlConnectionRefreshBusy || context.hmlState.health_loading || context.hmlState.checks.length !== 1) throw new Error('异步状态未回填总览');
}

setCommonStubs();
let calls = [];
context.hmlPost = function(method, args, success) {
  calls.push(method);
  if (method === 'get_connection_snapshot') success({connection_snapshot: {available: true, active: 3, reading: 1, writing: 1, waiting: 1}});
};
context.hmlSafeMessageConfirm = function(title, message, callback) {};
context.hmlToggleExternalService();
if (calls.join(',') !== 'get_connection_snapshot') throw new Error('取消确认时调用了关闭接口: ' + calls.join(','));

setCommonStubs();
calls = [];
context.hmlPost = function(method, args, success) {
  calls.push(method);
  if (method === 'get_connection_snapshot') success({connection_snapshot: {available: true, active: 0, reading: 0, writing: 0, waiting: 0}});
  if (method === 'close_external_service') success({connection_snapshot: {available: true, active: 0, reading: 0, writing: 0, waiting: 0}, state_snapshot: {external_closed: true}});
};
context.hmlSafeMessageConfirm = function(title, message, callback) {
  if (message.indexOf('可能中断当前访问连接') === -1 || message.indexOf('不等同于真实用户人数') === -1) throw new Error('确认提示缺少风险说明');
  callback();
};
context.hmlToggleExternalService();
if (calls.join(',') !== 'get_connection_snapshot,close_external_service') throw new Error('确认后的调用顺序不正确: ' + calls.join(','));

setCommonStubs();
calls = [];
context.hmlPost = function(method, args, success, failure) {
  calls.push(method);
  if (method === 'get_connection_snapshot') failure({msg: '快照接口不可用'});
  if (method === 'close_external_service') success({connection_snapshot: {available: false, reason: '快照接口不可用'}, state_snapshot: {external_closed: true}});
};
context.hmlSafeMessageConfirm = function(title, message, callback) {
  if (message.indexOf('当前连接数暂时无法获取') === -1 || message.indexOf('快照接口不可用') === -1) throw new Error('接口失败时缺少降级确认提示');
  callback();
};
context.hmlToggleExternalService();
if (calls.join(',') !== 'get_connection_snapshot,close_external_service') throw new Error('接口失败后的调用顺序不正确: ' + calls.join(','));

let refreshed = false;
calls = [];
context.hmlState.view = 'overview';
context.hmlRenderOverview = function() { refreshed = true; };
context.$ = function() { return {prop: function() { return this; }, text: function() { return this; }}; };
context.$.extend = function(deep, target, source) { return Object.assign(target, source || {}); };
context.hmlConnectionRefreshBusy = false;
context.hmlPost = function(method, args, success) {
  calls.push(method);
  if (method === 'get_connection_snapshot') success({connection_snapshot: {available: true, active: 8, reading: 2, writing: 3, waiting: 3}});
};
context.hmlRefreshConnectionSnapshot();
if (calls.join(',') !== 'get_connection_snapshot' || !refreshed || context.hmlState.connection_snapshot.active !== 8 || context.hmlConnectionRefreshBusy) throw new Error('刷新连接数未更新状态');

let detailHtml = '';
context.layer = {
  msg: function() { return 1; },
  close: function() {},
  open: function(options) { detailHtml = options.content; }
};
context.hmlPost = function(method, args, success) {
  calls.push(method);
  if (method === 'get_connection_details') success({connection_details: {
    available: true,
    total: 1,
    truncated: false,
    collected_at: '2026-09-09 14:00:00',
    keepalive_timeout: {available: true, value: '60', text: '约 60 秒', reason: ''},
    connections: [{remote_address: '192.168.3.8:54321', local_port: '82', recv_q: '0', send_q: '7'}]
  }});
};
context.hmlShowConnectionDetails();
if (calls[calls.length - 1] !== 'get_connection_details' || detailHtml.indexOf('192.168.3.8:54321') === -1 || detailHtml.indexOf('HTTP keep-alive') === -1 || detailHtml.indexOf('约 60 秒') === -1) throw new Error('连接详情弹窗未正确展示');

const emptyConnectionHtml = context.hmlConnectionSnapshotHtml({available: true, active: 0, reading: 0, writing: 0, waiting: 0, collected_at: '2026-09-09 14:10:00'}, true);
const activeConnectionHtml = context.hmlConnectionSnapshotHtml({available: true, active: 1, reading: 0, writing: 1, waiting: 0}, true);
const detailRowStart = emptyConnectionHtml.indexOf('class="hml-connection-values hml-connection-detail-row"');
const detailRowEnd = emptyConnectionHtml.indexOf('</span><span class="hml-connection-time"');
if (detailRowStart === -1 || detailRowEnd <= detailRowStart || emptyConnectionHtml.indexOf('onclick="hmlShowConnectionDetails()"') === -1 || emptyConnectionHtml.indexOf('Reading 0') === -1 || emptyConnectionHtml.indexOf('hml-connection-detail-link-empty') === -1 || emptyConnectionHtml.indexOf('hml-connection-label-active') !== -1 || activeConnectionHtml.indexOf('hml-connection-detail-link-active') === -1 || activeConnectionHtml.indexOf('hml-connection-label-active') === -1 || emptyConnectionHtml.indexOf('采集于 2026-09-09 14:10:00</span>') === -1) throw new Error('连接数颜色状态未正确渲染');
'''
    result = subprocess.run(
        ['node', '-', SCRIPT_PATH],
        input=script,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout


def main():
    test_connection_snapshot_backend()
    test_close_confirmation_frontend()
    print('ok')


if __name__ == '__main__':
    main()
