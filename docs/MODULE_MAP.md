# 代码模块、原文件和运行入口

本次只整理目录、导入和项目根路径，不改因子定义、模型参数、训练日期、配重、执行或已有回测结果。数据、outputs和当前PPT留在原位置。

## 按功能查找

| 模块 | 关键代码 | 负责内容 |
|---|---|---|
| 数据 | `orie5260/paths.py`、`common/data.py` | 统一根路径、读价格/月收益/宏观和交易日历 |
| 因子 | `factors/features.py` | 原31个价格路径和同类/残差候选公式 |
| IC与t统计 | `factors/ic.py` | 横截面IC、类别内IC、6期HAC t及收益月对齐 |
| 因子筛选 | `factors/selection.py` | 62数值输入及4类别控制、训练期IC/t筛选 |
| 信号袖套 | `signals/price_trend.py`、`macro_trend.py`、`negative_skew.py` | 日度趋势、经济趋势、独立负偏度策略 |
| 模型 | `models/extra_trees.py`、`training.py` | 原66输入预测、指定输入名单的因果模型拟合 |
| 风险与组合 | `portfolio/risk_model.py`、`engine.py` | 波动率、协方差、风险缩放和统一约束 |
| 配重 | `portfolio/allocation.py` | 四模块受约束收益/风险/成本配重目标及日度评估 |
| 执行成本 | `execution/accounting.py`、`optimizer.py`、`costs_and_execution.py` | 净持仓记账、最优交易比例、日度成本及持仓漂移 |
| 原始提交 | `backtests/` | 原baseline、66输入、原附录对照；保持原命令含义 |
| 因子实验 | `research/factors/` | IC诊断、IC筛选、IC+t筛选及后期比较 |
| 配重/执行实验 | `research/allocation/` | 原66与固定42的优化实验，均保留 |
| 汇报 | `presentation/` | 当前42输入结果、筛选图、模型对比PnL和t公式图 |

`models/ic_feature_filter.py`是兼容API，原函数仍可导入，实际筛选与训练已分别位于factors/selection.py、models/training.py。portfolio/engine.py也保留已迁往execution/的函数的惰性兼容导出，避免引入循环依赖。

## 原文件到新文件

所有原实现保存在archive/flat_layout_before_modularization/，以下为活跃新位置。

| 原根目录文件 | 新位置 | 运行方式 |
|---|---|---|
| `data_utils.py` | [orie5260/common/data.py](../orie5260/common/data.py) | 被其他模块导入，无独立回测入口 |
| `price_trend.py` | [orie5260/signals/price_trend.py](../orie5260/signals/price_trend.py) | 被其他模块导入，无独立回测入口 |
| `macro_trend.py` | [orie5260/signals/macro_trend.py](../orie5260/signals/macro_trend.py) | 被其他模块导入，无独立回测入口 |
| `negative_skew.py` | [orie5260/signals/negative_skew.py](../orie5260/signals/negative_skew.py) | 被其他模块导入，无独立回测入口 |
| `extra_trees.py` | [orie5260/models/extra_trees.py](../orie5260/models/extra_trees.py) | 被其他模块导入，无独立回测入口 |
| `ic_feature_filter.py` | [orie5260/models/ic_feature_filter.py](../orie5260/models/ic_feature_filter.py) | 被其他模块导入，无独立回测入口 |
| `portfolio_engine.py` | [orie5260/portfolio/engine.py](../orie5260/portfolio/engine.py) | 被其他模块导入，无独立回测入口 |
| `risk_model.py` | [orie5260/portfolio/risk_model.py](../orie5260/portfolio/risk_model.py) | 被其他模块导入，无独立回测入口 |
| `sleeve_allocation.py` | [orie5260/portfolio/allocation.py](../orie5260/portfolio/allocation.py) | 被其他模块导入，无独立回测入口 |
| `costs_and_execution.py` | [orie5260/execution/costs_and_execution.py](../orie5260/execution/costs_and_execution.py) | 被其他模块导入，无独立回测入口 |
| `daily_baseline.py` | [orie5260/backtests/daily_baseline.py](../orie5260/backtests/daily_baseline.py) | `python run.py baseline` |
| `run_final_strategy.py` | [orie5260/backtests/final_strategy.py](../orie5260/backtests/final_strategy.py) | `python run.py original-66` |
| `compare_baseline.py` | [orie5260/backtests/compare_baseline.py](../orie5260/backtests/compare_baseline.py) | `python run.py compare-original` |
| `decompose_steps.py` | [orie5260/backtests/decompose_steps.py](../orie5260/backtests/decompose_steps.py) | `python run.py decompose-original` |
| `exposure_sensitivity.py` | [orie5260/backtests/exposure_sensitivity.py](../orie5260/backtests/exposure_sensitivity.py) | `python run.py exposure-original` |
| `factor_ic_analysis.py` | [orie5260/research/factors/factor_ic_analysis.py](../orie5260/research/factors/factor_ic_analysis.py) | `python run.py factor-ic` |
| `backtest_ic_filter.py` | [orie5260/research/factors/backtest_ic_filter.py](../orie5260/research/factors/backtest_ic_filter.py) | `python run.py ic-filter` |
| `evaluate_ic_filter_oos.py` | [orie5260/research/factors/evaluate_ic_filter_oos.py](../orie5260/research/factors/evaluate_ic_filter_oos.py) | `python run.py ic-filter-oos` |
| `backtest_ic_t_filter.py` | [orie5260/research/factors/backtest_ic_t_filter.py](../orie5260/research/factors/backtest_ic_t_filter.py) | `python run.py ic-t-filter` |
| `optimize_daily_budgets.py` | [orie5260/research/allocation/optimize_daily_budgets.py](../orie5260/research/allocation/optimize_daily_budgets.py) | `python run.py allocation-original` |
| `optimize_ict42_portfolio.py` | [orie5260/research/allocation/optimize_ict42_portfolio.py](../orie5260/research/allocation/optimize_ict42_portfolio.py) | `python run.py allocation-42` |
| `prepare_ppt42_results.py` | [orie5260/presentation/prepare_results.py](../orie5260/presentation/prepare_results.py) | `python run.py selected-42` |
| `presentation_factor_model_evidence.py` | [orie5260/presentation/model_evidence.py](../orie5260/presentation/model_evidence.py) | `python run.py model-evidence` |

因子/统计/执行函数从原大文件中拆出时，原模块路径的导出仍保留。函数来源的拆分细节以organization_verification.json为准，不存在把被拆出的业务函数丢弃的情况。

## 当前42输入与原66输入不要混用

- `python run.py selected-42`（也可用`ppt-results`、`prepare_ppt42_results.py`作为命令名）重建当前42输入方案及附加诊断；数字在outputs/ppt42_update/。
- `python run.py model-evidence`重建2005–2014候选模型验证图，输出outputs/ppt_factor_model_evidence/。
- `python run_final_strategy.py`或`python run.py original-66`仍复现原66输入提交，输出outputs/final_strategy/。为了保留原算法，本次没有悄悄把这个旧入口改成42。
- `python compare_baseline.py`或`python run.py compare-original`比较的也是原66输入与baseline。
- 当前PPT在ppt/，原report.md保留66输入报告口径。42输入的研究报告及PPT修改说明单独保存。

## 命令、输出和依赖

| 命令 | 模块 | 前置冻结产物 |
|---|---|---|
| `python run.py baseline` | `orie5260.backtests.daily_baseline` | 不额外要求冻结模型；原数据/参考输出仍须存在 |
| `python run.py original-66` | `orie5260.backtests.final_strategy` | 不额外要求冻结模型；原数据/参考输出仍须存在 |
| `python run.py compare-original` | `orie5260.backtests.compare_baseline` | 不额外要求冻结模型；原数据/参考输出仍须存在 |
| `python run.py decompose-original` | `orie5260.backtests.decompose_steps` | 不额外要求冻结模型；原数据/参考输出仍须存在 |
| `python run.py exposure-original` | `orie5260.backtests.exposure_sensitivity` | 不额外要求冻结模型；原数据/参考输出仍须存在 |
| `python run.py factor-ic` | `orie5260.research.factors.factor_ic_analysis` | 不额外要求冻结模型；原数据/参考输出仍须存在 |
| `python run.py ic-filter` | `orie5260.research.factors.backtest_ic_filter` | 不额外要求冻结模型；原数据/参考输出仍须存在 |
| `python run.py ic-filter-oos` | `orie5260.research.factors.evaluate_ic_filter_oos` | `outputs/ic_feature_filter/frozen_pre2015_model.joblib` |
| `python run.py ic-t-filter` | `orie5260.research.factors.backtest_ic_t_filter` | `outputs/ic_feature_filter_oos/aligned_period_returns.csv` |
| `python run.py allocation-original` | `orie5260.research.allocation.optimize_daily_budgets` | 不额外要求冻结模型；原数据/参考输出仍须存在 |
| `python run.py allocation-42` | `orie5260.research.allocation.optimize_ict42_portfolio` | `outputs/ic_t_feature_filter/ICT_Fixed42_frozen_model.joblib` |
| `python run.py selected-42` | `orie5260.presentation.prepare_results` | `outputs/ic_t_feature_filter/ICT_Fixed42_probabilities.csv` |
| `python run.py model-evidence` | `orie5260.presentation.model_evidence` | `outputs/ic_t_feature_filter/frozen_selection.json`, `outputs/factor_ic/monthly_feature_ic.csv` |

### 从头重建研究产物

`factor-ic → ic-filter → ic-filter-oos → ic-t-filter → selected-42 → model-evidence`。

这只是原实验依赖顺序，不是把这些步骤都加入主策略。每个入口只运行选定任务，未指定任务或使用--list/--dry-run不执行回测。

## 如何调用与兼容

- 主入口：`python run.py --list`、`python -m orie5260 --list`。
- 旧研究文件名：例如`python run.py backtest_ic_t_filter.py`，与`python run.py ic-t-filter`等价。
- 原三个常用脚本daily_baseline.py、run_final_strategy.py、compare_baseline.py保留根目录兼容入口。导入它们得到实际实现模块对象，原函数和常量可访问。
- 底层旧根目录模块已移动；新代码请使用完整导入，例如`from orie5260.factors.selection import select_inputs`。不要从archive作为运行入口导入。
- 所有数据/输出路径由共享ROOT定位。可以从其他工作目录用绝对路径运行run.py，模型不会去子模块目录找data/。

## 保留与校验

- 23个原根目录Python实现完整归档；79个原顶层函数/类（包含其方法和嵌套函数）的AST主体与整理前一致，校验时仅归一化import路径。
- 35份源代码、测试、报告和README快照的SHA256校验一致，清单在archive/flat_layout_before_modularization/manifest.json。
- 当前PPT、数据、冻结模型和全部outputs未移动或覆写。
- 另保留会话中的PPT作者脚本与历史恢复版本于archive/ppt_authoring_session/。这些原作者脚本依赖当时绝对路径，是历史快照，不是当前运行入口。
- 24项测试通过；包含全部旧数学/时序/成本测试及新增模块导入、根路径、原主入口别名和跨工作目录CLI检查。
- 原66输入比较在临时目录重建，与原保存表在1e-12容差内一致；冻结42输入模型成功加载，未覆写旧结果。
- 固定42输入策略按保存持仓重放12,916个交易日，净收益最大绝对差为3.21e-16，整理未改变逐日收益。

验证记录：organization_verification.json、organization_smoke_check.json。整理前英文README原文为README_before_modularization.md。
