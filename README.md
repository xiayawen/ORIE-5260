# ORIE 5260：代码与实验导航

代码已按功能模块整理。当前选定的是 **IC＋方向t筛选、固定42输入Extra Trees、固定30/20/20/30预算、21营业日全量调仓**；不采用学习配重或成本感知执行。对应历史IS Sharpe **1.2831**、2015–2025年5月后期Sharpe **0.3567**。

原始66输入提交、所有筛选/模型/优化实验、数据和结果均保留。这里仅整理文件及导入，不改变策略规则、训练日期或已有回测产物。`report.md`仍是原66输入提交报告；当前42输入数字和19页演示见`ppt/`及`outputs/ppt42_update/`。

## 常用入口

在项目根目录安装`requirements.txt`中的依赖，然后运行：

```bash
python run.py --list
python run.py selected-42 --dry-run
python run.py selected-42
python run.py model-evidence
python -m unittest discover -s tests -v
```

`selected-42`使用已有冻结42输入预测重建组合主结果、风控对照与图表，输出`outputs/ppt42_update/`；`model-evidence`重建筛选证据及候选模型验证PnL，输出`outputs/ppt_factor_model_evidence/`。这两个命令不编辑PPT文件。

完整重建研究产物时，依次运行：

```bash
python run.py factor-ic
python run.py ic-filter
python run.py ic-filter-oos
python run.py ic-t-filter
python run.py selected-42
python run.py model-evidence
```

这些命令会重建各自的结果目录。若只阅读现有结果，无需重新训练。`--dry-run`可先查看模块及必要产物。

原有三个常用命令继续有效，含义保持不变：

```bash
python daily_baseline.py       # 课程日度baseline
python run_final_strategy.py   # 原66输入提交，保留作对照
python compare_baseline.py     # 原66输入与baseline的比较
```

其他旧脚本名可作为统一入口参数使用，例如：

```bash
python run.py factor_ic_analysis.py
python run.py optimize_ict42_portfolio.py
python -m orie5260 selected-42 --dry-run
```

## 代码在哪里

```text
orie5260/
├── common/          数据读取与日历
├── factors/         31原始因子、排名输入、IC/HAC统计、训练期筛选
├── signals/         日度趋势、经济趋势、独立负偏度袖套
├── models/          Extra Trees预测与按指定特征训练
├── portfolio/       协方差/波动率、组合约束、模块配重优化
├── execution/       交易记账、交易成本、成本感知执行
├── backtests/       原提交baseline/66输入回测及附录对照
├── research/
│   ├── factors/     IC、IC+t筛选及后期实验
│   └── allocation/  模块配重与执行优化实验
└── presentation/    42输入主结果、因子证据和模型对比图表
```

| 位置 | 内容 |
|---|---|
| `tests/` | 数学、时序、成本、筛选及模块路径测试 |
| `reports/research/` | 六份研究报告，包含未采用的实验 |
| `report.md` | 原66输入提交报告，保留历史口径 |
| `ppt/ORIE5260 Presentation.pptx` | 当前19页42输入方案演示 |
| `data/` | 原始价格、月收益、类别映射、宏观数据 |
| `outputs/` | 所有现有回测、冻结模型、筛选表和图表；位置不变 |
| `archive/flat_layout_before_modularization/` | 整理前完整源码/测试/报告快照及SHA256清单 |
| `archive/ppt_authoring_session/` | PPT原作者脚本及历史恢复版本 |
| `docs/MODULE_MAP.md` | 原文件→新模块、命令、输出与依赖对照 |

数据路径由`orie5260/paths.py`统一定位，不依赖运行时工作目录。原始数据和输出目录没有移动。

## 当前方案与未采用实验

- **保留**：训练期IC幅度＋方向HAC t筛选的固定42项名单；2015年前重训模型后冻结；四模块信号预算固定30/20/20/30。
- **对照保留**：原66输入、仅IC的56输入、2015年前重筛的55/38输入、其它模型、配重优化和成本感知执行。它们没有被删除，也不自动成为主策略。
- 1976–2014是长期历史统计区间，2005年前ML预算回到趋势；不能把长期IS称作42输入模型全程运行39年的成绩。
- 2015年后数据曾在研究中反复查看，后期比较不等于新获得的未触碰测试集。

研究报告索引见[reports/research/README.md](reports/research/README.md)。整理前英文README原文保存在[docs/README_before_modularization.md](docs/README_before_modularization.md)。
