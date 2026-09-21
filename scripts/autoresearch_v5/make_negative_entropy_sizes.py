"""生成局部纠缠尺寸核验包，保留历史保存态。"""
import copy
import json
from pathlib import Path
from make_negative_phase_independent_pilot import ROOT, SOURCES, sha256, write_json

REL = 'results/autoresearch_v5_20260914/negative_entropy_sizes_r1'
RUN = ROOT / REL
LAUNCH = 'scripts/autoresearch_v5/launch_negative_entropy_sizes.sh'


def main():
    old = ROOT / 'results/autoresearch_v5_20260913/negative_phase_independent_pilot_r1/parameter-scan.run_spec.json'
    spec = copy.deepcopy(json.loads(old.read_text(encoding='utf-8')))
    spec['run_id'] = 'negative-entropy-sizes-r1-20260914'
    spec['scope'] = 'beta .25 localized entropy size check; no phase assigned; Fig.9 excluded'
    cells = []
    reused = []
    for alpha in (-.175, -.150, -.125, -.100):
        for length in (40, 60, 80):
            if length == 80 and alpha in (-.175, -.100):
                directory = ROOT / 'results/autoresearch_v5_20260913/negative_phase_independent_pilot_fetch_20260914_2243' / f'negdiag-a{round(abs(alpha)*10000):05d}-b02500-L080'
                reused.append({'alpha': alpha, 'beta': .25, 'L': length,
                               'path': str(directory.relative_to(ROOT)).replace('\\', '/'),
                               'manifest_sha256': sha256(directory / 'manifest.json')})
                continue
            cells.append({'cell_id': f'negsize-a{round(abs(alpha)*10000):05d}-b02500-L{length:03d}',
                          'params': {'alpha': alpha, 'beta': .25, 'L': length, 'n_units': length//5},
                          'budget': 64, 'stage': 'entropy-finite-size-r1'})
    assert len(cells) == 10 and len(reused) == 2
    spec['cells'] = cells
    spec['reused_cells'] = reused
    spec['settings']['maxdim_by_L'] = {'40': 1200, '60': 1200, '80': 1200}
    spec['acceptance']['phase_claim'] = 'finite-size diagnostic only; compare entropy, gap and bond observables; no q-peak-only phase claim'
    sources = [s for s in SOURCES if not s.endswith('launch_negative_phase_independent_pilot.sh')] + [LAUNCH, 'docs/pilot_entropy_closeout_decision_20260914.md']
    hashes = {s: sha256(ROOT / s) for s in sources}
    spec['provenance']['code_sha256'] = hashes
    spec['provenance']['parent_spec_sha256'] = sha256(old)
    spec['provenance']['user_authorized_upload_and_launch'] = 'ongoing campaign and active research closeout goal'
    if RUN.exists():
        raise FileExistsError(RUN)
    RUN.mkdir(parents=True)
    write_json(RUN / 'parameter-scan.run_spec.json', spec)
    (RUN / 'source_hashes.sha256').write_bytes(''.join(f'{h}  {s}\n' for s, h in hashes.items()).encode())
    contract = {'launch_ready': True, 'cell_count': 10, 'concurrency': 1, 'save_state': True,
                'enriched_diagnostics': True, 'stop_on_first_failure': True, 'eta_hours': [3, 5],
                'run_spec_sha256': sha256(RUN / 'parameter-scan.run_spec.json'),
                'standard_sha256': spec['provenance']['standard_sha256'],
                'manifest_sha256': sha256(ROOT / 'Manifest.toml')}
    write_json(RUN / 'launch-contract.json', contract)
    files = sources + [f'{REL}/{s}' for s in ('parameter-scan.run_spec.json', 'source_hashes.sha256', 'launch-contract.json')]
    write_json(RUN / 'server_upload_manifest.json', {'target': '/home/wangjieren/code/1x5_Heisenberg_Pentamer',
               'cell_count': 10, 'concurrency': 1, 'files': [{'path': s, 'sha256': sha256(ROOT/s), 'bytes': (ROOT/s).stat().st_size} for s in files]})
    print(f'PACKAGE_READY cells=10 reused=2 files={len(files)}')


if __name__ == '__main__':
    main()
