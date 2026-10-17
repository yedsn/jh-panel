#!/usr/bin/env python3
"""生成一次性的 Linux 服务器资源分析报告。

默认只执行低风险、只读的资源采集。磁盘性能测试和外网测速必须显式
选择并确认，非交互模式还需要对应的 --allow-* 参数。
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import math
import os
import pathlib
import pwd
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Sequence, Tuple


DEFAULT_OUTPUT_DIR = "/www/server/log/server_resource_report"
FALLBACK_OUTPUT_DIR = "/tmp/server_resource_report"

MODULES = OrderedDict(
    [
        ("1", ("system", "系统概要", False)),
        ("2", ("cpu", "CPU 使用分析", False)),
        ("3", ("memory", "内存使用分析", False)),
        ("4", ("disk_space", "磁盘容量和目录占用排行", False)),
        ("5", ("disk_io", "磁盘实时读写分析", False)),
        ("6", ("network", "网络流量和网卡状态", False)),
        ("7", ("hardware", "基础硬件健康信息", False)),
        ("8", ("disk_benchmark", "磁盘性能测试（主动负载）", True)),
        ("9", ("speedtest", "外网速度测试（主动负载）", True)),
    ]
)
DEFAULT_MODULE_KEYS = ["system", "cpu", "memory", "disk_space"]
MODULE_BY_KEY = {value[0]: (number, value[1], value[2]) for number, value in MODULES.items()}

SEVERITY_LABELS = OrderedDict([("critical", "严重"), ("warning", "警告"), ("info", "提示")])
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

DIALOG_PACKAGE = "dialog"


class SelectionCancelled(Exception):
    """用户在交互式模块选择界面取消。"""


TOOL_SPECS = OrderedDict(
    [
        ("findmnt", {"modules": {"disk_space", "disk_benchmark"}, "apt": "util-linux", "dnf": "util-linux", "yum": "util-linux"}),
        ("du", {"modules": {"disk_space"}, "apt": "coreutils", "dnf": "coreutils", "yum": "coreutils"}),
        ("iostat", {"modules": {"disk_io"}, "apt": "sysstat", "dnf": "sysstat", "yum": "sysstat"}),
        ("ip", {"modules": {"network"}, "apt": "iproute2", "dnf": "iproute", "yum": "iproute"}),
        ("ethtool", {"modules": {"network"}, "apt": "ethtool", "dnf": "ethtool", "yum": "ethtool"}),
        ("smartctl", {"modules": {"hardware"}, "apt": "smartmontools", "dnf": "smartmontools", "yum": "smartmontools"}),
        ("fio", {"modules": {"disk_benchmark"}, "apt": "fio", "dnf": "fio", "yum": "fio"}),
        ("speedtest-cli", {"modules": {"speedtest"}, "alternatives": ["speedtest", "speedtest-cli"], "apt": "speedtest-cli", "dnf": "speedtest-cli", "yum": "speedtest-cli"}),
    ]
)

REMOTE_FS_TYPES = {
    "nfs",
    "nfs4",
    "cifs",
    "smb3",
    "sshfs",
    "fuse.sshfs",
    "ceph",
    "fuse.ceph",
    "glusterfs",
    "fuse.glusterfs",
    "fuse.rclone",
    "9p",
    "davfs",
    "fuse.davfs",
}
SPECIAL_FS_TYPES = {
    "proc",
    "sysfs",
    "devtmpfs",
    "devpts",
    "tmpfs",
    "overlay",
    "aufs",
    "squashfs",
    "nsfs",
    "tracefs",
    "debugfs",
    "securityfs",
    "pstore",
    "efivarfs",
    "configfs",
    "cgroup",
    "cgroup2",
    "mqueue",
    "hugetlbfs",
    "rpc_pipefs",
    "nfsd",
    "autofs",
    "binfmt_misc",
    "bpf",
    "fusectl",
    "ramfs",
}
SKIP_BLOCK_PREFIXES = ("loop", "ram", "fd", "sr")


def show_info(message: str = "") -> None:
    print(message)


def show_error(message: str) -> None:
    print(message, file=sys.stderr)


def prompt(message: str, default: str = "") -> str:
    try:
        value = input(message).strip()
    except (EOFError, KeyboardInterrupt):
        return default
    return value or default


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def format_bytes(value: float) -> str:
    size = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if size < 1024 or unit == "PB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def parse_size(value: str) -> int:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMGTP]?)(?:i?B)?\s*", value, re.I)
    if not match:
        raise ValueError(f"无法识别大小: {value}")
    number = float(match.group(1))
    power = " KMGTP".index(match.group(2).upper())
    return int(number * (1024**power))


def normalize_path(path: str) -> str:
    return os.path.abspath(os.path.realpath(os.path.expanduser(path)))


def path_is_within(path: str, parent: str) -> bool:
    try:
        return os.path.commonpath([normalize_path(path), normalize_path(parent)]) == normalize_path(parent)
    except ValueError:
        return False


def read_text(path: str, default: str = "") -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as file:
            return file.read()
    except OSError:
        return default


def run_command(
    command: Sequence[str], timeout: float = 15, cwd: Optional[str] = None
) -> Tuple[str, str, int]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return stdout, stderr or f"命令执行超时（{timeout}s）", 124
    except OSError as exc:
        return "", str(exc), 127


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def available_tool_command(command: str, spec: Dict[str, Any]) -> Optional[str]:
    for candidate in spec.get("alternatives", [command]):
        if command_exists(candidate):
            return candidate
    return None


def selected_tool_specs(selected: Sequence[str]) -> OrderedDict:
    selected_set = set(selected)
    return OrderedDict(
        (command, spec)
        for command, spec in TOOL_SPECS.items()
        if selected_set.intersection(spec["modules"])
    )


def package_for_spec(command: str, spec: Dict[str, Any], manager: Optional[str]) -> str:
    if manager:
        return spec.get(manager, command)
    return spec.get("apt") or spec.get("dnf") or spec.get("yum") or command


def detect_package_manager() -> Optional[str]:
    for manager in ("apt-get", "dnf", "yum"):
        if command_exists(manager):
            return {"apt-get": "apt", "dnf": "dnf", "yum": "yum"}[manager]
    return None


def package_manager_binary(manager: str) -> str:
    return {"apt": "apt-get", "dnf": "dnf", "yum": "yum"}[manager]


def privilege_prefix() -> Tuple[List[str], Optional[str]]:
    if os.geteuid() == 0:
        return [], None
    if command_exists("sudo"):
        return ["sudo", "-n"], None
    return [], "当前用户不是 root，且未安装 sudo"


def manual_install_command(manager: Optional[str], packages: Sequence[str]) -> str:
    package_text = " ".join(sorted(set(packages)))
    if os.geteuid() == 0:
        prefix = ""
    elif command_exists("sudo"):
        prefix = "sudo "
    else:
        prefix = "以 root 用户执行: "
    if manager == "apt":
        return f"{prefix}apt-get update && {prefix}apt-get install -y {package_text}"
    if manager in ("dnf", "yum"):
        return f"{prefix}{package_manager_binary(manager)} install -y {package_text}"
    return f"请使用当前系统的软件包管理器安装: {package_text}"


def summarize_install_error(stdout: str, stderr: str, code: int) -> str:
    content = (stderr.strip() or stdout.strip() or f"安装命令退出码 {code}").strip()
    if len(content) > 2000:
        content = content[-2000:]
    return content


def prepare_dependencies(selected: Sequence[str]) -> Dict[str, Any]:
    specs = selected_tool_specs(selected)
    manager = detect_package_manager()
    prefix, privilege_error = privilege_prefix()
    tool_results: List[Dict[str, Any]] = []
    missing: List[Tuple[str, Dict[str, Any]]] = []

    for command, spec in specs.items():
        package = package_for_spec(command, spec, manager)
        available_command = available_tool_command(command, spec)
        item = {
            "command": command,
            "available_command": available_command,
            "package": package,
            "modules": sorted(spec["modules"].intersection(selected)),
            "status": "present" if available_command else "pending",
            "manual_install_command": manual_install_command(manager, [package]),
            "error": None,
        }
        tool_results.append(item)
        if item["status"] == "pending":
            missing.append((command, spec))

    result = {
        "status": "ok",
        "package_manager": manager or "unknown",
        "tools": tool_results,
        "install_commands": [],
        "errors": [],
    }
    if not missing:
        return result

    packages = sorted({package_for_spec(command, spec, manager) for command, spec in missing})
    manual_command = manual_install_command(manager, packages)
    result["manual_install_command"] = manual_command
    if manager is None:
        error = "未检测到 apt-get、dnf 或 yum"
    elif privilege_error:
        error = privilege_error
    else:
        binary = package_manager_binary(manager)
        install_errors: List[str] = []
        if manager == "apt":
            update_command = prefix + ["env", "DEBIAN_FRONTEND=noninteractive", binary, "update"]
            result["install_commands"].append(" ".join(update_command))
            show_info("|- 正在刷新软件源索引...")
            stdout, stderr, code = run_command(update_command, timeout=300)
            if code != 0:
                install_errors.append("软件源刷新失败: " + summarize_install_error(stdout, stderr, code))
        if manager == "apt":
            install_command = prefix + ["env", "DEBIAN_FRONTEND=noninteractive", binary, "install", "-y"] + packages
        else:
            install_command = prefix + [binary, "install", "-y"] + packages
        result["install_commands"].append(" ".join(install_command))
        show_info("|- 正在自动安装依赖：" + ", ".join(packages))
        stdout, stderr, code = run_command(install_command, timeout=600)
        if code != 0:
            install_errors.append("软件包安装失败: " + summarize_install_error(stdout, stderr, code))
            if manager == "apt":
                retry_command = prefix + [
                    "env",
                    "DEBIAN_FRONTEND=noninteractive",
                    binary,
                    "install",
                    "-y",
                    "--fix-missing",
                ] + packages
                result["install_commands"].append(" ".join(retry_command))
                show_info("|- 首次安装失败，正在使用 --fix-missing 重试...")
                retry_stdout, retry_stderr, retry_code = run_command(retry_command, timeout=600)
                if retry_code != 0:
                    install_errors.append(
                        "软件包重试失败: "
                        + summarize_install_error(retry_stdout, retry_stderr, retry_code)
                    )
        error = "；".join(install_errors) if install_errors else None

    if error:
        result["errors"].append(error)

    failed_count = 0
    for item in tool_results:
        if item["status"] != "pending":
            continue
        spec = specs[item["command"]]
        available_command = available_tool_command(item["command"], spec)
        if available_command:
            item["status"] = "installed"
            item["available_command"] = available_command
            show_info(f"|- {item['command']} 安装完成✅")
        else:
            failed_count += 1
            item["status"] = "failed"
            error_text = error or "安装结束后命令仍不可执行"
            item["error"] = error_text if len(error_text) <= 2000 else error_text[-2000:]
            item["manual_install_command"] = manual_install_command(manager, [item["package"]])
            show_error(
                f"|- {item['command']} 自动安装失败，请手动执行：{item['manual_install_command']}"
            )
    if failed_count:
        result["status"] = "partial" if failed_count < len(missing) else "failed"
        if not error:
            result["errors"].append("部分工具安装后仍不可执行")
    return result


def parse_modules(value: Optional[str]) -> List[str]:
    if value is None or not value.strip():
        return list(DEFAULT_MODULE_KEYS)
    tokens = [token.strip().lower() for token in value.split(",") if token.strip()]
    if not tokens:
        return list(DEFAULT_MODULE_KEYS)
    if "all" in tokens:
        return [item[0] for item in MODULES.values()]
    selected: List[str] = []
    invalid: List[str] = []
    for token in tokens:
        if token in MODULES:
            key = MODULES[token][0]
        elif token in MODULE_BY_KEY:
            key = token
        else:
            invalid.append(token)
            continue
        if key not in selected:
            selected.append(key)
    if invalid:
        raise ValueError(f"无效模块: {', '.join(invalid)}")
    return selected


def ensure_dialog() -> bool:
    if command_exists("dialog"):
        return True
    show_info("|- 未检测到 dialog，正在尝试自动安装...")
    manager = detect_package_manager()
    prefix, privilege_error = privilege_prefix()
    manual = manual_install_command(manager, [DIALOG_PACKAGE])
    if manager is None or privilege_error:
        show_error(f"dialog 自动安装失败，请手动执行：{manual}")
        return False
    binary = package_manager_binary(manager)
    if manager == "apt":
        show_info("|- 正在刷新软件源索引...")
        run_command(prefix + ["env", "DEBIAN_FRONTEND=noninteractive", binary, "update"], timeout=300)
        install_command = prefix + [
            "env",
            "DEBIAN_FRONTEND=noninteractive",
            binary,
            "install",
            "-y",
            DIALOG_PACKAGE,
        ]
    else:
        install_command = prefix + [binary, "install", "-y", DIALOG_PACKAGE]
    show_info(f"|- 正在自动安装：{DIALOG_PACKAGE}")
    stdout, stderr, code = run_command(install_command, timeout=600)
    if code != 0 or not command_exists("dialog"):
        show_error("dialog 自动安装失败：" + summarize_install_error(stdout, stderr, code))
        show_error(f"请手动执行：{manual}")
        return False
    show_info("|- dialog 安装完成✅")
    return True


def build_dialog_checklist_command() -> List[str]:
    options: List[str] = []
    for number, (key, label, active) in MODULES.items():
        state = "on" if key in DEFAULT_MODULE_KEYS else "off"
        suffix = "（主动负载）" if active else ""
        options.extend([number, f"{label}{suffix}", state])
    return [
        "dialog",
        "--stdout",
        "--separate-output",
        "--title",
        "服务器资源分析报告",
        "--checklist",
        "请选择要生成的报告模块（空格勾选/取消，回车确认）：",
        str(len(MODULES) + 10),
        "78",
        str(len(MODULES)),
    ] + options


def run_dialog(command: Sequence[str]) -> Tuple[int, str]:
    try:
        tty_fd = os.open("/dev/tty", os.O_RDWR)
    except OSError:
        return 255, ""
    try:
        completed = subprocess.run(
            list(command),
            stdin=tty_fd,
            stdout=subprocess.PIPE,
            stderr=tty_fd,
            text=True,
            check=False,
        )
        return completed.returncode, completed.stdout
    except OSError:
        return 255, ""
    finally:
        os.close(tty_fd)


def dialog_module_selection() -> Optional[List[str]]:
    """对话框不可用时返回 None；用户点取消时抛出 SelectionCancelled。"""
    command = build_dialog_checklist_command()
    while True:
        code, output = run_dialog(command)
        if code == 1:
            raise SelectionCancelled()
        if code != 0:
            show_error(f"对话框运行失败（退出码 {code}），改为文本选择。")
            return None
        chosen = {line.strip() for line in output.splitlines() if line.strip()}
        selected = [MODULES[number][0] for number in MODULES if number in chosen]
        if selected:
            return selected
        show_info("|- 未勾选任何模块，请至少选择一项。")


def text_module_selection() -> List[str]:
    show_info("请选择要生成的报告模块（多个编号用逗号分隔）：")
    for number, (key, label, active) in MODULES.items():
        default_mark = "x" if key in DEFAULT_MODULE_KEYS else " "
        risk = "，会主动产生负载" if active else ""
        show_info(f"[{default_mark}] {number}. {label}{risk}")
    show_info("直接回车使用默认项；输入 all 选择全部。")
    default = ",".join(number for number, (key, _, _) in MODULES.items() if key in DEFAULT_MODULE_KEYS)
    while True:
        raw = prompt(f"请输入模块编号（默认{default}）：", default)
        try:
            return parse_modules(raw)
        except ValueError as exc:
            show_error(f"输入错误：{exc}")


def interactive_module_selection() -> List[str]:
    show_info("================服务器资源分析报告================")
    if ensure_dialog():
        selected = dialog_module_selection()
        if selected is not None:
            return selected
    show_info("使用文本方式选择模块。")
    return text_module_selection()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 Linux 服务器资源分析报告")
    parser.add_argument("--modules", help="模块编号或名称，多个用逗号分隔；all 表示全部；默认 CPU 和内存")
    parser.add_argument(
        "--non-interactive", action="store_true", help="禁用交互提示，使用 --modules 或默认模块（CPU、内存）"
    )
    parser.add_argument("--sample-seconds", type=float, default=10.0, help="采样总时长，默认10秒")
    parser.add_argument("--sample-interval", type=float, default=1.0, help="采样间隔，默认1秒")
    parser.add_argument("--top", type=int, default=20, help="排行数量，默认20")
    parser.add_argument("--scan-root", action="append", help="目录扫描根，可重复指定，默认/www")
    parser.add_argument("--scan-depth", type=int, default=2, help="目录排行最大深度，默认2")
    parser.add_argument("--scan-timeout", type=float, default=120.0, help="每个扫描任务超时秒数")
    parser.add_argument("--exclude-path", action="append", default=[], help="额外排除路径，可重复指定")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="报告输出目录")
    parser.add_argument("--interfaces", help="网卡名称，多个用逗号分隔")
    parser.add_argument("--allow-disk-benchmark", action="store_true", help="非交互模式允许磁盘性能测试")
    parser.add_argument("--allow-speedtest", action="store_true", help="非交互模式允许外网测速")
    parser.add_argument("--disk-test-dir", default="/tmp", help="fio 测试目录，默认/tmp")
    parser.add_argument("--disk-test-seconds", type=int, default=10, help="fio 测试时长，默认10秒")
    parser.add_argument("--disk-test-size", default="256M", help="fio 测试文件大小，默认256M")
    parser.add_argument("--cpu-warn", type=float, default=80.0)
    parser.add_argument("--cpu-crit", type=float, default=90.0)
    parser.add_argument("--mem-warn", type=float, default=80.0)
    parser.add_argument("--mem-crit", type=float, default=90.0)
    parser.add_argument("--disk-warn", type=float, default=80.0)
    parser.add_argument("--disk-crit", type=float, default=90.0)
    parser.add_argument("--inode-warn", type=float, default=80.0)
    parser.add_argument("--inode-crit", type=float, default=90.0)
    parser.add_argument("--io-util-warn", type=float, default=80.0)
    parser.add_argument("--io-util-crit", type=float, default=95.0)
    parser.add_argument("--io-await-warn", type=float, default=20.0)
    parser.add_argument("--io-await-crit", type=float, default=50.0)
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.sample_seconds <= 0:
        raise ValueError("采样总时长必须大于0")
    if args.sample_interval <= 0:
        raise ValueError("采样间隔必须大于0")
    if args.top <= 0:
        raise ValueError("排行数量必须大于0")
    if args.scan_depth < 1:
        raise ValueError("扫描深度必须至少为1")
    if args.scan_timeout <= 0:
        raise ValueError("扫描超时必须大于0")
    if args.disk_test_seconds <= 0:
        raise ValueError("磁盘测试时长必须大于0")
    for label, warn, critical in (
        ("CPU", args.cpu_warn, args.cpu_crit),
        ("内存", args.mem_warn, args.mem_crit),
        ("磁盘容量", args.disk_warn, args.disk_crit),
        ("inode", args.inode_warn, args.inode_crit),
        ("磁盘利用率", args.io_util_warn, args.io_util_crit),
        ("I/O 等待", args.io_await_warn, args.io_await_crit),
    ):
        if warn < 0 or critical < 0 or warn > critical:
            raise ValueError(f"{label}阈值必须满足 0 ≤ 警告阈值 ≤ 严重阈值")
    parse_size(args.disk_test_size)


def resolve_active_modules(
    selected: Sequence[str], interactive: bool, allow_disk: bool, allow_speed: bool
) -> Tuple[List[str], Dict[str, str]]:
    runnable = list(selected)
    skipped: Dict[str, str] = {}
    checks = [
        ("disk_benchmark", allow_disk, "磁盘性能测试会在目标目录写入临时文件并产生磁盘负载"),
        ("speedtest", allow_speed, "外网测速会占用服务器公网带宽"),
    ]
    for key, allowed, warning in checks:
        if key not in runnable:
            continue
        if interactive:
            show_info("")
            show_info(f"[风险提示] {warning}。")
            confirmed = prompt("确认执行吗？（默认n）[y/n]：", "n").lower() in ("y", "yes", "是")
        else:
            confirmed = allowed
        if not confirmed:
            runnable.remove(key)
            skipped[key] = "未获得主动测试明确确认"
    return runnable, skipped


def load_os_release() -> str:
    values: Dict[str, str] = {}
    for line in read_text("/etc/os-release").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('\"')
    return values.get("PRETTY_NAME") or values.get("NAME") or "unknown"


def read_meminfo() -> Dict[str, int]:
    result: Dict[str, int] = {}
    for line in read_text("/proc/meminfo").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        match = re.search(r"(\d+)", value)
        if match:
            result[key] = int(match.group(1)) * 1024
    return result


def collect_system() -> Dict[str, Any]:
    mem = read_meminfo()
    virtualization = "unknown"
    if shutil.which("systemd-detect-virt"):
        stdout, _, code = run_command(["systemd-detect-virt"], timeout=3)
        if code == 0 and stdout.strip():
            virtualization = stdout.strip()
        elif code == 1:
            virtualization = "none"
    uptime_seconds = safe_float(read_text("/proc/uptime").split()[0] if read_text("/proc/uptime").split() else 0)
    return {
        "status": "ok",
        "hostname": socket.gethostname() or "unknown",
        "os": load_os_release(),
        "kernel": os.uname().release if hasattr(os, "uname") else "unknown",
        "architecture": os.uname().machine if hasattr(os, "uname") else "unknown",
        "uptime_seconds": uptime_seconds,
        "cpu_count": os.cpu_count() or 0,
        "memory_total": mem.get("MemTotal", 0),
        "virtualization": virtualization,
    }


def read_cpu_stat(text: Optional[str] = None) -> Optional[Dict[str, int]]:
    content = text if text is not None else read_text("/proc/stat")
    first = content.splitlines()[0].split() if content else []
    if not first or first[0] != "cpu" or len(first) < 5:
        return None
    values = [safe_int(value) for value in first[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return {"total": sum(values), "idle": idle}


def cpu_percent(previous: Dict[str, int], current: Dict[str, int]) -> float:
    total_delta = current["total"] - previous["total"]
    idle_delta = current["idle"] - previous["idle"]
    if total_delta <= 0:
        return 0.0
    return round(max(0.0, min(100.0, (total_delta - idle_delta) * 100.0 / total_delta)), 2)


def process_identity(pid: int) -> Tuple[str, str]:
    command = read_text(f"/proc/{pid}/cmdline").replace("\x00", " ").strip()
    if not command:
        command = read_text(f"/proc/{pid}/comm").strip() or "unknown"
    try:
        user = pwd.getpwuid(os.stat(f"/proc/{pid}").st_uid).pw_name
    except (KeyError, OSError):
        user = "unknown"
    return user, command


def read_process_cpu(pid: int, text: Optional[str] = None) -> Optional[int]:
    content = text if text is not None else read_text(f"/proc/{pid}/stat")
    if not content:
        return None
    end = content.rfind(")")
    if end < 0:
        return None
    fields = content[end + 2 :].split()
    if len(fields) < 13:
        return None
    return safe_int(fields[11]) + safe_int(fields[12])


def read_all_process_cpu() -> Tuple[Dict[int, Dict[str, Any]], int]:
    result: Dict[int, Dict[str, Any]] = {}
    denied = 0
    try:
        entries = os.listdir("/proc")
    except OSError:
        return result, denied
    for entry in entries:
        if not entry.isdigit():
            continue
        pid = int(entry)
        ticks = read_process_cpu(pid)
        if ticks is None:
            denied += 1
            continue
        user, command = process_identity(pid)
        result[pid] = {"ticks": ticks, "user": user, "command": command}
    return result, denied


def read_diskstats(text: Optional[str] = None) -> Dict[str, Dict[str, int]]:
    content = text if text is not None else read_text("/proc/diskstats")
    result: Dict[str, Dict[str, int]] = {}
    for line in content.splitlines():
        parts = line.split()
        if len(parts) < 14:
            continue
        name = parts[2]
        if name.startswith(SKIP_BLOCK_PREFIXES):
            continue
        sys_path = f"/sys/class/block/{name}"
        if text is None and (not os.path.exists(sys_path) or os.path.exists(os.path.join(sys_path, "partition"))):
            continue
        result[name] = {
            "reads": safe_int(parts[3]),
            "sectors_read": safe_int(parts[5]),
            "writes": safe_int(parts[7]),
            "sectors_written": safe_int(parts[9]),
        }
    return result


NET_COUNTER_NAMES = ("rx_bytes", "tx_bytes", "rx_errors", "tx_errors", "rx_dropped", "tx_dropped")


def interface_type(name: str) -> str:
    base = f"/sys/class/net/{name}"
    if os.path.isdir(os.path.join(base, "bonding")):
        return "bond"
    if os.path.isdir(os.path.join(base, "bridge")):
        return "bridge"
    if os.path.exists(os.path.join(base, "device")):
        return "physical"
    return "virtual"


def default_interface_allowed(name: str) -> bool:
    kind = interface_type(name)
    if kind in ("physical", "bond", "bridge"):
        return True
    return name.startswith(("eth", "enp", "eno", "ens", "em", "wlan", "wlp"))


def read_net_stats(interfaces: Optional[Sequence[str]] = None) -> Dict[str, Dict[str, int]]:
    base = pathlib.Path("/sys/class/net")
    if not base.exists():
        return {}
    allowed = set(interfaces or [])
    result: Dict[str, Dict[str, int]] = {}
    for item in base.iterdir():
        name = item.name
        if name == "lo" or (allowed and name not in allowed):
            continue
        if not allowed and not default_interface_allowed(name):
            continue
        counters: Dict[str, int] = {}
        for counter in NET_COUNTER_NAMES:
            counters[counter] = safe_int(read_text(str(item / "statistics" / counter)).strip())
        result[name] = counters
    return result


def delta_rate(current: int, previous: int, elapsed: float) -> float:
    return max(0, current - previous) / max(elapsed, 0.001)


def sample_resources(
    selected: Sequence[str], seconds: float, interval: float, interfaces: Optional[Sequence[str]], top_n: int
) -> Dict[str, Dict[str, Any]]:
    need_cpu = "cpu" in selected
    need_disk = "disk_io" in selected
    need_network = "network" in selected
    if not (need_cpu or need_disk or need_network):
        return {}

    ticks_per_second = safe_int(os.sysconf("SC_CLK_TCK"), 100)
    previous_time = time.monotonic()
    previous_cpu = read_cpu_stat() if need_cpu else None
    previous_processes, denied = read_all_process_cpu() if need_cpu else ({}, 0)
    previous_disk = read_diskstats() if need_disk else {}
    previous_net = read_net_stats(interfaces) if need_network else {}

    cpu_samples: List[float] = []
    process_samples: Dict[int, Dict[str, Any]] = {}
    disk_samples: Dict[str, List[Dict[str, float]]] = {}
    net_samples: Dict[str, List[Dict[str, float]]] = {}
    iterations = max(1, int(math.ceil(seconds / interval)))

    for index in range(iterations):
        remaining = seconds - (time.monotonic() - previous_time if index == 0 else index * interval)
        time.sleep(max(0.01, min(interval, remaining if remaining > 0 else interval)))
        current_time = time.monotonic()
        elapsed = max(0.001, current_time - previous_time)

        if need_cpu:
            current_cpu = read_cpu_stat()
            current_processes, denied_now = read_all_process_cpu()
            denied = max(denied, denied_now)
            if previous_cpu and current_cpu:
                cpu_samples.append(cpu_percent(previous_cpu, current_cpu))
            for pid, current in current_processes.items():
                previous = previous_processes.get(pid)
                if not previous:
                    continue
                percent = max(0.0, (current["ticks"] - previous["ticks"]) * 100.0 / ticks_per_second / elapsed)
                item = process_samples.setdefault(
                    pid,
                    {"pid": pid, "user": current["user"], "command": current["command"], "samples": []},
                )
                item["samples"].append(percent)
            previous_cpu = current_cpu
            previous_processes = current_processes

        if need_disk:
            current_disk = read_diskstats()
            for name, current in current_disk.items():
                previous = previous_disk.get(name)
                if not previous:
                    continue
                sample = {
                    "read_bps": delta_rate(current["sectors_read"] * 512, previous["sectors_read"] * 512, elapsed),
                    "write_bps": delta_rate(current["sectors_written"] * 512, previous["sectors_written"] * 512, elapsed),
                    "read_iops": delta_rate(current["reads"], previous["reads"], elapsed),
                    "write_iops": delta_rate(current["writes"], previous["writes"], elapsed),
                }
                disk_samples.setdefault(name, []).append(sample)
            previous_disk = current_disk

        if need_network:
            current_net = read_net_stats(interfaces)
            for name, current in current_net.items():
                previous = previous_net.get(name)
                if not previous:
                    continue
                sample = {
                    "rx_bps": delta_rate(current["rx_bytes"], previous["rx_bytes"], elapsed),
                    "tx_bps": delta_rate(current["tx_bytes"], previous["tx_bytes"], elapsed),
                    "rx_errors": max(0, current["rx_errors"] - previous["rx_errors"]),
                    "tx_errors": max(0, current["tx_errors"] - previous["tx_errors"]),
                    "rx_dropped": max(0, current["rx_dropped"] - previous["rx_dropped"]),
                    "tx_dropped": max(0, current["tx_dropped"] - previous["tx_dropped"]),
                }
                net_samples.setdefault(name, []).append(sample)
            previous_net = current_net

        previous_time = current_time

    result: Dict[str, Dict[str, Any]] = {}
    if need_cpu:
        processes = []
        for item in process_samples.values():
            samples = item.pop("samples")
            if not samples:
                continue
            item["average_percent"] = round(sum(samples) / len(samples), 2)
            item["peak_percent"] = round(max(samples), 2)
            item["sample_count"] = len(samples)
            processes.append(item)
        processes.sort(key=lambda item: item["average_percent"], reverse=True)
        try:
            load = list(os.getloadavg())
        except OSError:
            load = [0.0, 0.0, 0.0]
        result["cpu"] = {
            "status": "ok" if cpu_samples else "unknown",
            "sample_seconds": seconds,
            "sample_interval": interval,
            "average_percent": round(sum(cpu_samples) / len(cpu_samples), 2) if cpu_samples else 0.0,
            "peak_percent": round(max(cpu_samples), 2) if cpu_samples else 0.0,
            "load": [round(value, 2) for value in load],
            "processes": processes[:top_n],
            "unreadable_process_count": denied,
        }
    if need_disk:
        devices = []
        for name, samples in disk_samples.items():
            if not samples:
                continue
            device: Dict[str, Any] = {"device": name, "device_kind": "whole-device"}
            for metric in ("read_bps", "write_bps", "read_iops", "write_iops"):
                values = [sample[metric] for sample in samples]
                device[f"average_{metric}"] = round(sum(values) / len(values), 2)
                device[f"peak_{metric}"] = round(max(values), 2)
            devices.append(device)
        devices.sort(key=lambda item: item["average_read_bps"] + item["average_write_bps"], reverse=True)
        result["disk_io"] = {
            "status": "ok" if devices else "unknown",
            "sample_seconds": seconds,
            "devices": devices,
            "enhanced_metrics": "unknown",
        }
    if need_network:
        network_items = []
        for name, samples in net_samples.items():
            if not samples:
                continue
            item = {"name": name, "type": interface_type(name)}
            for metric in ("rx_bps", "tx_bps"):
                values = [sample[metric] for sample in samples]
                item[f"average_{metric}"] = round(sum(values) / len(values), 2)
                item[f"peak_{metric}"] = round(max(values), 2)
            for metric in ("rx_errors", "tx_errors", "rx_dropped", "tx_dropped"):
                item[metric] = int(sum(sample[metric] for sample in samples))
            network_items.append(item)
        network_items.sort(key=lambda item: item["average_rx_bps"] + item["average_tx_bps"], reverse=True)
        result["network"] = {
            "status": "ok" if network_items else "unknown",
            "sample_seconds": seconds,
            "interfaces": network_items,
        }
    return result


def collect_memory(top_n: int) -> Dict[str, Any]:
    mem = read_meminfo()
    total = mem.get("MemTotal", 0)
    available = mem.get("MemAvailable", mem.get("MemFree", 0))
    used = max(0, total - available)
    swap_total = mem.get("SwapTotal", 0)
    swap_free = mem.get("SwapFree", 0)
    processes: List[Dict[str, Any]] = []
    for entry in os.listdir("/proc") if os.path.isdir("/proc") else []:
        if not entry.isdigit():
            continue
        pid = int(entry)
        status = read_text(f"/proc/{pid}/status")
        match = re.search(r"^VmRSS:\s+(\d+)\s+kB", status, re.M)
        if not match:
            continue
        rss = int(match.group(1)) * 1024
        user, command = process_identity(pid)
        processes.append(
            {
                "pid": pid,
                "user": user,
                "command": command,
                "rss_bytes": rss,
                "memory_percent": round(rss * 100.0 / total, 2) if total else 0.0,
            }
        )
    processes.sort(key=lambda item: item["rss_bytes"], reverse=True)
    return {
        "status": "ok" if total else "unknown",
        "total": total,
        "used": used,
        "available": available,
        "available_percent": round(available * 100.0 / total, 2) if total else 0.0,
        "used_percent": round(used * 100.0 / total, 2) if total else 0.0,
        "cached": mem.get("Cached", 0) + mem.get("SReclaimable", 0),
        "buffers": mem.get("Buffers", 0),
        "swap_total": swap_total,
        "swap_used": max(0, swap_total - swap_free),
        "processes": processes[:top_n],
    }


def unescape_mount(value: str) -> str:
    value = re.sub(r"\\x([0-9a-fA-F]{2})", lambda match: chr(int(match.group(1), 16)), value)
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), value)


def classify_filesystem(fstype: str, source: str = "") -> Tuple[str, str]:
    normalized = (fstype or "unknown").lower()
    if normalized in SPECIAL_FS_TYPES:
        return "special", "特殊或容器文件系统"
    if normalized in REMOTE_FS_TYPES or normalized.startswith(("nfs", "cifs", "smb")):
        return "remote", "远程或分布式挂载"
    if normalized.startswith("fuse."):
        return "remote", "未知 FUSE 挂载，保守排除"
    if source.startswith(("//", "sshfs#")):
        return "remote", "远程或分布式挂载"
    return "local", "本地文件系统"


def discover_mounts_findmnt() -> List[Dict[str, str]]:
    if not shutil.which("findmnt"):
        return []
    stdout, _, code = run_command(["findmnt", "-n", "-P", "-o", "SOURCE,TARGET,FSTYPE"], timeout=10)
    if code != 0 or not stdout.strip():
        return []
    mounts: List[Dict[str, str]] = []
    for line in stdout.splitlines():
        try:
            fields = dict(part.split("=", 1) for part in shlex.split(line) if "=" in part)
        except ValueError:
            continue
        source = unescape_mount(fields.get("SOURCE", "unknown"))
        target = normalize_path(unescape_mount(fields.get("TARGET", "/")))
        fstype = fields.get("FSTYPE", "unknown")
        category, reason = classify_filesystem(fstype, source)
        mounts.append(
            {
                "source": source,
                "target": target,
                "fstype": fstype,
                "options": "",
                "category": category,
                "reason": reason,
            }
        )
    return mounts


def discover_mounts_mountinfo(text: Optional[str] = None) -> List[Dict[str, str]]:
    content = text if text is not None else read_text("/proc/self/mountinfo")
    mounts: List[Dict[str, str]] = []
    for line in content.splitlines():
        left, separator, right = line.partition(" - ")
        if not separator:
            continue
        left_parts = left.split()
        right_parts = right.split()
        if len(left_parts) < 6 or len(right_parts) < 2:
            continue
        target = normalize_path(unescape_mount(left_parts[4]))
        fstype = right_parts[0]
        source = unescape_mount(right_parts[1])
        category, reason = classify_filesystem(fstype, source)
        mounts.append(
            {
                "source": source,
                "target": target,
                "fstype": fstype,
                "options": left_parts[5],
                "category": category,
                "reason": reason,
            }
        )
    return mounts


def discover_mounts() -> List[Dict[str, str]]:
    mounts = discover_mounts_findmnt() or discover_mounts_mountinfo()
    unique: Dict[str, Dict[str, str]] = {}
    for mount in mounts:
        unique[mount["target"]] = mount
    return sorted(unique.values(), key=lambda item: (len(item["target"]), item["target"]))


def find_mount_for_path(path: str, mounts: Sequence[Dict[str, str]]) -> Optional[Dict[str, str]]:
    normalized = normalize_path(path)
    candidates = [mount for mount in mounts if path_is_within(normalized, mount["target"])]
    return max(candidates, key=lambda item: len(item["target"])) if candidates else None


def collect_filesystems(mounts: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    filesystems: List[Dict[str, Any]] = []
    for mount in mounts:
        if mount["category"] != "local":
            continue
        if not os.path.isdir(mount["target"]):
            continue
        try:
            stats = os.statvfs(mount["target"])
        except OSError as exc:
            filesystems.append({**mount, "status": "unknown", "error": str(exc)})
            continue
        total = stats.f_blocks * stats.f_frsize
        available = stats.f_bavail * stats.f_frsize
        used = max(0, total - stats.f_bfree * stats.f_frsize)
        inode_total = stats.f_files
        inode_available = stats.f_favail
        inode_used = max(0, inode_total - stats.f_ffree)
        filesystems.append(
            {
                **mount,
                "status": "ok",
                "total": total,
                "used": used,
                "available": available,
                "used_percent": round(used * 100.0 / total, 2) if total else 0.0,
                "inode_total": inode_total,
                "inode_used": inode_used,
                "inode_available": inode_available,
                "inode_used_percent": round(inode_used * 100.0 / inode_total, 2) if inode_total else 0.0,
            }
        )
    return {"status": "ok" if filesystems else "unknown", "filesystems": filesystems, "skipped_mounts": []}


def build_scan_plan(
    roots: Sequence[str], mounts: Sequence[Dict[str, str]], excludes: Sequence[str]
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    plan: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []
    normalized_excludes = {normalize_path(path) for path in excludes}
    seen: set = set()
    for root_value in roots:
        root = normalize_path(root_value)
        if root in seen:
            continue
        seen.add(root)
        if not os.path.exists(root):
            skipped.append({"target": root, "fstype": "unknown", "reason": "扫描根目录不存在"})
            continue
        if any(path_is_within(root, excluded) for excluded in normalized_excludes):
            skipped.append({"target": root, "fstype": "unknown", "reason": "用户自定义排除"})
            continue
        root_mount = find_mount_for_path(root, mounts)
        if not root_mount:
            skipped.append({"target": root, "fstype": "unknown", "reason": "无法确定所属文件系统"})
            continue
        if root_mount["category"] != "local":
            skipped.append(
                {"target": root, "fstype": root_mount["fstype"], "reason": root_mount["reason"]}
            )
            continue
        plan.append(
            {
                "root": root,
                "mount_target": root_mount["target"],
                "fstype": root_mount["fstype"],
                "source": root_mount["source"],
            }
        )
        nested = [
            mount
            for mount in mounts
            if mount["target"] != root_mount["target"] and path_is_within(mount["target"], root)
        ]
        for mount in nested:
            if mount["category"] == "local":
                if mount["target"] not in seen and not any(
                    path_is_within(mount["target"], excluded) for excluded in normalized_excludes
                ):
                    seen.add(mount["target"])
                    plan.append(
                        {
                            "root": mount["target"],
                            "mount_target": mount["target"],
                            "fstype": mount["fstype"],
                            "source": mount["source"],
                        }
                    )
            else:
                skipped.append(
                    {"target": mount["target"], "fstype": mount["fstype"], "reason": mount["reason"]}
                )
    unique_plan = {item["root"]: item for item in plan}
    unique_skipped = {item["target"]: item for item in skipped}
    return list(unique_plan.values()), sorted(unique_skipped.values(), key=lambda item: item["target"])


def scan_directory_tree(
    root: str,
    mount_target: str,
    max_depth: int,
    timeout: float,
    excludes: Sequence[str],
    mounts: Sequence[Dict[str, str]],
) -> Dict[str, Any]:
    start = time.monotonic()
    root = normalize_path(root)
    normalized_excludes = {normalize_path(path) for path in excludes}
    blocked_mounts = {
        mount["target"]
        for mount in mounts
        if mount["target"] != mount_target and path_is_within(mount["target"], root)
    }
    exclude_paths = sorted(
        {path for path in normalized_excludes | blocked_mounts if path_is_within(path, root) and path != root}
    )
    errors: List[str] = []
    timed_out = False
    if not os.path.isdir(root):
        return {
            "root": root,
            "mount_target": mount_target,
            "status": "failed",
            "duration_seconds": round(time.monotonic() - start, 2),
            "entries": [],
            "errors": ["扫描根目录不存在或不是目录"],
        }
    command = ["du", "-x", "-B1", f"--max-depth={max_depth}"]
    for path in exclude_paths:
        command.append(f"--exclude={path}")
    command.append(root)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    stdout = ""
    stderr = ""
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        partial_stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        partial_stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        try:
            os.killpg(process.pid, signal.SIGTERM)
            stdout_after, stderr_after = process.communicate(timeout=2)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout_after, stderr_after = process.communicate()
        stdout = partial_stdout + (stdout_after or "")
        stderr = partial_stderr + (stderr_after or "")
    except KeyboardInterrupt:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        raise
    if stderr.strip():
        errors.extend(stderr.strip().splitlines()[:50])
    entries: List[Dict[str, Any]] = []
    seen_paths = set()
    for line in stdout.splitlines():
        size_text, separator, path = line.partition("\t")
        if not separator:
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            size_text, path = parts
        normalized = normalize_path(path)
        if normalized == root or normalized in seen_paths:
            continue
        if any(path_is_within(normalized, excluded) for excluded in exclude_paths):
            continue
        seen_paths.add(normalized)
        entries.append({"path": normalized, "bytes": safe_int(size_text)})
    entries.sort(key=lambda item: item["bytes"], reverse=True)
    return {
        "root": root,
        "mount_target": mount_target,
        "status": "incomplete" if timed_out or errors or process.returncode not in (0, None) else "ok",
        "timed_out": timed_out,
        "duration_seconds": round(time.monotonic() - start, 2),
        "entries": entries,
        "errors": errors,
    }


def collect_disk_space(
    roots: Sequence[str], mounts: Sequence[Dict[str, str]], excludes: Sequence[str], depth: int, timeout: float, top_n: int
) -> Dict[str, Any]:
    result = collect_filesystems(mounts)
    plan, plan_skipped = build_scan_plan(roots, mounts, excludes)
    result["skipped_mounts"] = sorted(
        {item["target"]: item for item in result["skipped_mounts"] + plan_skipped}.values(),
        key=lambda item: item["target"],
    )
    scans: List[Dict[str, Any]] = []
    ranking: List[Dict[str, Any]] = []
    for task in plan:
        scan = scan_directory_tree(
            task["root"], task["mount_target"], depth, timeout, excludes, mounts
        )
        scan["fstype"] = task["fstype"]
        scan["source"] = task["source"]
        scans.append(scan)
        for item in scan["entries"]:
            ranking.append(
                {
                    **item,
                    "scan_root": task["root"],
                    "mount_target": task["mount_target"],
                    "fstype": task["fstype"],
                }
            )
    ranking.sort(key=lambda item: item["bytes"], reverse=True)
    result.update(
        {
            "scan_roots": list(roots),
            "scan_depth": depth,
            "scan_timeout": timeout,
            "exclude_paths": list(excludes),
            "scan_tasks": scans,
            "directory_ranking": ranking[:top_n],
        }
    )
    return result


def parse_iostat_json(payload: str) -> Dict[str, Dict[str, float]]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    hosts = data.get("sysstat", {}).get("hosts", [])
    if not hosts:
        return {}
    statistics = hosts[0].get("statistics", [])
    if not statistics:
        return {}
    devices = statistics[-1].get("disk", [])
    result: Dict[str, Dict[str, float]] = {}
    for item in devices:
        name = str(item.get("disk_device", item.get("disk", "")))
        if not name:
            continue
        result[name] = {
            "await_ms": safe_float(item.get("await", item.get("aqu-sz"))),
            "queue_size": safe_float(item.get("aqu-sz", item.get("avgqu-sz"))),
            "util_percent": safe_float(item.get("util", item.get("%util"))),
        }
    return result


def enrich_disk_io(disk_io: Dict[str, Any]) -> Dict[str, Any]:
    if disk_io.get("status") != "ok":
        return disk_io
    if not shutil.which("iostat"):
        disk_io["enhanced_error"] = "iostat 自动安装失败或安装后仍不可用，详见依赖工具章节"
        return disk_io
    stdout, stderr, code = run_command(["iostat", "-x", "-o", "JSON", "1", "2"], timeout=8)
    enhanced = parse_iostat_json(stdout) if code == 0 else {}
    if not enhanced:
        disk_io["enhanced_error"] = stderr.strip() or "iostat 输出无法解析"
        return disk_io
    for device in disk_io.get("devices", []):
        device.update(enhanced.get(device["device"], {}))
    disk_io["enhanced_metrics"] = "ok"
    return disk_io


def interface_addresses(name: str) -> List[str]:
    if not shutil.which("ip"):
        return []
    stdout, _, code = run_command(["ip", "-o", "addr", "show", "dev", name], timeout=3)
    if code != 0:
        return []
    result = []
    for line in stdout.splitlines():
        match = re.search(r"\s(inet6?)\s+(\S+)", line)
        if match:
            result.append(match.group(2))
    return result


def interface_speed(name: str) -> Optional[str]:
    speed = read_text(f"/sys/class/net/{name}/speed").strip()
    if speed and safe_int(speed, -1) > 0:
        return f"{speed}Mb/s"
    if shutil.which("ethtool"):
        stdout, _, code = run_command(["ethtool", name], timeout=3)
        if code == 0:
            match = re.search(r"Speed:\s*(\S+)", stdout)
            if match:
                return match.group(1)
    return None


def default_routes() -> Dict[str, str]:
    if not shutil.which("ip"):
        return {}
    stdout, _, code = run_command(["ip", "route", "show", "default"], timeout=3)
    if code != 0:
        return {}
    result: Dict[str, str] = {}
    for line in stdout.splitlines():
        dev = re.search(r"\bdev\s+(\S+)", line)
        via = re.search(r"\bvia\s+(\S+)", line)
        if dev:
            result[dev.group(1)] = via.group(1) if via else "direct"
    return result


def enrich_network(network: Dict[str, Any]) -> Dict[str, Any]:
    routes = default_routes()
    for item in network.get("interfaces", []):
        name = item["name"]
        item["state"] = read_text(f"/sys/class/net/{name}/operstate", "unknown").strip() or "unknown"
        item["addresses"] = interface_addresses(name)
        item["link_speed"] = interface_speed(name) or "unknown"
        item["default_gateway"] = routes.get(name)
    return network


def collect_hardware() -> Dict[str, Any]:
    cpu_model = "unknown"
    match = re.search(r"^model name\s*:\s*(.+)$", read_text("/proc/cpuinfo"), re.M)
    if match:
        cpu_model = match.group(1).strip()
    devices: List[Dict[str, Any]] = []
    block_root = pathlib.Path("/sys/class/block")
    if block_root.exists():
        for item in sorted(block_root.iterdir(), key=lambda value: value.name):
            if item.name.startswith(SKIP_BLOCK_PREFIXES) or (item / "partition").exists():
                continue
            sectors = safe_int(read_text(str(item / "size")).strip())
            rotational = safe_int(read_text(str(item / "queue" / "rotational")).strip(), -1)
            device = {
                "device": f"/dev/{item.name}",
                "model": read_text(str(item / "device" / "model"), "unknown").strip() or "unknown",
                "type": "HDD" if rotational == 1 else "SSD" if rotational == 0 else "unknown",
                "capacity": sectors * 512,
                "smart_status": "unknown",
                "temperature": None,
            }
            if shutil.which("smartctl"):
                stdout, stderr, code = run_command(["smartctl", "-H", "-A", device["device"]], timeout=8)
                combined = f"{stdout}\n{stderr}"
                if code in (0, 2) and combined.strip():
                    if re.search(r"overall-health.*PASSED|SMART Health Status:\s*OK", combined, re.I):
                        device["smart_status"] = "passed"
                    elif re.search(r"overall-health.*FAILED|SMART Health Status:\s*(?!OK)", combined, re.I):
                        device["smart_status"] = "failed"
                    temp = re.search(r"(?:Temperature_Celsius|Composite Temperature|Temperature):.*?(\d+)\s*(?:Celsius|C|$)", combined, re.I)
                    if temp:
                        device["temperature"] = safe_int(temp.group(1))
                else:
                    device["smart_error"] = stderr.strip() or "当前环境无法读取 SMART"
            else:
                device["smart_error"] = "smartctl 自动安装失败或安装后仍不可用，详见依赖工具章节"
            devices.append(device)
    return {
        "status": "ok",
        "cpu_model": cpu_model,
        "devices": devices,
        "note": "虚拟机可能不暴露物理磁盘 SMART 或温度信息",
    }


def validate_disk_test_dir(
    directory: str, mounts: Sequence[Dict[str, str]], excludes: Sequence[str], required_bytes: int
) -> Tuple[bool, str, Optional[Dict[str, str]]]:
    path = normalize_path(directory)
    if not os.path.isdir(path):
        return False, "测试目录不存在", None
    if not os.access(path, os.W_OK):
        return False, "测试目录不可写", None
    if any(path_is_within(path, normalize_path(value)) for value in excludes):
        return False, "测试目录属于用户排除路径", None
    mount = find_mount_for_path(path, mounts)
    if not mount:
        return False, "无法确认测试目录所属文件系统", None
    if mount["category"] != "local":
        return False, f"测试目录位于{mount['reason']} ({mount['fstype']})", mount
    try:
        available = shutil.disk_usage(path).free
    except OSError as exc:
        return False, f"无法读取可用空间: {exc}", mount
    if available < required_bytes * 2:
        return False, f"可用空间不足，至少需要 {format_bytes(required_bytes * 2)}", mount
    return True, "ok", mount


def run_disk_benchmark(args: argparse.Namespace, mounts: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    if not shutil.which("fio"):
        return {"status": "skipped", "error": "fio 自动安装失败或安装后仍不可用，详见依赖工具章节"}
    size_bytes = parse_size(args.disk_test_size)
    ok, reason, mount = validate_disk_test_dir(args.disk_test_dir, mounts, args.exclude_path, size_bytes)
    if not ok:
        return {"status": "skipped", "error": reason}
    fd, test_path = tempfile.mkstemp(prefix="jh-resource-fio-", dir=normalize_path(args.disk_test_dir))
    os.close(fd)
    cleanup_error = None
    result: Dict[str, Any] = {"status": "failed", "error": "fio 未完成"}
    command = [
        "fio",
        "--name=jh-resource-report",
        f"--filename={test_path}",
        "--rw=readwrite",
        "--bs=1M",
        "--ioengine=sync",
        "--iodepth=1",
        "--numjobs=1",
        f"--size={args.disk_test_size}",
        f"--runtime={args.disk_test_seconds}",
        "--time_based",
        "--direct=1",
        "--output-format=json",
    ]
    try:
        stdout, stderr, code = run_command(command, timeout=args.disk_test_seconds + 20)
        if code != 0:
            result: Dict[str, Any] = {"status": "failed", "error": stderr.strip() or f"fio 退出码 {code}"}
        else:
            try:
                payload = json.loads(stdout)
                job = payload.get("jobs", [{}])[0]
                result = {
                    "status": "ok",
                    "read_bps": safe_float(job.get("read", {}).get("bw_bytes")),
                    "write_bps": safe_float(job.get("write", {}).get("bw_bytes")),
                    "read_iops": safe_float(job.get("read", {}).get("iops")),
                    "write_iops": safe_float(job.get("write", {}).get("iops")),
                }
            except (json.JSONDecodeError, IndexError):
                result = {"status": "failed", "error": "fio JSON 输出无法解析"}
        result.update(
            {
                "test_dir": normalize_path(args.disk_test_dir),
                "fstype": mount["fstype"] if mount else "unknown",
                "size": args.disk_test_size,
                "runtime_seconds": args.disk_test_seconds,
            }
        )
    except KeyboardInterrupt:
        result = {
            "status": "skipped",
            "error": "用户中断磁盘性能测试",
            "test_dir": normalize_path(args.disk_test_dir),
            "fstype": mount["fstype"] if mount else "unknown",
            "size": args.disk_test_size,
            "runtime_seconds": args.disk_test_seconds,
        }
    finally:
        try:
            os.remove(test_path)
        except OSError as exc:
            cleanup_error = str(exc)
    if cleanup_error:
        result["cleanup_error"] = cleanup_error
        result["residual_file"] = test_path
    return result


def run_speedtest() -> Dict[str, Any]:
    candidates = [
        ("speedtest", ["speedtest", "--accept-license", "--accept-gdpr", "-f", "json"]),
        ("speedtest-cli", ["speedtest-cli", "--json"]),
    ]
    for tool, command in candidates:
        if not shutil.which(tool):
            continue
        stdout, stderr, code = run_command(command, timeout=90)
        if code != 0:
            return {"status": "failed", "tool": tool, "error": stderr.strip() or f"退出码 {code}"}
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return {"status": "failed", "tool": tool, "error": "测速工具 JSON 输出无法解析"}
        if tool == "speedtest":
            return {
                "status": "ok",
                "tool": tool,
                "latency_ms": safe_float(payload.get("ping", {}).get("latency")),
                "download_bps": safe_float(payload.get("download", {}).get("bandwidth")) * 8,
                "upload_bps": safe_float(payload.get("upload", {}).get("bandwidth")) * 8,
                "server": payload.get("server", {}).get("name"),
            }
        return {
            "status": "ok",
            "tool": tool,
            "latency_ms": safe_float(payload.get("ping")),
            "download_bps": safe_float(payload.get("download")),
            "upload_bps": safe_float(payload.get("upload")),
            "server": payload.get("server", {}).get("sponsor"),
        }
    return {"status": "skipped", "error": "测速工具自动安装失败或安装后仍不可用，详见依赖工具章节"}


def make_issue(
    severity: str, module: str, metric: str, value: Any, basis: str, window: str, suggestion: str
) -> Dict[str, Any]:
    return {
        "severity": severity,
        "module": module,
        "metric": metric,
        "value": value,
        "basis": basis,
        "window": window,
        "message": f"本次采样期间观察到 {metric} 为 {value}",
        "suggestion": suggestion,
    }


def threshold_severity(value: float, warn: float, critical: float) -> Optional[str]:
    if value >= critical:
        return "critical"
    if value >= warn:
        return "warning"
    return None


def analyze_report(report: Dict[str, Any], args: argparse.Namespace) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    modules = report.get("modules", {})
    cpu = modules.get("cpu", {})
    if cpu.get("status") == "ok":
        average = safe_float(cpu.get("average_percent"))
        severity = threshold_severity(average, args.cpu_warn, args.cpu_crit)
        if severity:
            issues.append(
                make_issue(
                    severity,
                    "cpu",
                    "CPU 平均使用率",
                    f"{average}%",
                    f"警告 {args.cpu_warn}% / 严重 {args.cpu_crit}%",
                    f"{cpu.get('sample_seconds', 0)} 秒",
                    "检查 CPU 排行进程，并结合业务时段继续观察。",
                )
            )
        cpu_count = max(1, safe_int(report.get("metadata", {}).get("cpu_count"), 1))
        load1 = safe_float((cpu.get("load") or [0])[0])
        if load1 >= cpu_count * 2:
            issues.append(
                make_issue(
                    "critical",
                    "cpu",
                    "1 分钟负载",
                    load1,
                    f"逻辑核数 {cpu_count} 的 2 倍",
                    "当前负载快照",
                    "检查运行队列、不可中断 I/O 和高占用进程。",
                )
            )
        elif load1 >= cpu_count:
            issues.append(
                make_issue(
                    "warning",
                    "cpu",
                    "1 分钟负载",
                    load1,
                    f"逻辑核数 {cpu_count}",
                    "当前负载快照",
                    "结合 CPU 与磁盘 I/O 排行确认排队来源。",
                )
            )

    memory = modules.get("memory", {})
    if memory.get("status") == "ok":
        used_percent = safe_float(memory.get("used_percent"))
        severity = threshold_severity(used_percent, args.mem_warn, args.mem_crit)
        if severity:
            issues.append(
                make_issue(
                    severity,
                    "memory",
                    "内存使用率（按可用内存计算）",
                    f"{used_percent}%",
                    f"警告 {args.mem_warn}% / 严重 {args.mem_crit}%",
                    "当前内存快照",
                    "检查 RSS 内存排行和应用缓存配置。",
                )
            )
        swap_total = safe_int(memory.get("swap_total"))
        swap_used = safe_int(memory.get("swap_used"))
        if swap_total and swap_used:
            swap_percent = swap_used * 100.0 / swap_total
            issues.append(
                make_issue(
                    "warning" if swap_percent >= 50 else "info",
                    "memory",
                    "Swap 使用率",
                    f"{swap_percent:.2f}%",
                    "Swap 已被使用",
                    "当前内存快照",
                    "确认是否存在历史内存压力，并观察换入换出活动。",
                )
            )

    disk_space = modules.get("disk_space", {})
    for filesystem in disk_space.get("filesystems", []):
        if filesystem.get("status") != "ok":
            continue
        used_percent = safe_float(filesystem.get("used_percent"))
        severity = threshold_severity(used_percent, args.disk_warn, args.disk_crit)
        if severity:
            issues.append(
                make_issue(
                    severity,
                    "disk_space",
                    f"{filesystem.get('target')} 磁盘使用率",
                    f"{used_percent}%",
                    f"警告 {args.disk_warn}% / 严重 {args.disk_crit}%",
                    "当前文件系统快照",
                    "根据目录占用排行清理、迁移或扩容。",
                )
            )
        inode_percent = safe_float(filesystem.get("inode_used_percent"))
        severity = threshold_severity(inode_percent, args.inode_warn, args.inode_crit)
        if severity:
            issues.append(
                make_issue(
                    severity,
                    "disk_space",
                    f"{filesystem.get('target')} inode 使用率",
                    f"{inode_percent}%",
                    f"警告 {args.inode_warn}% / 严重 {args.inode_crit}%",
                    "当前文件系统快照",
                    "检查大量小文件目录和日志文件。",
                )
            )

    disk_io = modules.get("disk_io", {})
    for device in disk_io.get("devices", []):
        util = device.get("util_percent")
        if util is not None:
            severity = threshold_severity(safe_float(util), args.io_util_warn, args.io_util_crit)
            if severity:
                issues.append(
                    make_issue(
                        severity,
                        "disk_io",
                        f"{device.get('device')} 磁盘利用率",
                        f"{safe_float(util):.2f}%",
                        f"警告 {args.io_util_warn}% / 严重 {args.io_util_crit}%",
                        f"{disk_io.get('sample_seconds', 0)} 秒",
                        "检查当前读写任务，避免同时运行备份或性能测试。",
                    )
                )
        await_ms = device.get("await_ms")
        if await_ms is not None:
            severity = threshold_severity(safe_float(await_ms), args.io_await_warn, args.io_await_crit)
            if severity:
                issues.append(
                    make_issue(
                        severity,
                        "disk_io",
                        f"{device.get('device')} I/O 等待时间",
                        f"{safe_float(await_ms):.2f} ms",
                        f"警告 {args.io_await_warn} ms / 严重 {args.io_await_crit} ms",
                        f"{disk_io.get('sample_seconds', 0)} 秒",
                        "检查设备繁忙度、队列和高 I/O 业务。",
                    )
                )

    network = modules.get("network", {})
    for interface in network.get("interfaces", []):
        errors = sum(safe_int(interface.get(name)) for name in NET_COUNTER_NAMES[2:])
        if errors:
            issues.append(
                make_issue(
                    "critical" if errors >= 100 else "warning",
                    "network",
                    f"{interface.get('name')} 网络错误与丢包增量",
                    errors,
                    "采样期间增量大于 0",
                    f"{network.get('sample_seconds', 0)} 秒",
                    "检查网卡、交换机端口、双工协商和链路拥塞。",
                )
            )

    severity_order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(issues, key=lambda item: severity_order.get(item["severity"], 9))


def severity_label(severity: str) -> str:
    return SEVERITY_LABELS.get(severity, severity)


def module_label(key: str) -> str:
    return MODULE_BY_KEY.get(key, ("", key, False))[1]


def build_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    """汇总异常风险和采集降级信息，供报告顶部的概要信息使用。"""
    items: List[Dict[str, str]] = []
    dependencies = report.get("dependencies", {})
    failed_tools = [item for item in dependencies.get("tools", []) if item.get("status") == "failed"]

    for issue in report.get("issues", []):
        if issue.get("severity") not in ("critical", "warning"):
            continue
        items.append(
            {
                "severity": issue["severity"],
                "module": issue.get("module", ""),
                "text": (
                    f"{module_label(issue.get('module', ''))}：{issue['metric']} {issue['value']}"
                    f"（依据：{issue['basis']}；窗口：{issue['window']}）"
                ),
            }
        )

    status_labels = {
        "failed": ("critical", "采集失败"),
        "incomplete": ("warning", "采集不完整"),
        "unknown": ("warning", "部分指标不可用"),
        "skipped": ("info", "未执行"),
    }
    for key, value in report.get("modules", {}).items():
        status = value.get("status")
        if status not in status_labels:
            continue
        severity, label = status_labels[status]
        detail = value.get("error") or label
        items.append({"severity": severity, "module": key, "text": f"{module_label(key)}：{label}（{detail}）"})

    disk_io = report.get("modules", {}).get("disk_io", {})
    if disk_io.get("enhanced_error") and not failed_tools:
        items.append(
            {
                "severity": "warning",
                "module": "disk_io",
                "text": f"{module_label('disk_io')}：增强指标不可用（{disk_io['enhanced_error']}）",
            }
        )

    disk_space = report.get("modules", {}).get("disk_space", {})
    for task in disk_space.get("scan_tasks", []):
        if task.get("status") == "ok":
            continue
        items.append(
            {
                "severity": "warning",
                "module": "disk_space",
                "text": (
                    f"目录扫描未完成：{task.get('root')}"
                    f"（{task.get('status')}，耗时 {task.get('duration_seconds')}s）"
                ),
            }
        )

    for key, value in report.get("modules", {}).items():
        if value.get("residual_file"):
            items.append(
                {
                    "severity": "warning",
                    "module": key,
                    "text": f"{module_label(key)}：发现需要人工清理的残留文件 {value['residual_file']}",
                }
            )

    for item in failed_tools:
        items.append(
            {
                "severity": "warning",
                "module": "dependencies",
                "text": (
                    f"依赖工具 {item['command']}（{item['package']}）安装后仍不可用，"
                    f"请手动执行：{item['manual_install_command']}"
                ),
            }
        )

    metadata = report.get("metadata", {})
    if metadata.get("output_fallback_reason"):
        items.append(
            {
                "severity": "info",
                "module": "output",
                "text": (
                    f"报告输出目录已回退到 {metadata.get('output_dir')}"
                    f"（{metadata['output_fallback_reason']}）"
                ),
            }
        )

    items.sort(key=lambda item: SEVERITY_ORDER.get(item["severity"], 9))
    counts = {severity: sum(1 for item in items if item["severity"] == severity) for severity in SEVERITY_ORDER}
    risk_count = counts["critical"] + counts["warning"]
    return {
        "status": "risk" if risk_count else "ok",
        "counts": counts,
        "items": items,
        "conclusion": None if risk_count else "服务运行正常，继续保持！",
    }


def section_status_summary(report: Dict[str, Any]) -> Tuple[List[str], List[str], List[str]]:
    completed: List[str] = []
    skipped: List[str] = []
    failed: List[str] = []
    for key in report.get("selected_modules", []):
        label = MODULE_BY_KEY.get(key, ("", key, False))[1]
        value = report.get("modules", {}).get(key, {})
        status = value.get("status", "unknown")
        if status in ("ok", "incomplete", "unknown"):
            completed.append(label)
        elif status == "skipped":
            skipped.append(label)
        else:
            failed.append(label)
    for key in report.get("skipped_modules", {}):
        label = MODULE_BY_KEY.get(key, ("", key, False))[1]
        if label not in skipped:
            skipped.append(label)
    return completed, skipped, failed


def render_text(report: Dict[str, Any]) -> str:
    metadata = report["metadata"]
    modules = report.get("modules", {})
    issues = report.get("issues", [])
    completed, skipped, failed = section_status_summary(report)
    lines = [
        "================服务器资源分析报告================",
        f"主机：{metadata.get('hostname', 'unknown')}",
        f"系统：{metadata.get('os', 'unknown')}",
        f"内核：{metadata.get('kernel', 'unknown')}",
        f"报告时间：{metadata.get('started_at')} ~ {metadata.get('finished_at')}",
        f"完成模块：{', '.join(completed) or '无'}",
        f"跳过模块：{', '.join(skipped) or '无'}",
        f"失败模块：{', '.join(failed) or '无'}",
        "",
        "【概要信息】",
    ]
    summary = report.get("summary") or build_summary(report)
    if summary.get("items"):
        lines.append(f"风险统计：严重 {summary['counts']['critical']}，警告 {summary['counts']['warning']}，提示 {summary['counts']['info']}")
        for item in summary["items"]:
            lines.append(f"- 【{severity_label(item['severity'])}】{item['text']}")
    else:
        lines.append(f"- {summary.get('conclusion') or '服务运行正常，继续保持！'}")
    lines.extend(["", "【分析结论】"])
    if not issues:
        lines.append("本次采样期间未发现达到已配置阈值的问题。")
    for index, issue in enumerate(issues, 1):
        severity = severity_label(issue["severity"])
        lines.extend(
            [
                f"{index}. [{severity}] {issue['message']}",
                f"   依据：{issue['basis']}；观察窗口：{issue['window']}",
                f"   建议：{issue['suggestion']}",
            ]
        )

    dependencies = report.get("dependencies", {})
    lines.extend(["", "【依赖工具】", f"包管理器：{dependencies.get('package_manager', 'unknown')}"] )
    for item in dependencies.get("tools", []):
        lines.append(
            f"- {item['command']}：{item['status']}（软件包 {item['package']}，模块 {', '.join(item.get('modules', [])) or 'unknown'}）"
        )
        if item.get("error"):
            lines.append(f"  错误：{item['error']}")
            lines.append(f"  手动安装：{item['manual_install_command']}")

    system = modules.get("system")
    if system:
        lines.extend(
            [
                "",
                "【系统概要】",
                f"主机名：{system.get('hostname', 'unknown')}",
                f"系统：{system.get('os', 'unknown')}",
                f"内核：{system.get('kernel', 'unknown')} / {system.get('architecture', 'unknown')}",
                f"运行时间：{system.get('uptime_seconds', 0) / 86400:.2f} 天",
                f"CPU 核数：{system.get('cpu_count', 0)}",
                f"内存总量：{format_bytes(system.get('memory_total', 0))}",
                f"虚拟化：{system.get('virtualization', 'unknown')}",
            ]
        )

    cpu = modules.get("cpu")
    if cpu:
        lines.extend(
            [
                "",
                "【CPU 使用分析】",
                f"采样：{cpu.get('sample_seconds', 0)} 秒，平均 {cpu.get('average_percent', 0)}%，峰值 {cpu.get('peak_percent', 0)}%",
                f"负载：{', '.join(str(value) for value in cpu.get('load', []))}（1/5/15分钟）",
                "CPU 进程排行：",
            ]
        )
        for index, item in enumerate(cpu.get("processes", []), 1):
            lines.append(
                f"{index}. PID {item['pid']} {item['user']} 平均 {item['average_percent']}% 峰值 {item['peak_percent']}% 样本 {item['sample_count']} | {item['command'][:100]}"
            )

    memory = modules.get("memory")
    if memory:
        lines.extend(
            [
                "",
                "【内存使用分析】",
                f"总量：{format_bytes(memory.get('total', 0))}",
                f"已用：{format_bytes(memory.get('used', 0))} ({memory.get('used_percent', 0)}%)",
                f"可用：{format_bytes(memory.get('available', 0))} ({memory.get('available_percent', 0)}%)",
                f"缓存：{format_bytes(memory.get('cached', 0))}；Swap：{format_bytes(memory.get('swap_used', 0))} / {format_bytes(memory.get('swap_total', 0))}",
                "内存进程排行：",
            ]
        )
        for index, item in enumerate(memory.get("processes", []), 1):
            lines.append(
                f"{index}. PID {item['pid']} {item['user']} RSS {format_bytes(item['rss_bytes'])} ({item['memory_percent']}%) | {item['command'][:100]}"
            )

    disk_space = modules.get("disk_space")
    if disk_space:
        lines.extend(["", "【磁盘容量和目录占用排行】", "文件系统："])
        for item in disk_space.get("filesystems", []):
            if item.get("status") == "ok":
                lines.append(
                    f"- {item['target']} ({item['fstype']}, {item['source']}): {format_bytes(item['used'])} / {format_bytes(item['total'])}, {item['used_percent']}%；inode {item['inode_used_percent']}%"
                )
            else:
                lines.append(f"- {item.get('target')}: 读取失败，{item.get('error')}")
        lines.append("目录占用排行：")
        for index, item in enumerate(disk_space.get("directory_ranking", []), 1):
            lines.append(
                f"{index}. {item['path']} {format_bytes(item['bytes'])}（扫描根 {item['scan_root']}，{item['fstype']}）"
            )
        lines.append("已跳过的挂载目录：")
        for item in disk_space.get("skipped_mounts", []):
            lines.append(f"- {item['target']} ({item['fstype']}): {item['reason']}")
        incomplete = [item for item in disk_space.get("scan_tasks", []) if item.get("status") != "ok"]
        if incomplete:
            lines.append("扫描不完整项：")
            for item in incomplete:
                lines.append(
                    f"- {item['root']}: 状态 {item['status']}，耗时 {item['duration_seconds']}s，错误 {len(item.get('errors', []))} 条"
                )

    disk_io = modules.get("disk_io")
    if disk_io:
        lines.extend(["", "【磁盘实时读写分析】"] )
        for item in disk_io.get("devices", []):
            details = (
                f"平均读 {format_bytes(item.get('average_read_bps', 0))}/s，平均写 {format_bytes(item.get('average_write_bps', 0))}/s，"
                f"读 IOPS {item.get('average_read_iops', 0):.2f}，写 IOPS {item.get('average_write_iops', 0):.2f}"
            )
            if item.get("util_percent") is not None:
                details += f"，利用率 {item['util_percent']:.2f}%，等待 {item.get('await_ms', 0):.2f}ms"
            lines.append(f"- {item['device']}: {details}")
        if disk_io.get("enhanced_error"):
            lines.append(f"增强指标：unknown（{disk_io['enhanced_error']}）")

    network = modules.get("network")
    if network:
        lines.extend(["", "【网络流量和网卡状态】"])
        for item in network.get("interfaces", []):
            errors = sum(safe_int(item.get(name)) for name in NET_COUNTER_NAMES[2:])
            lines.append(
                f"- {item['name']} ({item.get('type')}, {item.get('state')}, 链路 {item.get('link_speed')}): "
                f"平均接收 {format_bytes(item.get('average_rx_bps', 0))}/s，平均发送 {format_bytes(item.get('average_tx_bps', 0))}/s，"
                f"错误/丢包增量 {errors}，地址 {', '.join(item.get('addresses', [])) or 'unknown'}"
            )

    hardware = modules.get("hardware")
    if hardware:
        lines.extend(["", "【基础硬件健康信息】", f"CPU 型号：{hardware.get('cpu_model', 'unknown')}"] )
        for item in hardware.get("devices", []):
            temperature = f"，温度 {item['temperature']}℃" if item.get("temperature") is not None else "，温度 unknown"
            lines.append(
                f"- {item['device']} {item['model']} {item['type']} {format_bytes(item['capacity'])}，SMART {item['smart_status']}{temperature}"
            )

    for key, title in (("disk_benchmark", "磁盘性能测试"), ("speedtest", "外网速度测试")):
        active = modules.get(key)
        if active:
            lines.extend(["", f"【{title}】", json.dumps(active, ensure_ascii=False, indent=2)])

    lines.append("======================================================")
    return "\n".join(lines) + "\n"


def render_html(report: Dict[str, Any], text_report: Optional[str] = None) -> str:
    metadata = report["metadata"]
    issues = report.get("issues", [])
    summary = report.get("summary") or build_summary(report)
    summary_items = "".join(
        f"<li class='{html.escape(item['severity'])}'>【{severity_label(item['severity'])}】{html.escape(item['text'])}</li>"
        for item in summary.get("items", [])
    ) or f"<li class='ok'>{html.escape(summary.get('conclusion') or '服务运行正常，继续保持！')}</li>"
    summary_counts = (
        f"<p class='muted'>严重 {summary['counts']['critical']} · 警告 {summary['counts']['warning']} · 提示 {summary['counts']['info']}</p>"
        if summary.get("items")
        else ""
    )
    issue_rows = "".join(
        "<tr>"
        f"<td><span class='badge {html.escape(issue['severity'])}'>{severity_label(issue['severity'])}</span></td>"
        f"<td>{html.escape(issue['module'])}</td>"
        f"<td>{html.escape(issue['message'])}</td>"
        f"<td>{html.escape(issue['basis'])}</td>"
        f"<td>{html.escape(issue['suggestion'])}</td>"
        "</tr>"
        for issue in issues
    ) or "<tr><td colspan='5'>本次采样期间未发现达到已配置阈值的问题。</td></tr>"
    dependency_rows = "".join(
        "<tr>"
        f"<td>{html.escape(item['command'])}</td>"
        f"<td>{html.escape(item['status'])}</td>"
        f"<td>{html.escape(item['package'])}</td>"
        f"<td>{html.escape(', '.join(item.get('modules', [])))}</td>"
        f"<td>{html.escape(item.get('error') or '')}</td>"
        f"<td><code>{html.escape(item.get('manual_install_command') or '')}</code></td>"
        "</tr>"
        for item in report.get("dependencies", {}).get("tools", [])
    ) or "<tr><td colspan='6'>本次没有额外系统工具依赖。</td></tr>"
    module_cards = []
    for key, value in report.get("modules", {}).items():
        title = MODULE_BY_KEY.get(key, ("", key, False))[1]
        module_cards.append(
            f"<section><h2>{html.escape(title)} <small>{html.escape(str(value.get('status', 'unknown')))}</small></h2>"
            f"<pre>{html.escape(json.dumps(value, ensure_ascii=False, indent=2))}</pre></section>"
        )
    raw_text = text_report or render_text(report)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(metadata.get('hostname', 'unknown'))} - 服务器资源分析报告</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;background:#f4f6f8;color:#1f2937;margin:0}}
main{{max-width:1200px;margin:0 auto;padding:28px}}h1{{margin-bottom:6px}}.muted,small{{color:#6b7280}}
section{{background:#fff;border-radius:10px;padding:20px;margin:18px 0;box-shadow:0 1px 4px #00000012}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top}}
pre{{white-space:pre-wrap;word-break:break-word;background:#111827;color:#e5e7eb;padding:16px;border-radius:8px;overflow:auto}}
.badge{{padding:3px 8px;border-radius:999px;color:#fff}}.critical{{background:#dc2626}}.warning{{background:#d97706}}.info{{background:#2563eb}}
.summary{{list-style:disc;margin:8px 0 0 20px;padding:0}}.summary li{{margin:6px 0}}.summary li.critical{{color:#b91c1c}}.summary li.warning{{color:#b45309}}.summary li.info{{color:#1d4ed8}}.summary li.ok{{color:#15803d;font-weight:600}}
</style></head><body><main>
<h1>服务器资源分析报告</h1><p class="muted">{html.escape(metadata.get('hostname', 'unknown'))} · {html.escape(metadata.get('started_at', ''))} ~ {html.escape(metadata.get('finished_at', ''))}</p>
<section><h2>概要信息</h2>{summary_counts}<ul class="summary">{summary_items}</ul></section>
<section><h2>分析结论</h2><table><thead><tr><th>级别</th><th>模块</th><th>观察</th><th>依据</th><th>建议</th></tr></thead><tbody>{issue_rows}</tbody></table></section>
<section><h2>依赖工具</h2><p class="muted">包管理器：{html.escape(report.get('dependencies', {}).get('package_manager', 'unknown'))}</p><table><thead><tr><th>工具</th><th>状态</th><th>软件包</th><th>模块</th><th>错误</th><th>手动安装</th></tr></thead><tbody>{dependency_rows}</tbody></table></section>
{''.join(module_cards)}
<section><h2>文本报告</h2><pre>{html.escape(raw_text)}</pre></section>
</main></body></html>"""


def ensure_output_dir(preferred: str) -> Tuple[str, Optional[str]]:
    for path, reason in ((normalize_path(preferred), None), (FALLBACK_OUTPUT_DIR, f"默认输出目录 {preferred} 不可写")):
        try:
            os.makedirs(path, exist_ok=True)
            fd, probe = tempfile.mkstemp(prefix=".write-test-", dir=path)
            os.close(fd)
            os.remove(probe)
            return path, reason
        except OSError:
            continue
    raise OSError(f"无法写入报告目录 {preferred} 或 {FALLBACK_OUTPUT_DIR}")


def atomic_write(path: str, content: str) -> None:
    directory = os.path.dirname(path) or "."
    fd, temp_path = tempfile.mkstemp(prefix=f".{os.path.basename(path)}.", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
    except BaseException:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise


def save_reports(report: Dict[str, Any], output_dir: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    hostname = re.sub(r"[^A-Za-z0-9_.-]+", "_", report["metadata"].get("hostname", "unknown"))
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(output_dir, f"server_resource_report_{hostname}_{stamp}")
    text_content = render_text(report)
    json_content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    html_content = render_html(report, text_content)
    paths = {
        "txt": f"{base}.txt",
        "json": f"{base}.json",
        "html": f"{base}.html",
        "latest_json": os.path.join(output_dir, "server_resource_report_latest.json"),
    }
    contents = {
        "txt": text_content,
        "json": json_content,
        "html": html_content,
        "latest_json": json_content,
    }
    successful: Dict[str, str] = {}
    errors: Dict[str, str] = {}
    for label, path in paths.items():
        try:
            atomic_write(path, contents[label])
        except OSError as exc:
            errors[label] = str(exc)
        else:
            successful[label] = path
    if not any(label in successful for label in ("txt", "json", "html")):
        raise OSError("所有主要报告格式均写入失败：" + "；".join(f"{key}: {value}" for key, value in errors.items()))
    return successful, errors


def print_execution_summary(
    selected: Sequence[str], args: argparse.Namespace, output_dir: str, output_reason: Optional[str]
) -> None:
    show_info("")
    show_info("-----------------------")
    show_info("即将执行以下操作：")
    for index, key in enumerate(selected, 1):
        show_info(f"{index}. {MODULE_BY_KEY[key][1]}")
    show_info(f"采样时间：{args.sample_seconds} 秒，每 {args.sample_interval} 秒一次")
    show_info(f"目录扫描：{', '.join(args.scan_root)}，深度 {args.scan_depth}，单任务超时 {args.scan_timeout} 秒")
    show_info(f"报告输出：{output_dir}")
    if output_reason:
        show_info(f"输出回退：{output_reason}")
    show_info("主动测试：" + ("已选择并确认" if any(MODULE_BY_KEY[key][2] for key in selected) else "未启用"))
    show_info("-----------------------")


def print_dependency_summary(dependencies: Dict[str, Any]) -> None:
    tools = dependencies.get("tools", [])
    if not tools:
        return
    show_info("")
    show_info("-----------------------")
    show_info("依赖工具准备结果：")
    for item in tools:
        show_info(f"|- {item['command']}: {item['status']}（{item['package']}）")
        if item.get("error"):
            show_error(f"   错误：{item['error']}")
            show_error(f"   手动安装：{item['manual_install_command']}")
    show_info("-----------------------")


def collect_module(
    key: str,
    args: argparse.Namespace,
    report: Dict[str, Any],
    mounts: Sequence[Dict[str, str]],
    sampled: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    if key == "system":
        return collect_system()
    if key == "cpu":
        return sampled.get("cpu", {"status": "unknown", "error": "CPU 采样无结果"})
    if key == "memory":
        return collect_memory(args.top)
    if key == "disk_space":
        return collect_disk_space(
            args.scan_root, mounts, args.exclude_path, args.scan_depth, args.scan_timeout, args.top
        )
    if key == "disk_io":
        return enrich_disk_io(sampled.get("disk_io", {"status": "unknown", "error": "磁盘采样无结果"}))
    if key == "network":
        return enrich_network(sampled.get("network", {"status": "unknown", "error": "网络采样无结果"}))
    if key == "hardware":
        return collect_hardware()
    if key == "disk_benchmark":
        return run_disk_benchmark(args, mounts)
    if key == "speedtest":
        return run_speedtest()
    return {"status": "failed", "error": f"未知模块 {key}"}


def build_report(
    args: argparse.Namespace, selected: Sequence[str], skipped_modules: Dict[str, str], dependencies: Dict[str, Any]
) -> Dict[str, Any]:
    started_at = now_iso()
    system = collect_system()
    interfaces = [value.strip() for value in args.interfaces.split(",") if value.strip()] if args.interfaces else None
    mounts = discover_mounts()
    sampled = sample_resources(selected, args.sample_seconds, args.sample_interval, interfaces, args.top)
    report: Dict[str, Any] = {
        "metadata": {
            "hostname": system.get("hostname", "unknown"),
            "os": system.get("os", "unknown"),
            "kernel": system.get("kernel", "unknown"),
            "cpu_count": system.get("cpu_count", 0),
            "memory_total": system.get("memory_total", 0),
            "started_at": started_at,
            "finished_at": None,
            "sample_seconds": args.sample_seconds,
            "sample_interval": args.sample_interval,
        },
        "selected_modules": list(selected),
        "skipped_modules": dict(skipped_modules),
        "dependencies": dependencies,
        "modules": {},
        "issues": [],
    }
    for key in selected:
        label = MODULE_BY_KEY[key][1]
        show_info(f"|- 正在采集：{label}...")
        try:
            report["modules"][key] = collect_module(key, args, report, mounts, sampled)
        except KeyboardInterrupt:
            report["modules"][key] = {"status": "skipped", "error": "用户中断该模块"}
            show_error(f"|- {label} 已被用户中断，继续生成已有报告")
        except Exception as exc:  # 单模块故障隔离
            report["modules"][key] = {"status": "failed", "error": str(exc)}
            show_error(f"|- {label} 采集失败：{exc}")
        else:
            show_info(f"|- {label} 完成✅")
    for key, reason in skipped_modules.items():
        report["modules"][key] = {"status": "skipped", "error": reason}
    report["metadata"]["finished_at"] = now_iso()
    report["issues"] = analyze_report(report, args)
    return report


def print_final_summary(report: Dict[str, Any], paths: Dict[str, str], output_errors: Dict[str, str]) -> None:
    completed, skipped, failed = section_status_summary(report)
    incomplete_scans = [
        item
        for item in report.get("modules", {}).get("disk_space", {}).get("scan_tasks", [])
        if item.get("status") != "ok"
    ]
    residual_files = [
        value.get("residual_file")
        for value in report.get("modules", {}).values()
        if value.get("residual_file")
    ]
    show_info("")
    show_info("===========================执行完成✅==========================")
    show_info(f"|- 完成模块：{', '.join(completed) or '无'}")
    show_info(f"|- 跳过模块：{', '.join(skipped) or '无'}")
    show_info(f"|- 失败模块：{', '.join(failed) or '无'}")
    show_info(f"|- 问题数量：严重 {sum(1 for i in report['issues'] if i['severity'] == 'critical')}，警告 {sum(1 for i in report['issues'] if i['severity'] == 'warning')}，提示 {sum(1 for i in report['issues'] if i['severity'] == 'info')}")
    summary = report.get("summary") or build_summary(report)
    if summary.get("items"):
        show_info("|- 概要信息：")
        for item in summary["items"]:
            show_info(f"   - 【{severity_label(item['severity'])}】{item['text']}")
    else:
        show_info(f"|- 概要信息：{summary.get('conclusion') or '服务运行正常，继续保持！'}")
    dependency_failed = [item for item in report.get("dependencies", {}).get("tools", []) if item.get("status") == "failed"]
    show_info(f"|- 依赖工具：失败 {len(dependency_failed)} 项")
    for item in dependency_failed:
        show_error(f"   {item['command']} 请手动安装：{item['manual_install_command']}")
    for label, path in paths.items():
        show_info(f"|- {label}: {path}")
    for label, error in output_errors.items():
        show_error(f"|- {label} 写入失败：{error}")
    if incomplete_scans:
        show_error("|- 以下目录扫描不完整：" + ", ".join(item["root"] for item in incomplete_scans))
    if residual_files:
        show_error("|- 主动测试残留文件，请人工检查：" + ", ".join(residual_files))
    if report["issues"]:
        show_info("|- 下一步：先查看报告顶部的严重和警告项，再结合原始排行进一步定位。")
    else:
        show_info("|- 下一步：如问题具有间歇性，可在业务高峰期再次生成报告。")
    show_info("==============================================================")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_args(args)
        args.scan_root = [normalize_path(path) for path in (args.scan_root or ["/www"])]
        args.exclude_path = [normalize_path(path) for path in args.exclude_path]
        interactive = not args.non_interactive and sys.stdin.isatty()
        if args.modules is not None:
            selected = parse_modules(args.modules)
        elif interactive:
            selected = interactive_module_selection()
        else:
            selected = list(DEFAULT_MODULE_KEYS)
        selected, skipped = resolve_active_modules(
            selected, interactive, args.allow_disk_benchmark, args.allow_speedtest
        )
        output_dir, output_reason = ensure_output_dir(args.output_dir)
    except SelectionCancelled:
        show_info("已取消模块选择，本次未生成报告。")
        return 0
    except (ValueError, OSError) as exc:
        show_error(f"初始化失败：{exc}")
        return 1

    print_execution_summary(selected, args, output_dir, output_reason)
    dependencies = prepare_dependencies(selected)
    print_dependency_summary(dependencies)
    report = build_report(args, selected, skipped, dependencies)
    report["metadata"]["output_dir"] = output_dir
    report["metadata"]["output_fallback_reason"] = output_reason
    report["summary"] = build_summary(report)
    try:
        paths, output_errors = save_reports(report, output_dir)
    except OSError as exc:
        show_error(f"报告写入失败：{exc}")
        return 1
    print_final_summary(report, paths, output_errors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
