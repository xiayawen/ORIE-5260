# 研究报告索引

这些报告完整保留研究过程，包括未采用的方案。当前选定方案为固定42输入、固定预算、全量调仓；原`report.md`是66输入提交版本。

| 报告 | 内容 |
|---|---|
| [FACTOR_IC_REPORT.md](FACTOR_IC_REPORT.md) | 66候选输入与模型概率的分期IC诊断 |
| [IC_FEATURE_FILTER_REPORT.md](IC_FEATURE_FILTER_REPORT.md) | 仅IC筛选：56输入验证、55输入冻结 |
| [IC_FILTER_OOS_REPORT.md](IC_FILTER_OOS_REPORT.md) | 固定56/重筛55的后期对照 |
| [IC_T_FILTER_REPORT.md](IC_T_FILTER_REPORT.md) | IC＋方向HAC t筛选：固定42/重筛38 |
| [DAILY_BUDGET_OPTIMIZATION_REPORT.md](DAILY_BUDGET_OPTIMIZATION_REPORT.md) | 原66输入的四模块配重优化 |
| [ICT42_PORTFOLIO_OPTIMIZATION_REPORT.md](ICT42_PORTFOLIO_OPTIMIZATION_REPORT.md) | 固定42输入的配重/执行四组对照 |

原文的源脚本名称可在[模块迁移表](../../docs/MODULE_MAP.md)中找到当前位置。命令改为`python run.py <原脚本名.py>`；数据和输出路径保持项目根目录下的`data/`、`outputs/`。
