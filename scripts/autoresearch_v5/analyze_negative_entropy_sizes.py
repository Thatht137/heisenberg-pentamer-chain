"""统一分析已验收的尺寸剖面，保留缺失点。"""
import argparse
import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np

from audit_pilot_entropy_robustness import fit, self_test, WINDOWS
from check_negative_entropy_size_coverage import SPEC, OLD_SPEC
from validate_negative_phase_run_practical_v2 import validate, sha256


def exact_integer(value, field):
    """只接受可精确表示为整数的数值，拒绝布尔和小数截断。"""
    if isinstance(value, bool) or value is None or value == '':
        raise ValueError(f'{field} 不是整数')
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f'{field} 不是整数') from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f'{field} 不是精确整数')
    return int(number)


def normalize_params(params):
    """规范物理尺寸参数，并补齐可由 L 唯一确定的单元数。"""
    normalized = dict(params)
    try:
        length = exact_integer(normalized['L'], 'L')
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('缺少有效 L') from exc
    if length <= 0 or length % 5:
        raise ValueError('L 必须为正的五倍数')
    raw_units = normalized.get('n_units')
    if raw_units in (None, ''):
        units = length // 5
    else:
        try:
            units = exact_integer(raw_units, 'n_units')
        except (TypeError, ValueError) as exc:
            raise ValueError('n_units 不是整数') from exc
        if units != length // 5:
            raise ValueError('n_units 与 L/5 不一致')
    normalized['L'] = length
    normalized['n_units'] = units
    return normalized


def check_coverage_grid(coverage):
    # 不把重复记录误认为十二个独立点。
    keys = []
    for item in coverage['results']:
        params = normalize_params(item['params'])
        validation_params = item.get('validation', {}).get('params')
        if validation_params is not None and normalize_params(validation_params) != params:
            raise ValueError('顶层 params 与 validation.params 不一致')
        item['params'] = params
        keys.append((params['alpha'], params['beta'], params['L']))
    expected = {(a, .25, length) for a in (-.175, -.150, -.125, -.100)
                for length in (40, 60, 80)}
    if len(keys) != 12 or set(keys) != expected:
        raise ValueError('分析输入不是完整唯一的十二点网格')


def analyze_profile(path, length):
    with path.open(newline='', encoding='utf-8') as handle:
        data = list(csv.DictReader(handle))
    if [int(r['bond']) for r in data] != list(range(1, length)):
        raise ValueError('纠缠切口不完整或重复')
    bonds = np.array([int(r['bond']) for r in data])
    x = np.array([float(r['log_chord']) for r in data])
    y = np.array([float(r['entropy']) for r in data])
    expected = np.log(2 * length / np.pi * np.sin(np.pi * bonds / length))
    if not np.all(np.isfinite(y)) or not np.allclose(x, expected, rtol=1e-10, atol=1e-12):
        raise ValueError('纠缠值非有限或弦长与尺寸不一致')
    result = []
    for window in WINDOWS:
        keep = (bonds >= window * length) & (bonds <= (1-window) * length)
        for period in (5, 10):
            result.append({'window': window, 'period': period,
                           **fit(x[keep], y[keep], bonds[keep] % period)})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--coverage', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError('拒绝覆盖分析结果')
    self_test()
    coverage = json.loads(args.coverage.read_text(encoding='utf-8'))
    check_coverage_grid(coverage)
    if coverage['run_spec_sha256'] != sha256(SPEC):
        raise ValueError('coverage 对应的运行配置已改变')
    rows, statuses, sources = [], [], []
    observables, connected, bonds = [], [], []
    for item in coverage['results']:
        old = item['validation']
        params = item['params']
        state = old['status']
        if state != 'pass':
            statuses.append({'params': params, 'status': state})
            continue
        directory = Path(old['run_dir'])
        spec = OLD_SPEC if item['origin'] == 'reused' else SPEC
        fresh = validate(directory, spec)
        if fresh['status'] != 'pass':
            statuses.append({'params': params, 'status': 'failed_revalidation', 'failures': fresh['failures']})
            continue
        sources.append({'manifest': str(directory / 'manifest.json'), 'sha256': sha256(directory / 'manifest.json')})
        for mode in ('center', 'ferro_j2'):
            child = directory / f'start_{mode}'
            profile = child / 'entropy_profile_full.csv'
            sources.append({'profile': str(profile), 'sha256': sha256(profile)})
            for row in analyze_profile(profile, int(params['L'])):
                rows.append({**params, 'initial_state': mode, **row})
            manifest = json.loads((child / 'manifest.json').read_text(encoding='utf-8'))
            measured = manifest['observables']
            diagnostics = manifest['diagnostics']
            observables.append({**params, 'initial_state': mode,
                                'energy_per_site': measured['energy_sz0'] / params['L'],
                                'spin_gap': measured['spin_gap'],
                                'q_peak_over_pi': measured['structure_factor_peak_q_over_pi'],
                                'variance_sz0_per_site': diagnostics['variance_per_site_sz0'],
                                'variance_sz1_per_site': diagnostics['variance_per_site_sz1']})
            # 保留符号和距离，不把小尾部直接解释为无序。
            for filename, target in [('bond_bond_connected.csv', connected), ('bond_correlations.csv', bonds)]:
                path = child / filename
                sources.append({'profile': str(path), 'sha256': sha256(path)})
                with path.open(encoding='utf-8', newline='') as handle:
                    for measurement in csv.DictReader(handle):
                        value_key = 'connected' if filename == 'bond_bond_connected.csv' else 'correlation'
                        if not np.isfinite(float(measurement[value_key])):
                            raise ValueError('非有限键关联')
                        record = {**params, 'initial_state': mode, **measurement}
                        if 'distance_units' in measurement:
                            record['distance_over_units'] = float(measurement['distance_units']) / (params['L'] / 5)
                        target.append(record)
        statuses.append({'params': params, 'status': 'analyzed'})
    args.out.mkdir(parents=True)
    derived_outputs = []
    if rows:
        path = args.out / 'entropy_fits.csv'
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        derived_outputs.append({'name': path.name, 'path': str(path.resolve()), 'sha256': sha256(path)})
    for name, records in [('observables.csv', observables), ('connected_bonds.csv', connected), ('bond_expectations.csv', bonds)]:
        if records:
            path = args.out / name
            with path.open('w', newline='', encoding='utf-8') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(records[0]))
                writer.writeheader()
                writer.writerows(records)
            derived_outputs.append({'name': path.name, 'path': str(path.resolve()), 'sha256': sha256(path)})
    count = sum(r['status'] == 'analyzed' for r in statuses)
    summary = {'analyzed_points': count, 'planned_points': len(statuses), 'fits': len(rows),
               'finite_size_comparison_ready': count == 12 and len(statuses) == 12,
               'phase_assigned': False, 'statuses': statuses, 'sources': sources,
               'derived_outputs': derived_outputs,
               'analysis_script': {'path': str(Path(__file__).resolve()),
                                   'sha256': sha256(Path(__file__))},
               'coverage': {'path': str(args.coverage.resolve()),
                            'sha256': sha256(args.coverage),
                            'run_spec_sha256': coverage.get('run_spec_sha256')},
               'run_spec_sha256': coverage.get('run_spec_sha256'),
               'limitations': ['single-size entries do not establish scaling',
                               'c_eff is diagnostic, not thermodynamic central charge',
                               'window and start ranges are not confidence intervals']}
    (args.out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ('analyzed_points', 'planned_points', 'fits', 'finite_size_comparison_ready')}))


if __name__ == '__main__':
    main()
