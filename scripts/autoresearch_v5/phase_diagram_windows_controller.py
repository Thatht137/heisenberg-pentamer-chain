#!/usr/bin/env python3
"""在 Windows 上调用上游 phase-diagram 控制器。"""

from __future__ import annotations

import msvcrt
import os
import runpy
import sys
import types
from pathlib import Path


def _lock(fd: int, operation: int) -> None:
    """用 msvcrt 提供上游所需的独占锁。"""
    if operation != 1:
        return
    os.lseek(fd, 0, os.SEEK_SET)
    try:
        os.write(fd, b"0")
    except OSError:
        pass
    os.lseek(fd, 0, os.SEEK_SET)
    msvcrt.locking(fd, msvcrt.LK_LOCK, 1)


def main() -> None:
    skill_script = (
        Path.home()
        / ".codex"
        / "skills"
        / "phase-diagram"
        / "scripts"
        / "phase_diagram.py"
    )
    if not skill_script.is_file():
        raise SystemExit(f"找不到 phase-diagram Skill: {skill_script}")
    shim = types.ModuleType("fcntl")
    shim.LOCK_EX = 1
    shim.flock = _lock
    sys.modules["fcntl"] = shim
    runpy.run_path(str(skill_script), run_name="__main__")


if __name__ == "__main__":
    main()
