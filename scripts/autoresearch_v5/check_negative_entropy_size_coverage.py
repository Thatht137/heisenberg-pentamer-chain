"""核对尺寸核验的全部点，缺失与失败均保留。"""
import argparse
import json
from pathlib import Path

from validate_negative_phase_run_practical_v2 import validate, sha256

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / 'results/autoresearch_v5_20260914/negative_entropy_sizes_r1/parameter-scan.run_spec.json'
OLD_SPEC = ROOT / 'results/autoresearch_v5_20260913/negative_phase_independent_pilot_r1/parameter-scan.run_spec.json'


def inspect(path, spec, pinned=None):
    if not (path / 'manifest.json').is_file():
        return {'status': 'missing', 'path': str(path)}
    try:
        if pinned is not None and sha256(path / 'manifest.json') != pinned:
            return {'status': 'fail', 'path': str(path), 'failures': ['复用 manifest 哈希改变']}
        result = validate(path, spec)
        for mode in ('center', 'ferro_j2'):
            for name in ('state_sz0.jld2', 'entropy_profile_full.csv', 'bond_bond_connected.csv'):
                if not (path / f'start_{mode}' / name).is_file():
                    result['failures'].append(f'缺少保存态诊断文件 {mode}/{name}')
        if result['failures']:
            result['status'] = 'fail'
        return result
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {'status': 'fail', 'path': str(path), 'failures': [str(error)]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetched-cells', type=Path, default=SPEC.parent / 'cells')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError('拒绝覆盖验收快照')
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    results = []
    for cell in spec['cells']:
        result = inspect(args.fetched_cells / cell['cell_id'], SPEC)
        results.append({'params': cell['params'], 'origin': 'new', 'validation': result})
    for cell in spec['reused_cells']:
        result = inspect(ROOT / cell['path'], OLD_SPEC, cell['manifest_sha256'])
        results.append({'params': {key: cell[key] for key in ('alpha', 'beta', 'L')},
                        'origin': 'reused', 'validation': result})
    keys = {(x['params']['alpha'], x['params']['beta'], x['params']['L']) for x in results}
    expected = {(a, .25, length) for a in (-.175, -.150, -.125, -.100) for length in (40, 60, 80)}
    if len(results) != 12 or keys != expected:
        raise ValueError('尺寸网格不是完整唯一的十二点')
    counts = {state: sum(x['validation']['status'] == state for x in results) for state in ('pass', 'fail', 'missing')}
    summary = {'counts': counts, 'complete': counts['pass'] == 12, 'phase_assigned': False,
               'note': '本地验收不代替远端 checksum 与非覆盖回传回执；complete 只指网格数值验收，不代表相已确认。',
               'run_spec_sha256': sha256(SPEC), 'results': results}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
