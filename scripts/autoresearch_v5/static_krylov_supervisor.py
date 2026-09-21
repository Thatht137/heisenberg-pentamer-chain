#!/usr/bin/env python3
"""在独立进程组内运行 batch，并可靠清理超时或孤儿。"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


class SupervisorError(RuntimeError):
    """启动或进程组安全校验失败。"""


class _SupervisorSignal(Exception):
    def __init__(self, signum: int) -> None:
        super().__init__(f"收到信号 {signum}")
        self.signum = signum


@dataclass(frozen=True)
class RunResult:
    returncode: int
    status: str
    pid: int
    pgid: int


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    """原子写入小型状态文件。"""
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _touch(path: Path) -> None:
    path.write_text("\n", encoding="utf-8")


def _group_alive(pgid: int) -> bool:
    killpg = getattr(os, "killpg", None)
    if killpg is None:
        return False
    try:
        killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_group(
    pgid: int,
    grace: float,
    *,
    group_alive: Callable[[int], bool] = _group_alive,
    kill_group: Callable[[int, int], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> bool:
    """只对已经证明归属的 PGID 发 TERM，超时后发 KILL。"""
    if kill_group is None:
        kill_group = getattr(os, "killpg", None)
    if kill_group is None or pgid <= 1 or not group_alive(pgid):
        return False
    try:
        kill_group(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    deadline = monotonic() + max(0.0, grace)
    while group_alive(pgid) and monotonic() < deadline:
        sleep(min(0.25, max(0.0, deadline - monotonic())))
    if group_alive(pgid):
        try:
            kill_group(pgid, getattr(signal, "SIGKILL", 9))
        except ProcessLookupError:
            pass
        return True
    return False


def _individual_stop(process: Any, grace: float) -> None:
    """PGID 未证明时只停止已知 child，不向未知组发信号。"""
    try:
        process.terminate()
    except (OSError, AttributeError):
        return
    try:
        process.wait(timeout=max(0.0, grace))
    except (subprocess.TimeoutExpired, OSError, AttributeError):
        pass


def run_supervised(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    receipt: Path,
    pid_file: Path,
    status_file: Path,
    timeout_file: Path,
    timeout: float = 7200.0,
    term_grace: float = 60.0,
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    signal_api: Any = signal,
    terminate_group: Callable[[int, float], Any] | None = None,
) -> RunResult:
    """运行一个 batch；start_new_session 证明 child.pid 即其 PGID。"""
    argv = [str(item) for item in command]
    if not argv:
        raise SupervisorError("空 command")
    if timeout <= 0 or term_grace < 0:
        raise SupervisorError("timeout/grace 必须为正")
    if terminate_group is None and not hasattr(os, "killpg"):
        raise SupervisorError("supervisor 只支持 POSIX 进程组")
    terminate = terminate_group or (lambda pgid, grace: _terminate_group(pgid, grace))
    handles: list[Any] = []
    process: Any | None = None
    proven_pgid: int | None = None
    group_cleaned = False
    try:
        stdout = subprocess.DEVNULL
        stderr = subprocess.DEVNULL
        if stdout_path is not None:
            handles.append(stdout_path.open("ab"))
            stdout = handles[-1]
        if stderr_path is not None:
            handles.append(stderr_path.open("ab"))
            stderr = handles[-1]
        process = popen_factory(
            argv,
            cwd=str(cwd) if cwd is not None else None,
            env=dict(env) if env is not None else None,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
            close_fds=True,
        )
        pid = int(process.pid)
        # POSIX start_new_session=True 保证 child.pid 是新 session/PGID，避免 leader 短命查询竞态。
        pgid = pid
        if pgid <= 1:
            _individual_stop(process, term_grace)
            raise SupervisorError("child pid 不可作为独立 PGID")
        proven_pgid = pgid

        started = time.time()
        _write_json(receipt, {"schema_version": 1, "pid": pid, "pgid": pgid, "started_at": started, "command": argv})
        _write_json(pid_file, {"schema_version": 1, "pid": pid, "pgid": pgid, "receipt": receipt.name})

        old_handlers: dict[int, Any] = {}
        for signum in (getattr(signal_api, "SIGTERM", None), getattr(signal_api, "SIGINT", None), getattr(signal_api, "SIGHUP", None)):
            if signum is None:
                continue
            old_handlers[signum] = signal_api.getsignal(signum)
            signal_api.signal(signum, lambda received, _frame: (_ for _ in ()).throw(_SupervisorSignal(int(received))))

        result_status = "completed"
        returncode = 1
        try:
            try:
                returncode = int(process.wait(timeout=timeout))
            except subprocess.TimeoutExpired:
                result_status = "timed_out"
                _touch(timeout_file)
                terminate(pgid, term_grace)
                try:
                    process.wait(timeout=max(0.0, term_grace))
                except (subprocess.TimeoutExpired, OSError):
                    pass
                returncode = 124
            except _SupervisorSignal as error:
                result_status = "terminated"
                terminate(pgid, term_grace)
                try:
                    process.wait(timeout=max(0.0, term_grace))
                except (subprocess.TimeoutExpired, OSError):
                    pass
                returncode = 128 + error.signum
        finally:
            for signum, handler in old_handlers.items():
                signal_api.signal(signum, handler)
            # 正常 parent 退出后仍可能留有孤儿，仍清理已证明的自有 PGID。
            terminate(pgid, term_grace)
            group_cleaned = True

        result = RunResult(returncode, result_status, pid, pgid)
        _write_json(
            status_file,
            {
                "schema_version": 1,
                "status": result.status,
                "returncode": result.returncode,
                "pid": result.pid,
                "pgid": result.pgid,
                "finished_at": time.time(),
            },
        )
        return result
    finally:
        # Popen 后任何 receipt/handler/status 异常都不能留下 child 或孤儿。
        if process is not None and proven_pgid is not None and not group_cleaned:
            try:
                terminate(proven_pgid, term_grace)
            except Exception:
                pass
        elif process is not None:
            _individual_stop(process, term_grace)
        for handle in handles:
            handle.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--pid-file", type=Path, required=True)
    parser.add_argument("--status-file", type=Path, required=True)
    parser.add_argument("--timeout-file", type=Path, required=True)
    parser.add_argument("--stdout", type=Path)
    parser.add_argument("--stderr", type=Path)
    parser.add_argument("--timeout", type=float, default=7200.0)
    parser.add_argument("--term-grace", type=float, default=60.0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command.pop(0)
    if not command:
        parser.error("缺少 command")
    try:
        result = run_supervised(
            command,
            cwd=args.cwd,
            receipt=args.receipt,
            pid_file=args.pid_file,
            status_file=args.status_file,
            timeout_file=args.timeout_file,
            stdout_path=args.stdout,
            stderr_path=args.stderr,
            timeout=args.timeout,
            term_grace=args.term_grace,
        )
    except (OSError, SupervisorError) as error:
        print(f"SUPERVISOR_REJECTED: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"status": result.status, "returncode": result.returncode, "pid": result.pid, "pgid": result.pgid}, ensure_ascii=False))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
