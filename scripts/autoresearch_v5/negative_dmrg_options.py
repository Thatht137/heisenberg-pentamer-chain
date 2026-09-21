"""负区 DMRG 的显式局部求解参数。"""

from __future__ import annotations

import argparse
import re


EIGSOLVE_KRYLOVDIM_DEFAULT = 3
EIGSOLVE_KRYLOVDIM_MIN = 3
EIGSOLVE_KRYLOVDIM_MAX = 32
EIGSOLVE_MAXITER = 1
EIGSOLVE_TOL = 1.0e-14


def validate_krylovdim(value: object) -> int:
    """只接受 JSON/程序接口中的严格整数。"""
    if isinstance(value, bool) or type(value) is not int:
        raise ValueError("eigsolve_krylovdim 必须是整数，不能是 bool 或浮点数")
    if not EIGSOLVE_KRYLOVDIM_MIN <= value <= EIGSOLVE_KRYLOVDIM_MAX:
        raise ValueError("eigsolve_krylovdim 必须位于 [3,32]")
    return value


def parse_krylovdim_arg(value: str) -> int:
    """解析命令行整数，不静默截断小数。"""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
        raise argparse.ArgumentTypeError("eigsolve_krylovdim 必须是十进制整数")
    try:
        parsed = int(value, 10)
    except ValueError as error:
        raise argparse.ArgumentTypeError("eigsolve_krylovdim 不是有效整数") from error
    try:
        return validate_krylovdim(parsed)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
