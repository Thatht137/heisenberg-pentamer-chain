#!/usr/bin/env python3
"""为长计算写入可读的原子 progress.json。"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


Probe = Callable[[], dict[str, object]]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProgressWriter:
    """周期性写入状态；probe 只读日志和输出目录。"""

    def __init__(
        self,
        outdir: Path,
        initial: dict[str, object],
        *,
        probe: Probe | None = None,
        interval_seconds: float = 30.0,
    ) -> None:
        self.outdir = Path(outdir)
        self.path = self.outdir / "progress.json"
        self._state = dict(initial)
        self._probe = probe
        self._interval = interval_seconds
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started_monotonic = time.monotonic()
        self._started_at = now_utc()
        self._terminal = False

    def update(self, **fields: object) -> None:
        with self._lock:
            self._state.update(fields)

    def _snapshot(self) -> dict[str, object]:
        with self._lock:
            state = dict(self._state)
        if self._probe is not None:
            try:
                state.update(self._probe())
            except Exception as error:  # 进度不能阻断主计算
                state["probe_error"] = f"{type(error).__name__}: {error}"
        state.update(
            {
                "schema_version": 1,
                "started_at": self._started_at,
                "updated_at": now_utc(),
                "elapsed_seconds": round(time.monotonic() - self._started_monotonic, 3),
            }
        )
        return state

    def _write(self) -> None:
        payload = self._snapshot()
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            self._write()
        self._write()

    def start(self) -> None:
        self.outdir.mkdir(parents=True, exist_ok=True)
        self.update(status="running")
        self._write()
        self._thread = threading.Thread(target=self._run, name="progress-heartbeat", daemon=True)
        self._thread.start()

    def finish(self, *, status: str, returncode: int | None = None, **fields: object) -> None:
        if self._terminal:
            return
        self.update(status=status, finished_at=now_utc(), **fields)
        if returncode is not None:
            self.update(returncode=returncode)
        self._terminal = True
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self._interval + 1.0, 2.0))
        self._write()

