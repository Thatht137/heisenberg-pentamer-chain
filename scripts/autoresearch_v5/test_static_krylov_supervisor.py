#!/usr/bin/env python3
"""supervisor 的本地纯单测；合成进程对象，不启动 Julia。"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import static_krylov_supervisor as supervisor


class _FakeSignal:
    SIGTERM = signal.SIGTERM
    SIGINT = signal.SIGINT
    SIGHUP = getattr(signal, "SIGHUP", signal.SIGTERM)

    def __init__(self) -> None:
        self.handlers = {}

    def getsignal(self, signum):
        return self.handlers.get(signum)

    def signal(self, signum, handler):
        self.handlers[signum] = handler


class _FakeProcess:
    pid = 12345

    def __init__(self, mode: str, signal_api: _FakeSignal | None = None) -> None:
        self.mode = mode
        self.signal_api = signal_api
        self.wait_calls = 0
        self.terminated = False

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self.mode == "timeout" and self.wait_calls == 1:
            raise subprocess.TimeoutExpired(["fake"], timeout)
        if self.mode == "signal" and self.wait_calls == 1:
            self.signal_api.handlers[signal.SIGTERM](signal.SIGTERM, None)
        return 0

    def terminate(self):
        self.terminated = True


class SupervisorTests(unittest.TestCase):
    def _paths(self, directory: Path):
        return {
            "receipt": directory / "session.receipt",
            "pid_file": directory / "batch.pid",
            "status_file": directory / "supervisor_status.json",
            "timeout_file": directory / "batch.timeout",
        }

    def _run(self, process, directory: Path, *, signal_api=signal, terminator=None):
        paths = self._paths(directory)
        factory = lambda *_args, **_kwargs: process
        return supervisor.run_supervised(
            ["fake-worker"], cwd=directory, receipt=paths["receipt"], pid_file=paths["pid_file"],
            status_file=paths["status_file"], timeout_file=paths["timeout_file"], timeout=0.01,
            term_grace=0.01, popen_factory=factory, signal_api=signal_api, terminate_group=terminator,
        )

    def test_normal_completion_writes_receipts(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            process = _FakeProcess("normal")
            result = self._run(process, directory, terminator=lambda *_: None)
            self.assertEqual((result.status, result.returncode), ("completed", 0))
            self.assertEqual(json.loads((directory / "session.receipt").read_text())["pgid"], process.pid)
            self.assertTrue((directory / "supervisor_status.json").is_file())

    def test_timeout_marks_and_terminates_own_group(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            process = _FakeProcess("timeout")
            calls = []
            result = self._run(process, directory, terminator=lambda pgid, grace: calls.append((pgid, grace)))
            self.assertEqual((result.status, result.returncode), ("timed_out", 124))
            self.assertEqual(calls, [(process.pid, 0.01), (process.pid, 0.01)])
            self.assertTrue((directory / "batch.timeout").is_file())

    def test_parent_signal_cleans_child_group(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            fake_signal = _FakeSignal()
            process = _FakeProcess("signal", fake_signal)
            calls = []
            result = self._run(process, directory, signal_api=fake_signal, terminator=lambda pgid, grace: calls.append((pgid, grace)))
            self.assertEqual((result.status, result.returncode), ("terminated", 128 + signal.SIGTERM))
            self.assertEqual(calls, [(process.pid, 0.01), (process.pid, 0.01)])

    def test_receipt_write_failure_cleans_created_group(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            process = _FakeProcess("normal")
            paths = self._paths(directory)
            factory = lambda *_args, **_kwargs: process
            calls = []
            with mock.patch.object(supervisor, "_write_json", side_effect=OSError("receipt fault")):
                with self.assertRaises(OSError):
                    supervisor.run_supervised(
                        ["fake-worker"], cwd=directory, receipt=paths["receipt"], pid_file=paths["pid_file"],
                        status_file=paths["status_file"], timeout_file=paths["timeout_file"], popen_factory=factory,
                        terminate_group=lambda pgid, grace: calls.append((pgid, grace)),
                    )
            self.assertEqual(calls, [(process.pid, 60.0)])

    def test_term_then_kill_after_grace(self):
        alive = iter((True, True, True, False, True))
        calls = []
        result = supervisor._terminate_group(
            123, 0.1, group_alive=lambda _pgid: next(alive),
            kill_group=lambda pgid, signum: calls.append((pgid, signum)), sleep=lambda _seconds: None,
            monotonic=iter((0.0, 0.2, 0.2)).__next__,
        )
        self.assertTrue(result)
        self.assertEqual(calls, [(123, signal.SIGTERM), (123, getattr(signal, "SIGKILL", 9))])


@unittest.skipUnless(os.name == "posix", "POSIX 进程组集成测试在 Windows 跳过")
class PosixIntegrationTests(unittest.TestCase):
    _TERM_CODE = (
        "import os,signal,sys,time\n"
        "ready=sys.argv[1]\n"
        "marker=sys.argv[2]\n"
        "pid_path=sys.argv[3]\n"
        "open(pid_path,'w',encoding='utf-8').write(str(os.getpid()))\n"
        "def h(*_):\n"
        "    open(marker,'w',encoding='utf-8').write('term')\n"
        "    raise SystemExit(0)\n"
        "signal.signal(signal.SIGTERM,h)\n"
        "open(ready,'w',encoding='utf-8').write('ready')\n"
        "time.sleep(30)\n"
    )

    def _paths(self, directory: Path):
        return {
            "receipt": directory / "session.receipt",
            "pid_file": directory / "batch.pid",
            "status_file": directory / "supervisor_status.json",
            "timeout_file": directory / "batch.timeout",
        }

    def _run(self, directory: Path, code: str, args=(), **kwargs):
        paths = self._paths(directory)
        return supervisor.run_supervised(
            [sys.executable, "-c", code, *args], cwd=directory,
            receipt=paths["receipt"], pid_file=paths["pid_file"],
            status_file=paths["status_file"], timeout_file=paths["timeout_file"],
            **kwargs,
        )

    def _wait_marker(self, path: Path):
        for _ in range(100):
            if path.exists():
                return
            time.sleep(0.05)
        self.fail(f"未收到清理标记：{path}")

    def _wait_stopped(self, pid_path: Path):
        pid = int(pid_path.read_text(encoding="utf-8"))
        for _ in range(20):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            state_path = Path(f"/proc/{pid}/stat")
            if state_path.is_file() and state_path.read_text(encoding="utf-8").split()[2] == "Z":
                return
            time.sleep(0.05)
        self.fail(f"子进程仍存活：{pid}")

    def test_real_normal_completion(self):
        with tempfile.TemporaryDirectory() as raw:
            result = self._run(Path(raw), "raise SystemExit(0)", timeout=1, term_grace=0.5)
            self.assertEqual((result.status, result.returncode), ("completed", 0))

    def test_real_timeout(self):
        with tempfile.TemporaryDirectory() as raw:
            result = self._run(Path(raw), "import time; time.sleep(30)", timeout=0.2, term_grace=0.5)
            self.assertEqual((result.status, result.returncode), ("timed_out", 124))

    def test_real_leader_exit_cleans_descendant(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            marker = directory / "term.marker"
            ready = directory / "ready.marker"
            pid_path = directory / "child.pid"
            code = (
                "import subprocess,sys\n"
                f"child=subprocess.Popen([sys.executable,'-c',{self._TERM_CODE!r},r'{ready}',r'{marker}',r'{pid_path}'])\n"
                "import time\n"
                "deadline=time.time()+1\n"
                "while not __import__('os').path.exists(r'" + str(ready) + "') and time.time()<deadline: time.sleep(0.01)\n"
                "assert __import__('os').path.exists(r'" + str(ready) + "')\n"
            )
            result = self._run(directory, code, timeout=1, term_grace=0.5)
            self.assertEqual((result.status, result.returncode), ("completed", 0))
            self._wait_marker(marker)
            self._wait_stopped(pid_path)

    def test_real_receipt_fault_cleans_child(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            marker = directory / "term.marker"
            ready = directory / "ready.marker"
            pid_path = directory / "child.pid"
            bad_receipt = directory / "missing" / "session.receipt"
            paths = self._paths(directory)
            def factory(*args, **kwargs):
                process = subprocess.Popen(*args, **kwargs)
                self._wait_marker(ready)
                return process
            with self.assertRaises(FileNotFoundError):
                supervisor.run_supervised(
                    [sys.executable, "-c", self._TERM_CODE, str(ready), str(marker), str(pid_path)], cwd=directory,
                    receipt=bad_receipt, pid_file=paths["pid_file"], status_file=paths["status_file"],
                    timeout_file=paths["timeout_file"], timeout=1, term_grace=0.5, popen_factory=factory,
                )
            self._wait_marker(marker)
            self._wait_stopped(pid_path)


if __name__ == "__main__":
    unittest.main()
