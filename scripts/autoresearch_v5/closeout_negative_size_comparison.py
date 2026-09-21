"""汇总十二点尺寸证据，不作热力学外推。"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ALPHAS = (-.175, -.150, -.125, -.100)
SIZES = (40, 60, 80)
STARTS = ('center', 'ferro_j2')
DERIVED_NAMES = ('entropy_fits.csv', 'observables.csv', 'connected_bonds.csv', 'bond_expectations.csv')
INPUT_NAMES = ('entropy_fits.csv', 'observables.csv', 'bond_expectations.csv', 'connected_bonds.csv')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def verify_derived_provenance(analysis_dir, summary):
    """核对分析脚本和四个派生表，拒绝缺失或篡改。"""
    records = summary.get('derived_outputs')
    if not isinstance(records, list) or {r.get('name') for r in records} != set(DERIVED_NAMES):
        raise ValueError('分析 summary 缺少完整派生文件哈希')
    for record in records:
        name = record.get('name')
        path = analysis_dir / name
        recorded_path = Path(record.get('path', '')).resolve()
        if recorded_path != path.resolve() or not path.is_file():
            raise ValueError(f'派生文件路径缺失或不匹配：{name}')
        if sha256(path) != record.get('sha256'):
            raise ValueError(f'派生文件哈希不匹配：{name}')
    script_record = summary.get('analysis_script')
    if not isinstance(script_record, dict):
        raise ValueError('分析 summary 缺少分析脚本哈希')
    script_path = Path(script_record.get('path', ''))
    if not script_path.is_file() or sha256(script_path) != script_record.get('sha256'):
        raise ValueError('分析脚本哈希不匹配')
    coverage_record = summary.get('coverage')
    if not isinstance(coverage_record, dict):
        raise ValueError('分析 summary 缺少 coverage 哈希')
    coverage_path = Path(coverage_record.get('path', ''))
    if (not coverage_path.is_file()
            or sha256(coverage_path) != coverage_record.get('sha256')
            or summary.get('run_spec_sha256') != coverage_record.get('run_spec_sha256')):
        raise ValueError('coverage 或 run_spec 哈希不匹配')


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def select(rows, alpha, length, start=None):
    return [r for r in rows if float(r['alpha']) == alpha and int(r['L']) == length
            and float(r['beta']) == .25 and (start is None or r['initial_state'] == start)]


def triplet(values):
    values = np.asarray(values, dtype=float)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError('缺少有限观测值')
    return float(values.mean()), float(values.min()), float(values.max())


def dimer_rms(rows, length):
    # 同类相邻晶胞；仅保留两个端点均在中部的键。
    by_bond = {int(r['bond']): float(r['correlation']) for r in rows}
    if len(rows) != length - 1 or set(by_bond) != set(range(1, length)):
        raise ValueError('键期望不完整或重复')
    pairs = [(b, b + 5) for b in by_bond if length / 4 <= b
             and b + 5 <= 3 * length / 4 and b + 5 in by_bond]
    if not pairs:
        raise ValueError('没有可比较的中部同类键')
    differences = [by_bond[a] - by_bond[b] for a, b in pairs]
    return float(np.sqrt(np.mean(np.square(differences)))), len(pairs)


def connected_quarter(rows, length):
    distance = length // 20
    selected = [r for r in rows if int(r['bond_class']) == 0
                and float(r['distance_units']) == distance]
    expected = {(length // 2, length // 2 - 5 * distance),
                (length // 2, length // 2 + 5 * distance)}
    actual = {(int(r['reference_bond']), int(r['target_bond'])) for r in selected}
    if len(selected) != 2 or actual != expected:
        raise ValueError('r/N=1/4连接关联缺少左右两点或重复')
    for row in selected:
        if abs(float(row['distance_over_units']) - .25) > 1e-12:
            raise ValueError('连接关联距离归一化错误')
    return [(-1) ** distance * float(r['connected']) for r in selected]


def summarize(fits, obs, bonds, connected):
    expected = {(a, .25, length, start) for a in ALPHAS for length in SIZES for start in STARTS}
    keys = [(float(r['alpha']), float(r['beta']), int(r['L']), r['initial_state']) for r in obs]
    if len(keys) != 24 or set(keys) != expected:
        raise ValueError('不是完整唯一的十二点双初态网格')
    fit_keys = [(float(r['alpha']), float(r['beta']), int(r['L']), r['initial_state'],
                 float(r['window']), int(r['period'])) for r in fits]
    expected_fit = {(*key, window, period) for key in expected
                    for window in (.1, .15, .2, .25) for period in (5, 10)}
    if len(fit_keys) != 192 or set(fit_keys) != expected_fit:
        raise ValueError('纠缠拟合网格缺失或重复')
    for table, value in ((fits, 'c_eff'), (obs, 'spin_gap'), (bonds, 'correlation'), (connected, 'connected')):
        if not all(np.isfinite(float(r[value])) for r in table):
            raise ValueError('非有限输入')
    output = []
    for alpha in ALPHAS:
        for length in SIZES:
            record = {'alpha': alpha, 'beta': .25, 'L': length, 'N': length // 5}
            fit_rows = select(fits, alpha, length)
            for period in (5, 10):
                chosen = [r for r in fit_rows if int(r['period']) == period]
                central = [float(r['c_eff']) for r in chosen if float(r['window']) == .2]
                _, lower, upper = triplet([float(r['c_eff']) for r in chosen])
                record.update({f'c{period}_fixed_mean': triplet(central)[0],
                               f'c{period}_all_min': lower, f'c{period}_all_max': upper,
                               f'c{period}_fixed_start_difference': abs(central[0] - central[1])})
            observed = select(obs, alpha, length)
            gaps = [float(r['spin_gap']) for r in observed]
            for key, value in zip(('gap_mean', 'gap_min', 'gap_max'), triplet(gaps)):
                record[key] = value
            record['gap_start_relative_spread'] = (max(gaps) - min(gaps)) / max(abs(np.mean(gaps)), 1e-15)
            record['max_variance_per_site'] = max(float(r[field]) for r in observed
                for field in ('variance_sz0_per_site', 'variance_sz1_per_site'))
            dimers, tails = [], []
            for start in STARTS:
                value, count = dimer_rms(select(bonds, alpha, length, start), length)
                dimers.append(value)
                tails.extend(connected_quarter(select(connected, alpha, length, start), length))
            record['dimer_pairs_per_start'] = count
            for prefix, values in (('dimer', dimers), ('staggered_connected', tails)):
                for suffix, value in zip(('mean', 'min', 'max'), triplet(values)):
                    record[f'{prefix}_{suffix}'] = value
            record['connected_samples'] = len(tails)
            output.append(record)
    return output


def plot(rows, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'DejaVu Sans'],
        'font.size': 7, 'axes.spines.top': False, 'axes.spines.right': False,
        'svg.fonttype': 'none', 'pdf.fonttype': 42, 'axes.linewidth': .7,
        'legend.frameon': False})
    fig, axes = plt.subplots(2, 2, figsize=(183 / 25.4, 137 / 25.4))
    fig.subplots_adjust(left=.105, right=.98, bottom=.105, top=.86, wspace=.38, hspace=.46)
    colors = ('#406786', '#5F8C87', '#B1854B', '#9F627C')
    markers = ('o', 's', '^', 'D')
    linestyles = ('-', '--', '-.', ':')
    handles = []
    for index_alpha, (alpha, color) in enumerate(zip(ALPHAS, colors)):
        chosen = [r for r in rows if r['alpha'] == alpha]
        x = np.array([r['N'] for r in chosen])
        specs = [('c10_fixed_mean', 'c10_all_min', 'c10_all_max'),
                 ('gap_mean', 'gap_min', 'gap_max'),
                 ('dimer_mean', 'dimer_min', 'dimer_max'),
                 ('staggered_connected_mean', 'staggered_connected_min', 'staggered_connected_max')]
        for index, (ax, columns) in enumerate(zip(axes.flat, specs)):
            y, lo, hi = (np.array([r[key] for r in chosen]) for key in columns)
            if index == 1:
                y, lo, hi = y * x, lo * x, hi * x
            line, = ax.plot(x, y, color=color, marker=markers[index_alpha],
                            linestyle=linestyles[index_alpha], ms=3, lw=1,
                            label=rf'$\alpha={alpha:.3f}$')
            ax.fill_between(x, lo, hi, color=color, alpha=.13, linewidth=0)
            ax.vlines(x, lo, hi, color=color, lw=.8)
            if index == 0:
                handles.append(line)
            ax.set_xticks((8, 12, 16))
            ax.set_xlabel(r'Number of pentamers $N=L/5$')
    labels = [(r'$c_{\mathrm{eff}}$ (diagnostic)', 'Entropy: window/start sensitivity'),
              (r'$N\Delta_{S^z}/J_1$', 'Sector gap: not a bulk-gap fit'),
              (r'$D_{\mathrm{RMS}}$', 'Central same-class bond difference'),
              (r'$(-1)^r C_{BB}(r)$', r'Intercell bonds at $r/N=1/4$')]
    for letter, ax, (ylabel, title) in zip('abcd', axes.flat, labels):
        ax.set_ylabel(ylabel)
        ax.set_title(title, loc='left', fontsize=7, pad=9)
        ax.text(-.2, 1.09, letter, transform=ax.transAxes, fontweight='bold', fontsize=9)
        ax.tick_params(direction='out', length=3, width=.7)
    axes[0, 0].axhline(1, color='.6', lw=.7, ls=':', zorder=0)
    axes[0, 1].ticklabel_format(axis='y', style='sci', scilimits=(0, 0))
    axes[1, 0].set_yscale('log')
    axes[1, 1].set_yscale('symlog', linthresh=1e-7)
    axes[1, 1].axhline(0, color='.6', lw=.6)
    fig.legend(handles=handles, loc='upper center', ncol=4, bbox_to_anchor=(.54, .98))
    outputs = []
    for suffix, options in (('svg', {}), ('pdf', {}), ('png', {'dpi': 200}),
                            ('tiff', {'dpi': 600, 'pil_kwargs': {'compression': 'tiff_lzw'}})):
        target = out / f'negative_size_joint_evidence.{suffix}'
        fig.savefig(target, **options)
        outputs.append(target)
    plt.close(fig)
    return outputs


def build_report(rows):
    table = [[f"{r['alpha']:.3f}", str(r['L']), f"{r['c10_all_min']:.3f}–{r['c10_all_max']:.3f}",
              f"{r['gap_mean']:.3e}", f"{r['gap_start_relative_spread']:.1%}", f"{r['dimer_mean']:.3e}"] for r in rows]
    return {'title': '五聚体收尾：十二点联合尺寸证据', 'eyebrow': '2026-09-19 · STAGE 1 · ACCEPTED DATA',
        'lede': '12个物理点、24个初态结果、192次纠缠拟合。数值验收通过不等于热力学相已经确认。',
        'sections': [
            {'title': '这轮回答什么', 'blocks': [
                {'kind': 'text', 'text': '固定β=0.25，比较α=-0.175、-0.150、-0.125、-0.100和L=40、60、80。对应只有8、12、16个五聚体，不能把80个物理自旋误读为80个有效晶胞。'},
                {'kind': 'verdict', 'status': 'warn', 'label': '相名保持未判定', 'why': '纠缠、有限链扇区gap和键观测量采用统一定义比较；不进行无误差支撑的热力学拟合或临界指数拟合。'}]},
            {'title': '联合尺寸图', 'blocks': [
                {'kind': 'figures', 'items': [{'src': 'negative_size_joint_evidence.png', 'caption': '已验收数据的尺寸比较。颜色区分α。a：十类截距拟合；线为固定f=0.20窗口的双初态均值，阴影及竖线覆盖全部四窗口和双初态。b：晶胞数N乘Sz扇区gap。c：中央区间内同类键跨相邻晶胞的差值RMS。d：胞间键在r/N=1/4的带符号交错连接关联。b、c的范围为双初态差异；d含左右两方向与双初态。所有范围均非统计置信区间；线仅引导视线。'}]},
                {'kind': 'note', 'text': '小扇区gap可能受到开边界低能态影响；NΔ不是体能隙外推。非零开边界键交替不自动等于自发二聚化；有限距离的小连接关联也不能排除长程有序。'}]},
            {'title': '逐点数值', 'blocks': [
                {'kind': 'table', 'columns': ['alpha', 'L', 'c_eff范围', 'gap均值/J1', 'gap初态全差/均值', 'D_RMS均值'], 'rows': table},
                {'kind': 'text', 'text': '范围、均值和精确定义都保存在逐点CSV；全套五/十类截距拟合不按R²筛选。f是左右各排除的链长比例。D_RMS对b和b+5均落在[L/4,3L/4]内的所有同类键差取均方根；这些位置不是独立统计样本。'}]},
            {'title': '接下来怎样决定', 'blocks': [
                {'kind': 'text', 'text': '先用有效投影区分晶胞动量与胞内形状因子，明确近α=0受控极限。随后只对最多两个敏感点检查观测量的键维和初态稳定性；若异常随精度漂移，报告数值敏感性，不扩大相界搜索。'},
                {'kind': 'text', 'text': 'q=0.6π与π相差2π/5，在五站点晶胞下折叠到同一晶胞动量。这一运动学关系不是完整物理机制证明；需要胞内分辨关联和谱权重验证。'},
                {'kind': 'note', 'text': '本轮仅本地分析；未启动新的Julia，未修改paper/。本图不证明新相，也不证明负区全域单相。'}]}
        ]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--analysis', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError('拒绝覆盖联合分析')
    base = json.loads((args.analysis / 'summary.json').read_text(encoding='utf-8'))
    if base['analyzed_points'] != 12 or not base['finite_size_comparison_ready']:
        raise ValueError('十二点尚未完整验收')
    verify_derived_provenance(args.analysis, base)
    for record in base['sources']:
        path = Path(record.get('manifest', record.get('profile')))
        if sha256(path) != record['sha256']:
            raise ValueError(f'源哈希已改变：{path.name}')
    paths = [args.analysis / name for name in INPUT_NAMES]
    rows = summarize(*(read_csv(path) for path in paths))
    args.out.mkdir(parents=True)
    write_csv(args.out / 'joint_size_evidence.csv', rows)
    outputs = plot(rows, args.out)
    summary = {'stage': 1, 'points': 12, 'initial_state_records': 24, 'fits': 192,
        'raw_sources_verified': len(base['sources']), 'phase_assigned': False,
        'derived_outputs_verified': list(DERIVED_NAMES),
        'analysis_script': base['analysis_script'],
        'thermodynamic_fit_performed': False,
        'max_gap_start_relative_spread': max(r['gap_start_relative_spread'] for r in rows),
        'source_data': [{'path': str(p.resolve()), 'sha256': sha256(p)} for p in paths + [args.analysis / 'summary.json']],
        'outputs': [{'path': p.name, 'sha256': sha256(p)} for p in outputs],
        'script_sha256': sha256(Path(__file__)),
        'definitions': {'entropy': 'fixed f=.20 dual-start mean; envelope=f .10/.15/.20/.25 x two starts',
            'gap': 'finite OBC Sz1-Sz0; no inference of bulk gap',
            'dimer': 'RMS(B_b-B_(b+5)) with both bonds in [L/4,3L/4]',
            'connected': '(-1)^r C_BB at r/N=.25, class0, both directions and starts',
            'intervals': 'sensitivity ranges, not statistical confidence intervals'},
        'limitations': ['8/12/16 unit cells only', 'no bond-dimension sweep in this dataset',
                        'OBC gap may include edge effects', 'no new phase assigned']}
    (args.out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.out / 'report.json').write_text(json.dumps(build_report(rows), ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'points': len(rows), 'raw_sources_verified': len(base['sources']),
                      'max_gap_start_relative_spread': summary['max_gap_start_relative_spread']}))


if __name__ == '__main__':
    main()
