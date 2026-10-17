#!/usr/bin/env python3

import importlib.util
import json
import os
import pathlib
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock


SCRIPT_PATH = pathlib.Path(__file__).resolve().parents[1] / "monitor__server_resource_report.py"
SPEC = importlib.util.spec_from_file_location("server_resource_report", SCRIPT_PATH)
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)


def mount(source, target, fstype, category=None):
    resolved_category, reason = REPORT.classify_filesystem(fstype, source)
    return {
        "source": source,
        "target": target,
        "fstype": fstype,
        "options": "",
        "category": category or resolved_category,
        "reason": reason,
    }


class ModuleSelectionTests(unittest.TestCase):
    def test_default_and_custom_modules(self):
        self.assertEqual(REPORT.parse_modules(None), REPORT.DEFAULT_MODULE_KEYS)
        self.assertEqual(REPORT.DEFAULT_MODULE_KEYS, ["system", "cpu", "memory", "disk_space"])
        self.assertEqual(REPORT.parse_modules("1,cpu,9"), ["system", "cpu", "speedtest"])
        self.assertEqual(len(REPORT.parse_modules("all")), len(REPORT.MODULES))

    def test_invalid_module_is_rejected(self):
        with self.assertRaises(ValueError):
            REPORT.parse_modules("1,unknown")

    def test_invalid_threshold_order_is_rejected(self):
        parser = REPORT.build_parser()
        args = parser.parse_args(["--cpu-warn", "95", "--cpu-crit", "90"])
        with self.assertRaises(ValueError):
            REPORT.validate_args(args)

    def test_non_interactive_active_tests_require_flags(self):
        selected, skipped = REPORT.resolve_active_modules(
            ["system", "disk_benchmark", "speedtest"], False, False, False
        )
        self.assertEqual(selected, ["system"])
        self.assertEqual(set(skipped), {"disk_benchmark", "speedtest"})

    def test_interactive_active_test_confirmation_and_cancel(self):
        with mock.patch.object(REPORT, "prompt", side_effect=["y", "n"]):
            selected, skipped = REPORT.resolve_active_modules(
                ["disk_benchmark", "speedtest"], True, False, False
            )
        self.assertEqual(selected, ["disk_benchmark"])
        self.assertEqual(skipped, {"speedtest": "未获得主动测试明确确认"})


class InteractiveSelectionTests(unittest.TestCase):
    def checklist_options(self, command):
        index = command.index("--checklist")
        return command[index + 5 :]

    def test_dialog_checklist_defaults_to_first_four_modules(self):
        options = self.checklist_options(REPORT.build_dialog_checklist_command())
        states = {options[i]: options[i + 2] for i in range(0, len(options), 3)}
        self.assertEqual([tag for tag in states if states[tag] == "on"], ["1", "2", "3", "4"])
        self.assertTrue(all(states[tag] == "off" for tag in states if tag not in ("1", "2", "3", "4")))

    def test_dialog_selection_maps_tags_in_module_order(self):
        with mock.patch.object(REPORT, "run_dialog", return_value=(0, "3\n1\n")):
            self.assertEqual(REPORT.dialog_module_selection(), ["system", "memory"])

    def test_dialog_selection_repeats_when_nothing_chosen(self):
        results = [(0, ""), (0, "2")]
        with mock.patch.object(REPORT, "run_dialog", side_effect=results) as run:
            self.assertEqual(REPORT.dialog_module_selection(), ["cpu"])
        self.assertEqual(run.call_count, 2)

    def test_dialog_cancel_raises(self):
        with mock.patch.object(REPORT, "run_dialog", return_value=(1, "")):
            with self.assertRaises(REPORT.SelectionCancelled):
                REPORT.dialog_module_selection()

    def test_dialog_failure_falls_back_to_text_selection(self):
        with mock.patch.object(REPORT, "ensure_dialog", return_value=True), mock.patch.object(
            REPORT, "dialog_module_selection", return_value=None
        ), mock.patch.object(REPORT, "prompt", return_value="") as prompt:
            self.assertEqual(REPORT.interactive_module_selection(), ["system", "cpu", "memory", "disk_space"])
        self.assertIn("默认1,2,3,4", prompt.call_args[0][0])

    def test_interactive_selection_uses_dialog_result(self):
        with mock.patch.object(REPORT, "ensure_dialog", return_value=True), mock.patch.object(
            REPORT, "dialog_module_selection", return_value=["disk_io"]
        ):
            self.assertEqual(REPORT.interactive_module_selection(), ["disk_io"])

    def test_ensure_dialog_auto_installs_when_missing(self):
        state = {"dialog": False}
        commands = []

        def fake_exists(name):
            if name == "dialog":
                return state["dialog"]
            return name == "apt-get"

        def fake_run(command, timeout=15, cwd=None):
            commands.append(list(command))
            if "install" in command:
                state["dialog"] = True
            return "", "", 0

        with mock.patch.object(REPORT, "command_exists", side_effect=fake_exists), mock.patch.object(
            REPORT, "run_command", side_effect=fake_run
        ):
            self.assertTrue(REPORT.ensure_dialog())
        self.assertTrue(any("update" in command for command in commands))
        self.assertTrue(any("install" in command and "dialog" in command for command in commands))

    def test_ensure_dialog_reports_failure(self):
        with mock.patch.object(REPORT, "command_exists", side_effect=lambda name: name == "apt-get"), mock.patch.object(
            REPORT, "run_command", return_value=("", "could not resolve host", 100)
        ), mock.patch.object(REPORT, "show_error") as show_error:
            self.assertFalse(REPORT.ensure_dialog())
        messages = " ".join(call.args[0] for call in show_error.call_args_list)
        self.assertIn("手动执行", messages)
        self.assertIn("apt-get install -y dialog", messages)


class CounterParsingTests(unittest.TestCase):
    def test_cpu_delta(self):
        before = REPORT.read_cpu_stat("cpu  100 0 50 850 0 0 0 0\n")
        after = REPORT.read_cpu_stat("cpu  150 0 70 880 0 0 0 0\n")
        self.assertEqual(REPORT.cpu_percent(before, after), 70.0)

    def test_process_stat_handles_spaces_in_command(self):
        text = "123 (worker process) R 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15"
        self.assertEqual(REPORT.read_process_cpu(123, text), 23)

    def test_diskstats_parser_and_delta_rate(self):
        text = "8 0 sda 10 0 20 0 30 0 40 0 0 0 0 0 0 0\n"
        parsed = REPORT.read_diskstats(text)
        self.assertEqual(parsed["sda"]["sectors_read"], 20)
        self.assertEqual(parsed["sda"]["sectors_written"], 40)
        self.assertEqual(REPORT.delta_rate(300, 100, 2), 100)

    def test_iostat_json_parser(self):
        payload = json.dumps(
            {
                "sysstat": {
                    "hosts": [
                        {
                            "statistics": [
                                {"disk": [{"disk_device": "sda", "await": 4.5, "aqu-sz": 1.2, "util": 33.0}]}
                            ]
                        }
                    ]
                }
            }
        )
        result = REPORT.parse_iostat_json(payload)
        self.assertEqual(result["sda"]["await_ms"], 4.5)
        self.assertEqual(result["sda"]["util_percent"], 33.0)

    def test_default_network_filter_ignores_container_veth(self):
        with mock.patch.object(REPORT, "interface_type", side_effect=lambda name: "physical" if name == "ens3" else "virtual"):
            self.assertTrue(REPORT.default_interface_allowed("ens3"))
            self.assertTrue(REPORT.default_interface_allowed("eth0"))
            self.assertFalse(REPORT.default_interface_allowed("veth1234"))
            self.assertFalse(REPORT.default_interface_allowed("docker0"))


class DependencyInstallTests(unittest.TestCase):
    def test_present_tool_is_not_installed(self):
        with mock.patch.object(REPORT, "detect_package_manager", return_value="apt"), mock.patch.object(
            REPORT, "privilege_prefix", return_value=([], None)
        ), mock.patch.object(REPORT, "available_tool_command", return_value="iostat"), mock.patch.object(
            REPORT, "run_command"
        ) as run:
            result = REPORT.prepare_dependencies(["disk_io"])
        self.assertEqual(result["tools"][0]["status"], "present")
        run.assert_not_called()

    def test_apt_install_success_rechecks_command(self):
        with mock.patch.object(REPORT, "detect_package_manager", return_value="apt"), mock.patch.object(
            REPORT, "privilege_prefix", return_value=([], None)
        ), mock.patch.object(REPORT, "available_tool_command", side_effect=[None, "iostat"]), mock.patch.object(
            REPORT, "run_command", return_value=("", "", 0)
        ) as run:
            result = REPORT.prepare_dependencies(["disk_io"])
        self.assertEqual(result["tools"][0]["status"], "installed")
        self.assertEqual(len(run.call_args_list), 2)
        self.assertIn("apt-get update", result["install_commands"][0])
        self.assertIn("apt-get install -y sysstat", result["install_commands"][1])

    def test_dnf_install_success(self):
        checks = {"ethtool": 0}

        def available(command, spec):
            if command == "ip":
                return "ip"
            checks["ethtool"] += 1
            return "ethtool" if checks["ethtool"] > 1 else None

        with mock.patch.object(REPORT, "detect_package_manager", return_value="dnf"), mock.patch.object(
            REPORT, "privilege_prefix", return_value=([], None)
        ), mock.patch.object(REPORT, "available_tool_command", side_effect=available), mock.patch.object(
            REPORT, "run_command", return_value=("", "", 0)
        ) as run:
            result = REPORT.prepare_dependencies(["network"])
        ethtool = [item for item in result["tools"] if item["command"] == "ethtool"][0]
        self.assertEqual(ethtool["status"], "installed")
        self.assertTrue(any("dnf install -y" in command for command in result["install_commands"]))
        self.assertEqual(len(run.call_args_list), 1)

    def test_install_failure_includes_manual_command(self):
        with mock.patch.object(REPORT, "detect_package_manager", return_value="apt"), mock.patch.object(
            REPORT, "privilege_prefix", return_value=([], "没有安装权限")
        ), mock.patch.object(REPORT, "available_tool_command", return_value=None):
            result = REPORT.prepare_dependencies(["hardware"])
        tool = result["tools"][0]
        self.assertEqual(result["status"], "failed")
        self.assertEqual(tool["status"], "failed")
        self.assertIn("没有安装权限", tool["error"])
        self.assertIn("apt-get install -y smartmontools", tool["manual_install_command"])

    def test_failed_tool_manual_command_only_contains_its_own_package(self):
        checks = {}

        def available(command, spec):
            checks[command] = checks.get(command, 0) + 1
            if command == "ip":
                return "ip"
            if command == "iostat":
                return None
            return "ethtool" if checks[command] > 1 else None

        with mock.patch.object(REPORT, "detect_package_manager", return_value="apt"), mock.patch.object(
            REPORT, "privilege_prefix", return_value=([], None)
        ), mock.patch.object(REPORT, "available_tool_command", side_effect=available), mock.patch.object(
            REPORT, "run_command", return_value=("", "", 0)
        ):
            result = REPORT.prepare_dependencies(["disk_io", "network"])
        iostat = [item for item in result["tools"] if item["command"] == "iostat"][0]
        ethtool = [item for item in result["tools"] if item["command"] == "ethtool"][0]
        self.assertEqual(ethtool["status"], "installed")
        self.assertEqual(iostat["status"], "failed")
        self.assertIn("install -y sysstat", iostat["manual_install_command"])
        self.assertNotIn("ethtool", iostat["manual_install_command"])

    def test_missing_package_manager_has_generic_manual_hint(self):
        with mock.patch.object(REPORT, "detect_package_manager", return_value=None), mock.patch.object(
            REPORT, "privilege_prefix", return_value=([], None)
        ), mock.patch.object(REPORT, "available_tool_command", return_value=None):
            result = REPORT.prepare_dependencies(["disk_benchmark"])
        self.assertEqual(result["tools"][0]["status"], "failed")
        self.assertIn("软件包管理器安装", result["tools"][0]["manual_install_command"])


class MountAndScanTests(unittest.TestCase):
    def test_findmnt_pair_parser_decodes_paths(self):
        output = 'SOURCE="/dev/sda1" TARGET="/data\\x20disk" FSTYPE="ext4"\n'
        with mock.patch.object(REPORT.shutil, "which", return_value="/usr/bin/findmnt"), mock.patch.object(
            REPORT, "run_command", return_value=(output, "", 0)
        ):
            mounts = REPORT.discover_mounts_findmnt()
        self.assertEqual(mounts[0]["target"], "/data disk")

    def test_remote_special_and_unknown_fuse_classification(self):
        for fstype in ("nfs", "nfs4", "cifs", "smb3", "fuse.sshfs", "ceph", "glusterfs", "fuse.rclone"):
            self.assertEqual(REPORT.classify_filesystem(fstype)[0], "remote", fstype)
        for fstype in ("overlay", "proc", "sysfs", "tmpfs", "nsfs", "bpf", "fusectl", "nfsd"):
            self.assertEqual(REPORT.classify_filesystem(fstype)[0], "special", fstype)
        category, reason = REPORT.classify_filesystem("fuse.example")
        self.assertEqual(category, "remote")
        self.assertIn("保守排除", reason)

    def test_mountinfo_parser(self):
        text = (
            "36 25 8:1 / / rw,relatime - ext4 /dev/sda1 rw\n"
            "40 36 0:45 / /srv/share rw,relatime - nfs4 10.0.0.1:/data rw\n"
        )
        mounts = REPORT.discover_mounts_mountinfo(text)
        self.assertEqual(mounts[0]["category"], "local")
        self.assertEqual(mounts[1]["category"], "remote")

    def test_scan_plan_separates_local_disk_and_skips_remote(self):
        mounts = [
            mount("/dev/sda1", "/", "ext4"),
            mount("/dev/sdb1", "/data", "xfs"),
            mount("10.0.0.1:/backup", "/data/backup", "nfs4"),
            mount("overlay", "/data/container", "overlay"),
        ]
        with mock.patch.object(REPORT.os.path, "exists", return_value=True):
            plan, skipped = REPORT.build_scan_plan(["/"], mounts, [])
        self.assertEqual([item["root"] for item in plan], ["/", "/data"])
        self.assertEqual({item["target"] for item in skipped}, {"/data/backup", "/data/container"})

    def test_directory_ranking_respects_exclude_depth_and_sorting(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "a", "deep"))
            os.makedirs(os.path.join(root, "b"))
            os.makedirs(os.path.join(root, "excluded"))
            pathlib.Path(root, "a", "a.bin").write_bytes(b"a" * 2048)
            pathlib.Path(root, "a", "deep", "deep.bin").write_bytes(b"d" * 1024)
            pathlib.Path(root, "b", "b.bin").write_bytes(b"b" * 512)
            pathlib.Path(root, "excluded", "hidden.bin").write_bytes(b"x" * 8192)
            result = REPORT.scan_directory_tree(root, "/", 2, 5, [os.path.join(root, "excluded")], [])
        paths = [os.path.basename(item["path"]) for item in result["entries"]]
        self.assertEqual(result["status"], "ok")
        self.assertEqual(paths[0], "a")
        self.assertEqual(set(paths[:3]), {"a", "deep", "b"})
        self.assertNotIn("excluded", paths)

    def test_scan_timeout_returns_incomplete(self):
        with tempfile.TemporaryDirectory() as root:
            for index in range(50):
                pathlib.Path(root, f"{index}.txt").write_bytes(b"x")
            result = REPORT.scan_directory_tree(root, "/", 1, 0.000001, [], [])
        self.assertEqual(result["status"], "incomplete")
        self.assertTrue(result["timed_out"])


class AnalysisAndOutputTests(unittest.TestCase):
    def args(self):
        return SimpleNamespace(
            cpu_warn=80.0,
            cpu_crit=90.0,
            mem_warn=80.0,
            mem_crit=90.0,
            disk_warn=80.0,
            disk_crit=90.0,
            inode_warn=80.0,
            inode_crit=90.0,
            io_util_warn=80.0,
            io_util_crit=95.0,
            io_await_warn=20.0,
            io_await_crit=50.0,
        )

    def sample_report(self):
        return {
            "metadata": {
                "hostname": "test-host",
                "os": "Test Linux",
                "kernel": "1.0",
                "cpu_count": 2,
                "started_at": "2026-01-01T00:00:00+08:00",
                "finished_at": "2026-01-01T00:00:10+08:00",
            },
            "selected_modules": ["cpu", "memory"],
            "skipped_modules": {},
            "dependencies": {
                "status": "failed",
                "package_manager": "apt",
                "tools": [
                    {
                        "command": "iostat",
                        "package": "sysstat",
                        "modules": ["disk_io"],
                        "status": "failed",
                        "error": "software source unavailable",
                        "manual_install_command": "apt-get update && apt-get install -y sysstat",
                    }
                ],
            },
            "modules": {
                "cpu": {
                    "status": "ok",
                    "average_percent": 95.0,
                    "peak_percent": 99.0,
                    "sample_seconds": 10,
                    "load": [3.0, 2.0, 1.0],
                    "processes": [],
                },
                "memory": {
                    "status": "unknown",
                    "error": "fixture unavailable",
                },
            },
            "issues": [],
        }

    def test_analysis_uses_thresholds_and_preserves_unknown(self):
        report = self.sample_report()
        issues = REPORT.analyze_report(report, self.args())
        self.assertTrue(any(item["severity"] == "critical" and item["module"] == "cpu" for item in issues))
        self.assertFalse(any(item["module"] == "memory" for item in issues))
        self.assertTrue(all("本次采样期间" in item["message"] for item in issues))

    def test_text_json_html_and_atomic_write_are_consistent(self):
        report = self.sample_report()
        report["issues"] = REPORT.analyze_report(report, self.args())
        text = REPORT.render_text(report)
        html_text = REPORT.render_html(report, text)
        self.assertIn("CPU 使用分析", text)
        self.assertIn("apt-get install -y sysstat", text)
        self.assertIn("服务器资源分析报告", html_text)
        self.assertIn("apt-get install -y sysstat", html_text)
        self.assertIn(str(len(report["issues"])), json.dumps(report, ensure_ascii=False))
        with tempfile.TemporaryDirectory() as directory:
            paths, errors = REPORT.save_reports(report, directory)
            self.assertEqual(errors, {})
            for path in paths.values():
                self.assertTrue(os.path.isfile(path))
            with open(paths["latest_json"], encoding="utf-8") as file:
                loaded = json.load(file)
            self.assertEqual(len(loaded["issues"]), len(report["issues"]))

    def test_report_output_continues_when_one_format_fails(self):
        report = self.sample_report()
        report["issues"] = []
        original = REPORT.atomic_write

        def sometimes_fail(path, content):
            if path.endswith(".html"):
                raise OSError("html denied")
            return original(path, content)

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            REPORT, "atomic_write", side_effect=sometimes_fail
        ):
            paths, errors = REPORT.save_reports(report, directory)
        self.assertIn("txt", paths)
        self.assertIn("json", paths)
        self.assertEqual(errors["html"], "html denied")

    def test_output_directory_falls_back(self):
        with mock.patch.object(REPORT.os, "makedirs", side_effect=[OSError("denied"), None]), mock.patch.object(
            REPORT.tempfile, "mkstemp", return_value=(99, "/tmp/probe")
        ), mock.patch.object(REPORT.os, "close"), mock.patch.object(REPORT.os, "remove"):
            path, reason = REPORT.ensure_output_dir("/not-writable")
        self.assertEqual(path, REPORT.FALLBACK_OUTPUT_DIR)
        self.assertIn("不可写", reason)

    def test_disk_test_directory_rejects_remote_mount(self):
        mounts = [mount("10.0.0.1:/data", "/mnt/remote", "nfs4")]
        with mock.patch.object(REPORT.os.path, "isdir", return_value=True), mock.patch.object(
            REPORT.os, "access", return_value=True
        ):
            ok, reason, _ = REPORT.validate_disk_test_dir("/mnt/remote/test", mounts, [], 1024)
        self.assertFalse(ok)
        self.assertIn("远程", reason)

    def test_disk_benchmark_interrupt_cleans_temporary_file(self):
        args = SimpleNamespace(
            disk_test_size="1M",
            disk_test_dir="/tmp",
            disk_test_seconds=1,
            exclude_path=[],
        )
        mounts = [mount("/dev/sda1", "/", "ext4")]
        with mock.patch.object(REPORT.shutil, "which", return_value="/usr/bin/fio"), mock.patch.object(
            REPORT, "validate_disk_test_dir", return_value=(True, "ok", mounts[0])
        ), mock.patch.object(REPORT.tempfile, "mkstemp", return_value=(99, "/tmp/jh-resource-fio-test")), mock.patch.object(
            REPORT.os, "close"
        ), mock.patch.object(REPORT, "run_command", side_effect=KeyboardInterrupt), mock.patch.object(
            REPORT.os, "remove"
        ) as remove:
            result = REPORT.run_disk_benchmark(args, mounts)
        self.assertEqual(result["status"], "skipped")
        self.assertIn("用户中断", result["error"])
        remove.assert_called_once_with("/tmp/jh-resource-fio-test")

    def test_module_failure_is_isolated(self):
        args = SimpleNamespace(
            interfaces=None,
            sample_seconds=0.01,
            sample_interval=0.01,
            top=1,
            scan_root=["/tmp"],
            exclude_path=[],
            scan_depth=1,
            scan_timeout=1,
        )
        system = {
            "hostname": "test",
            "os": "test",
            "kernel": "test",
            "cpu_count": 1,
            "memory_total": 1,
        }
        with mock.patch.object(REPORT, "collect_system", return_value=system), mock.patch.object(
            REPORT, "discover_mounts", return_value=[]
        ), mock.patch.object(REPORT, "sample_resources", return_value={}), mock.patch.object(
            REPORT, "collect_module", side_effect=[RuntimeError("boom"), {"status": "ok"}]
        ), mock.patch.object(REPORT, "analyze_report", return_value=[]):
            report = REPORT.build_report(args, ["system", "memory"], {}, {"status": "ok", "tools": []})
        self.assertEqual(report["modules"]["system"]["status"], "failed")
        self.assertEqual(report["modules"]["memory"]["status"], "ok")


class SummaryTests(unittest.TestCase):
    def report(self, **overrides):
        report = {
            "metadata": {
                "hostname": "test-host",
                "output_dir": "/tmp/report",
                "output_fallback_reason": None,
            },
            "selected_modules": ["system", "cpu", "memory", "disk_space"],
            "skipped_modules": {},
            "dependencies": {"status": "ok", "package_manager": "apt", "tools": []},
            "modules": {
                "system": {"status": "ok"},
                "cpu": {"status": "ok"},
                "memory": {"status": "ok"},
                "disk_space": {"status": "ok", "scan_tasks": []},
            },
            "issues": [],
        }
        report.update(overrides)
        return report

    def test_healthy_report_uses_positive_conclusion(self):
        summary = REPORT.build_summary(self.report())
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["items"], [])
        self.assertEqual(summary["conclusion"], "服务运行正常，继续保持！")

    def test_threshold_issues_become_summary_items(self):
        issues = [
            {
                "severity": "critical",
                "module": "cpu",
                "metric": "CPU 平均使用率",
                "value": "96.72%",
                "basis": "警告 80.0% / 严重 90.0%",
                "window": "3.0 秒",
                "message": "message",
                "suggestion": "suggestion",
            },
            {
                "severity": "info",
                "module": "cpu",
                "metric": "提示项",
                "value": 1,
                "basis": "basis",
                "window": "window",
                "message": "message",
                "suggestion": "suggestion",
            },
        ]
        summary = REPORT.build_summary(self.report(issues=issues))
        self.assertEqual(summary["status"], "risk")
        self.assertEqual(len(summary["items"]), 1)
        self.assertIn("CPU 使用分析：CPU 平均使用率 96.72%", summary["items"][0]["text"])
        self.assertIn("依据：警告 80.0% / 严重 90.0%", summary["items"][0]["text"])
        self.assertIsNone(summary["conclusion"])
        self.assertEqual(summary["counts"], {"critical": 1, "warning": 0, "info": 0})

    def test_collection_anomalies_are_listed_and_sorted_by_severity(self):
        report = self.report()
        report["modules"]["system"] = {"status": "failed", "error": "boom"}
        report["modules"]["memory"] = {"status": "skipped", "error": "用户中断该模块"}
        report["modules"]["disk_space"] = {
            "status": "ok",
            "scan_tasks": [{"root": "/www", "status": "incomplete", "duration_seconds": 12.0}],
        }
        report["dependencies"] = {
            "status": "failed",
            "tools": [
                {
                    "command": "iostat",
                    "package": "sysstat",
                    "status": "failed",
                    "manual_install_command": "apt-get update && apt-get install -y sysstat",
                }
            ],
        }
        report["metadata"]["output_fallback_reason"] = "默认输出目录 /www/server/log 不可写"
        summary = REPORT.build_summary(report)
        severities = [item["severity"] for item in summary["items"]]
        self.assertEqual(severities, sorted(severities, key=lambda value: REPORT.SEVERITY_ORDER[value]))
        texts = " ".join(item["text"] for item in summary["items"])
        self.assertIn("系统概要：采集失败（boom）", texts)
        self.assertIn("目录扫描未完成：/www", texts)
        self.assertIn("依赖工具 iostat（sysstat）安装后仍不可用", texts)
        self.assertIn("内存使用分析：未执行", texts)
        self.assertIn("报告输出目录已回退到", texts)
        self.assertEqual(summary["counts"], {"critical": 1, "warning": 2, "info": 2})

    def test_text_and_html_render_summary_block(self):
        report = self.report()
        report["modules"]["cpu"] = {"status": "failed", "error": "boom"}
        report["summary"] = REPORT.build_summary(report)
        text = REPORT.render_text(report)
        html_text = REPORT.render_html(report, text)
        self.assertIn("【概要信息】", text)
        self.assertIn("- 【严重】CPU 使用分析：采集失败（boom）", text)
        self.assertIn("概要信息", html_text)
        self.assertIn("class='critical'", html_text)
        healthy = self.report()
        healthy_text = REPORT.render_text(healthy)
        self.assertIn("服务运行正常，继续保持！", healthy_text)
        self.assertIn("class='ok'", REPORT.render_html(healthy, healthy_text))

    def test_main_attaches_summary_to_report(self):
        captured = {}
        report = self.report()

        def fake_save(report_data, output_dir):
            captured["report"] = report_data
            return {"txt": "/tmp/report.txt"}, {}

        with mock.patch.object(REPORT, "build_report", return_value=report), mock.patch.object(
            REPORT, "prepare_dependencies", return_value={"status": "ok", "tools": []}
        ), mock.patch.object(REPORT, "ensure_output_dir", return_value=("/tmp/report", None)), mock.patch.object(
            REPORT, "save_reports", side_effect=fake_save
        ), mock.patch.object(REPORT, "print_execution_summary"), mock.patch.object(
            REPORT, "print_dependency_summary"
        ), mock.patch.object(REPORT, "print_final_summary"):
            code = REPORT.main(["--non-interactive", "--modules", "cpu"])
        self.assertEqual(code, 0)
        self.assertIn("summary", captured["report"])


if __name__ == "__main__":
    unittest.main()
