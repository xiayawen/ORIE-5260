"""Small lazy command registry for reproducible baseline and research runs."""
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
import argparse
from orie5260.paths import ROOT


@dataclass(frozen=True)
class Command:
    module: str
    description: str
    group: str
    requires: tuple = ()


COMMANDS = {
    'baseline': Command('orie5260.backtests.daily_baseline', '重建课程日度baseline', '原始提交复现'),
    'original-66': Command('orie5260.backtests.final_strategy', '重建原66输入提交版，保留作对照', '原始提交复现'),
    'compare-original': Command('orie5260.backtests.compare_baseline', '原66输入提交与baseline比较', '原始提交复现'),
    'decompose-original': Command('orie5260.backtests.decompose_steps', '原66输入构造/风控/执行消融', '原始提交复现'),
    'exposure-original': Command('orie5260.backtests.exposure_sensitivity', '原66输入敞口限制敏感性', '原始提交复现'),
    'factor-ic': Command('orie5260.research.factors.factor_ic_analysis', '66候选输入的月度IC诊断', '因子筛选实验'),
    'ic-filter': Command('orie5260.research.factors.backtest_ic_filter', '仅IC筛选，2015年前验证并冻结模型', '因子筛选实验'),
    'ic-filter-oos': Command('orie5260.research.factors.evaluate_ic_filter_oos', '固定56/重筛55的后期评估', '因子筛选实验', ('outputs/ic_feature_filter/frozen_pre2015_model.joblib',)),
    'ic-t-filter': Command('orie5260.research.factors.backtest_ic_t_filter', 'IC+t筛选及固定42/重筛38对照', '因子筛选实验', ('outputs/ic_feature_filter_oos/aligned_period_returns.csv',)),
    'allocation-original': Command('orie5260.research.allocation.optimize_daily_budgets', '原66输入四模块配重优化实验', '配重与执行实验'),
    'allocation-42': Command('orie5260.research.allocation.optimize_ict42_portfolio', '固定42输入配重/成本感知执行四组对照', '配重与执行实验', ('outputs/ic_t_feature_filter/ICT_Fixed42_frozen_model.joblib',)),
    'selected-42': Command('orie5260.presentation.prepare_results', '重建当前选定42输入组合、主结果和附加诊断图', '当前方案与汇报', ('outputs/ic_t_feature_filter/ICT_Fixed42_probabilities.csv',)),
    'model-evidence': Command('orie5260.presentation.model_evidence', '生成因子证据、方向t公式和候选模型验证PnL', '当前方案与汇报', ('outputs/ic_t_feature_filter/frozen_selection.json', 'outputs/factor_ic/monthly_feature_ic.csv')),
}

LEGACY_COMMANDS = {
    'daily_baseline': 'baseline', 'run_final_strategy': 'original-66',
    'compare_baseline': 'compare-original', 'decompose_steps': 'decompose-original',
    'exposure_sensitivity': 'exposure-original', 'factor_ic_analysis': 'factor-ic',
    'backtest_ic_filter': 'ic-filter', 'evaluate_ic_filter_oos': 'ic-filter-oos',
    'backtest_ic_t_filter': 'ic-t-filter', 'optimize_daily_budgets': 'allocation-original',
    'optimize_ict42_portfolio': 'allocation-42', 'prepare_ppt42_results': 'selected-42',
    'presentation_factor_model_evidence': 'model-evidence', 'ppt-results': 'selected-42',
}


def resolve_command(name):
    key = Path(name).name
    if key.endswith('.py'):
        key = key[:-3]
    key = LEGACY_COMMANDS.get(key, key)
    if key not in COMMANDS:
        raise ValueError(f'未知命令: {name}；用 --list 查看可用命令。')
    return key, COMMANDS[key]


def list_commands():
    previous = None
    for key, spec in COMMANDS.items():
        if spec.group != previous:
            print(f'\n{spec.group}')
            previous = spec.group
        print(f'  {key:22s} {spec.description}')
    print('\n旧脚本名也可用，例如 python run.py factor_ic_analysis.py')


def main(argv=None):
    parser = argparse.ArgumentParser(description='ORIE5260模块化运行入口；未指定命令时只列出任务，不运行回测。')
    parser.add_argument('command', nargs='?', help='任务名或原脚本名（含/不含.py）')
    parser.add_argument('--list', action='store_true', help='列出模块和运行任务')
    parser.add_argument('--dry-run', action='store_true', help='显示实际模块和依赖，不读取数据/运行任务')
    args = parser.parse_args(argv)
    if args.list or not args.command:
        list_commands()
        return
    try:
        key, spec = resolve_command(args.command)
    except ValueError as error:
        parser.error(str(error))
    if args.dry_run:
        print(f'任务: {key}\n模块: {spec.module}\n说明: {spec.description}\n项目根目录: {ROOT}')
        print('前置产物: ' + (', '.join(spec.requires) if spec.requires else '无额外冻结产物要求；数据仍需位于data/'))
        return
    print(f'运行 {key}: {spec.module}', flush=True)
    import_module(spec.module).main()
