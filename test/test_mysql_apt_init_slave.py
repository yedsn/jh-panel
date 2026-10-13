# coding: utf-8
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from pymysql.err import OperationalError


PLUGIN_PATH = Path(__file__).resolve().parents[1] / 'plugins/mysql-apt/index.py'
spec = importlib.util.spec_from_file_location('mysql_apt_init_slave_test', PLUGIN_PATH)
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


class InitSlaveStatusTest(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        self.db.query.return_value = ()
        self.conn = Mock()
        self.conn.field.return_value.find.return_value = {
            'ip': '192.0.2.1', 'port': 22, 'id_rsa': '/test/key',
        }
        self.ssh_client = Mock()
        stdout = Mock()
        stdout.read.return_value = json.dumps({
            'status': True,
            'data': {
                'mode': 'gtid',
                'info': {'username': 'replica', 'password': 'test-password'},
                'cmd': "CHANGE MASTER TO MASTER_HOST='192.0.2.1', MASTER_AUTO_POSITION=1",
            },
        }).encode()
        stdout.channel.recv_exit_status.return_value = 0
        stderr = Mock()
        stderr.read.return_value = b''
        self.ssh_client.connect.return_value.exec_command.return_value = (None, stdout, stderr)
        self.args = self.patch('getArgs', return_value={})
        self.mysql = self.patch('pMysqlDb', return_value=self.db)
        self.sqlite = self.patch('pSqliteDb', return_value=self.conn)
        self.ssh_factory = self.patch('master_ssh_client', return_value=self.ssh_client)
        self.patch('recognizeDbMode', return_value='gtid')
        shell_patch = patch.object(plugin.mw, 'execShell', return_value=('', ''))
        self.shell = shell_patch.start()
        self.addCleanup(shell_patch.stop)

    def patch(self, name, **kwargs):
        patcher = patch.object(plugin, name, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def run_init(self):
        return json.loads(plugin.initSlaveStatus())

    def test_status_query_error_preserves_original_error_and_stops(self):
        for raised in (False, True):
            with self.subTest(raised=raised):
                error = OperationalError(1045, 'Access denied for test account')
                self.db.query.side_effect = error if raised else None
                self.db.query.return_value = error
                result = self.run_init()
                self.assertFalse(result['status'])
                self.assertIn('读取本机从库状态异常', result['msg'])
                self.assertIn('1045', result['msg'])
                self.assertIn('Access denied', result['msg'])
                self.assertNotIn('has no len', result['msg'])
                self.sqlite.assert_not_called()
                self.ssh_factory.assert_not_called()

    def test_connection_setup_error_is_reported(self):
        self.mysql.side_effect = RuntimeError('无法读取本机连接配置')
        result = self.run_init()
        self.assertFalse(result['status'])
        self.assertIn('无法读取本机连接配置', result['msg'])
        self.ssh_factory.assert_not_called()

    def test_unexpected_status_result_stops_before_ssh(self):
        for value in (None, False, 'connection error', {}):
            with self.subTest(value=value):
                self.db.query.return_value = value
                result = self.run_init()
                self.assertFalse(result['status'])
                self.assertIn('返回数据格式异常', result['msg'])
                self.ssh_factory.assert_not_called()

    def test_existing_replication_is_not_reinitialized(self):
        self.db.query.return_value = [{'Master_Host': '192.0.2.1'}]
        self.assertFalse(self.run_init()['status'])
        self.ssh_factory.assert_not_called()

    def test_empty_list_and_tuple_allow_initialization(self):
        for value in ([], ()):
            with self.subTest(value=value):
                self.db.query.return_value = value
                self.assertTrue(self.run_init()['status'])
        self.assertEqual(self.ssh_client.close.call_count, 2)
        self.assertEqual(self.shell.call_count, 2)

    def test_each_sql_failure_stops_later_steps_and_closes_ssh(self):
        self.args.return_value = {'gtid_purged': 'test-uuid:1-10'}
        steps = [
            '停止本机Slave', '重置本机GTID', '重置本机GTID', '重置本机GTID',
            '设置本机主从同步命令', '启动本机Slave', '开启本机只读模式', '开启本机只读模式',
        ]
        for failed_index, step in enumerate(steps, 1):
            with self.subTest(step=step, index=failed_index):
                self.db.query.reset_mock()
                self.ssh_client.close.reset_mock()
                self.db.query.side_effect = [()] * failed_index + [OperationalError(1227, 'Access denied')]
                result = self.run_init()
                self.assertFalse(result['status'])
                self.assertIn(step, result['msg'])
                self.assertIn('1227', result['msg'])
                self.assertEqual(self.db.query.call_count, failed_index + 1)
                self.ssh_client.close.assert_called_once()
                self.shell.assert_not_called()


class MasterRepSlaveUserCmdTest(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        self.db.query.return_value = [{'File': 'mysql-bin.000001', 'Position': 154}]
        self.conn = Mock()
        for name in ('field', 'limit', 'where', 'order'):
            getattr(self.conn, name).return_value = self.conn
        self.conn.count.return_value = 1
        self.conn.select.return_value = [{'username': 'replica', 'password': 'test-password'}]
        patcher = patch.multiple(plugin,
                                 getArgs=Mock(return_value={'username': '', 'db': ''}),
                                 pSqliteDb=Mock(return_value=self.conn),
                                 pMysqlDb=Mock(return_value=self.db),
                                 getMyPort=Mock(return_value='3306'),
                                 recognizeDbMode=Mock(return_value='gtid'))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(plugin.mw, 'getLocalIp', return_value='192.0.2.1')
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cmd(self):
        return json.loads(plugin.getMasterRepSlaveUserCmd('5.7'))

    def test_master_connection_error_is_returned_as_json(self):
        for raised in (False, True):
            with self.subTest(raised=raised):
                error = OperationalError(2003, 'Connection refused')
                self.db.query.side_effect = error if raised else None
                self.db.query.return_value = error
                result = self.run_cmd()
                self.assertFalse(result['status'])
                self.assertIn('读取主库状态失败', result['msg'])
                self.assertIn('2003', result['msg'])
                self.assertIn('Connection refused', result['msg'])

    def test_missing_account_stops_before_mysql(self):
        self.conn.select.return_value = []
        result = self.run_cmd()
        self.assertFalse(result['status'])
        self.assertIn('未找到同步账户', result['msg'])
        self.db.query.assert_not_called()

    def test_empty_status_reports_binlog_disabled(self):
        for value in ([], ()):
            self.db.query.return_value = value
            result = self.run_cmd()
            self.assertFalse(result['status'])
            self.assertIn('未开启binlog', result['msg'])

    def test_invalid_status_is_not_treated_as_binlog_disabled(self):
        for value in (None, False, 'connection error', {}):
            self.db.query.return_value = value
            result = self.run_cmd()
            self.assertFalse(result['status'])
            self.assertIn('返回数据格式异常', result['msg'])

    def test_gtid_and_classic_commands_remain_available(self):
        for mode in ('gtid', 'classic'):
            for rows in ([{'File': 'mysql-bin.000001', 'Position': 154}],
                         ({'File': 'mysql-bin.000001', 'Position': 154},)):
                plugin.recognizeDbMode.return_value = mode
                self.db.query.return_value = rows
                result = self.run_cmd()
                self.assertTrue(result['status'])
                expected = 'MASTER_AUTO_POSITION=1' if mode == 'gtid' else 'MASTER_LOG_POS=154'
                self.assertIn(expected, result['data']['cmd'])


if __name__ == '__main__':
    unittest.main()
