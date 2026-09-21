"""复核保存态纠缠拟合，不按拟合优度筛选数据。"""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'results/autoresearch_v5_20260913/negative_phase_independent_pilot_fetch_20260914_2243'
OUT = ROOT / 'results/autoresearch_v5_20260913/pilot_entropy_robustness_20260914'
WINDOWS = (0.10, 0.15, 0.20, 0.25)


def fit(x, y, groups):
    labels = sorted(set(groups))
    design = np.column_stack([x] + [np.asarray(groups) == k for k in labels])
    coef, _, rank, singular = np.linalg.lstsq(design, y, rcond=None)
    if rank != design.shape[1]:
        raise ValueError('拟合矩阵秩不足')
    residual = y - design @ coef
    return {'c_eff': float(6 * coef[0]), 'rmse': float(np.sqrt(np.mean(residual ** 2))),
            'rank': int(rank), 'n': len(x), 'condition': float(singular[0] / singular[-1])}


def self_test():
    x = np.linspace(1, 4, 80)
    groups = np.arange(80) % 10
    y = 0.7 * x / 6 + groups * 0.13
    assert abs(fit(x, y, groups)['c_eff'] - 0.7) < 1e-12
    try:
        fit(np.ones(20), np.ones(20), np.zeros(20))
    except ValueError:
        pass
    else:
        raise AssertionError('未拒绝退化矩阵')


def main():
    self_test()
    rows, sources = [], []
    for cell in sorted(SOURCE.glob('negdiag-*')):
        for start in ('start_center', 'start_ferro_j2'):
            path = cell / start / 'entropy_profile_full.csv'
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            expected = [line.split()[0] for line in (path.parent / 'checksums.sha256').read_text().splitlines()
                        if line.split()[-1].lstrip('*') == path.name]
            assert expected == [actual], path
            sources.append({'path': str(path.relative_to(ROOT)), 'sha256': actual})
            with path.open(newline='') as handle:
                data = list(csv.DictReader(handle))
            assert len(data) == 79
            for window in WINDOWS:
                subset = [r for r in data if window * 80 <= int(r['bond']) <= (1-window) * 80]
                x = np.array([float(r['log_chord']) for r in subset])
                y = np.array([float(r['entropy']) for r in subset])
                bonds = np.array([int(r['bond']) for r in subset])
                for model, groups in [('class5_intercepts', bonds % 5), ('class10_intercepts', bonds % 10)]:
                    rows.append(dict(cell=cell.name, start=start, window=window, model=model, **fit(x, y, groups)))
                for group in range(5):
                    keep = bonds % 5 == group
                    rows.append(dict(cell=cell.name, start=start, window=window, model=f'class{group}_separate',
                                     **fit(x[keep], y[keep], np.zeros(sum(keep)))))
    assert len(sources) == 12 and len(rows) == 336
    OUT.mkdir(exist_ok=True)
    with (OUT / 'fits.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    table = []
    for cell in sorted({r['cell'] for r in rows}):
        values = [cell]
        for model in ('class5_intercepts', 'class10_intercepts'):
            selected = [r['c_eff'] for r in rows if r['cell'] == cell and r['model'] == model]
            values.append(f'{min(selected):.3f} – {max(selected):.3f}')
        table.append(values)
    summary = {'source_checksums': sources, 'fits': len(rows), 'windows': WINDOWS,
               'tests': 'known_slope_and_rank_rejection_pass', 'table': table,
               'interpretation': 'sensitivity_audit_not_a_phase_classifier',
               'limitations': ['L80 only', 'shared slope is a diagnostic assumption',
                               'ranges are model/window/start sensitivity, not confidence intervals']}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    document = {'title': '负 α 保存态扫描：纠缠拟合复核',
                'lede': '6 个参数点、12 个已保存态。先检查分析选择的影响，再决定相界补算。',
                'sections': [
                    {'title': '复核方法', 'blocks': [
                        {'kind': 'text', 'text': '所有五类键均保留，不按 R² 筛选。比较中心 80%、70%、60%、50% 的链段；分别允许五类键具有不同截距，以及十类键（包含单元奇偶）具有不同截距，共享斜率。另保存每一类的独立拟合。'},
                        {'kind': 'text', 'text': '12 份原始纠缠 CSV 的 SHA256 与回传清单一致；共 336 次拟合。合成已知斜率恢复和秩不足拒绝测试通过。该复核不替代原有数值验收。'}]},
                    {'title': '拟合敏感性', 'blocks': [
                        {'kind': 'table', 'columns': ['参数点', '五类截距 c_eff 范围', '十类截距 c_eff 范围'], 'rows': table},
                        {'kind': 'note', 'text': '范围包含窗口和双初态变化，不是统计置信区间。单一 L=80 的有效斜率不能直接等同于热力学中心荷；共享斜率本身也需要检验。'}]},
                    {'title': '对收尾工作的影响', 'blocks': [
                        {'kind': 'text', 'text': '先前只选择高 R² 类别的中心荷数值不能单独作为新相证据。原始数据保留，旧拟合供历史追溯，不据此命名相。'},
                        {'kind': 'text', 'text': '下一步对最敏感的 beta=0.25、alpha=-0.175 至 -0.10 区间做有限尺寸比较，同时检查能隙与键关联。若不同指标不支持同一边界，就保留未判定标记，不为了得到新相继续无界扫描。'},
                        {'kind': 'text', 'text': '小的有限距离连接关联并不能排除长程有序；通过非负能隙验收也不能作为不存在相变的独立证明。'}]}]}
    (OUT / 'report.json').write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary['table'], indent=2))


if __name__ == '__main__':
    main()
