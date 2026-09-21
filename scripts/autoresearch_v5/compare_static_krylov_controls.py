"""比较同一物理点的两份 Krylov 对照观测；结果只标记为 audit_only。"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any, Mapping, Sequence


PAIR_FIELDS = ("alpha", "beta", "L", "start", "observable", "index")
RECORD_FIELDS = PAIR_FIELDS + ("value",)
KRYLOV_FIELD = "eigsolve_krylovdim"


def _finite_real(value: Any, label: str) -> float:
    """拒绝 bool、非数值和非有限值。"""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label} 必须是有限实数")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} 必须是有限实数")
    return number


def _strict_equal(left: Any, right: Any) -> bool:
    """递归比较 metadata，避免 1 与 True 静默相等。"""
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return (set(left) == set(right)
                and all(_strict_equal(left[key], right[key]) for key in left))
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(
            _strict_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def _normalise_record(record: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError(f"{label} 必须是对象")
    if set(record) != set(RECORD_FIELDS):
        missing = sorted(set(RECORD_FIELDS) - set(record))
        extra = sorted(set(record) - set(RECORD_FIELDS))
        raise ValueError(f"{label} 字段不完整：missing={missing}, extra={extra}")
    alpha = _finite_real(record["alpha"], f"{label}.alpha")
    beta = _finite_real(record["beta"], f"{label}.beta")
    if isinstance(record["L"], bool) or type(record["L"]) is not int:
        raise ValueError(f"{label}.L 必须是整数")
    if isinstance(record["index"], bool) or type(record["index"]) is not int:
        raise ValueError(f"{label}.index 必须是整数")
    if record["L"] <= 0 or record["index"] < 0:
        raise ValueError(f"{label}.L/index 范围错误")
    for field in ("start", "observable"):
        if not isinstance(record[field], str) or not record[field]:
            raise ValueError(f"{label}.{field} 必须是非空字符串")
    value = _finite_real(record["value"], f"{label}.value")
    return {
        "alpha": alpha,
        "beta": beta,
        "L": record["L"],
        "start": record["start"],
        "observable": record["observable"],
        "index": record["index"],
        "value": value,
    }


def _key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(record[field] for field in PAIR_FIELDS)


def _records_by_key(records: Sequence[Mapping[str, Any]], label: str) -> dict[tuple[Any, ...], dict[str, Any]]:
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise ValueError(f"{label} 必须是 records 序列")
    if not records:
        raise ValueError(f"{label} records 不能为空")
    indexed: dict[tuple[Any, ...], dict[str, Any]] = {}
    for number, record in enumerate(records):
        normalized = _normalise_record(record, f"{label}[{number}]")
        key = _key(normalized)
        if key in indexed:
            raise ValueError(f"{label} 存在重复完整 key：{key}")
        indexed[key] = normalized
    return indexed


def _validate_metadata(metadata: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(metadata, Mapping):
        raise ValueError(f"{label} metadata 必须是对象")
    if KRYLOV_FIELD not in metadata:
        raise ValueError(f"{label} metadata 缺少 {KRYLOV_FIELD}")
    value = metadata[KRYLOV_FIELD]
    if isinstance(value, bool) or type(value) is not int or not 3 <= value <= 32:
        raise ValueError(f"{label}.{KRYLOV_FIELD} 必须是 [3,32] 整数")
    return dict(metadata)


def _check_metadata(baseline: Mapping[str, Any], candidate: Mapping[str, Any]) -> None:
    baseline_keys = set(baseline) - {KRYLOV_FIELD}
    candidate_keys = set(candidate) - {KRYLOV_FIELD}
    if baseline_keys != candidate_keys:
        raise ValueError("固定参数 metadata 字段集合不一致")
    for field in sorted(baseline_keys):
        if not _strict_equal(baseline[field], candidate[field]):
            raise ValueError(f"固定参数 metadata 不一致：{field}")
    if baseline[KRYLOV_FIELD] != 3 or candidate[KRYLOV_FIELD] != 8:
        raise ValueError("本比较器只接受 eigsolve_krylovdim 3 -> 8")


def _symmetric_relative_delta(old: float, new: float) -> float | None:
    denominator = abs(new) + abs(old)
    if denominator == 0.0:
        return None
    return 2.0 * (new - old) / denominator


def compare_records(
    baseline_records: Sequence[Mapping[str, Any]],
    candidate_records: Sequence[Mapping[str, Any]],
    baseline_metadata: Mapping[str, Any],
    candidate_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """逐完整 key 配对并计算漂移；不作收敛或相判定。"""
    baseline = _records_by_key(baseline_records, "baseline")
    candidate = _records_by_key(candidate_records, "candidate")
    baseline_meta = _validate_metadata(baseline_metadata, "baseline")
    candidate_meta = _validate_metadata(candidate_metadata, "candidate")
    _check_metadata(baseline_meta, candidate_meta)

    missing = sorted(set(baseline) - set(candidate))
    extra = sorted(set(candidate) - set(baseline))
    if missing or extra:
        raise ValueError(f"records key 不完整配对：missing={missing}, extra={extra}")

    rows = []
    for key in sorted(baseline):
        old = baseline[key]["value"]
        new = candidate[key]["value"]
        signed = new - old
        row = {field: baseline[key][field] for field in PAIR_FIELDS}
        row.update({
            "baseline_value": old,
            "candidate_value": new,
            "signed_delta": signed,
            "abs_delta": abs(signed),
            "symmetric_relative_delta": _symmetric_relative_delta(old, new),
        })
        rows.append(row)
    return {
        "schema_version": 1,
        "status": "audit_only",
        "comparison_count": len(rows),
        "krylov_change": {"baseline": 3, "candidate": 8},
        "records": rows,
    }


__all__ = ["compare_records", "KRYLOV_FIELD", "PAIR_FIELDS", "RECORD_FIELDS"]
