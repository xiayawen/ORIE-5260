# 新增因子筛选、树模型与候选模型证据页

当前PPT为19页，新增第8、10、12页。主策略仍为固定42输入Extra Trees、固定30/20/20/30预算、10%预测风险、21营业日全量调仓。原主结果IS1.2831、OOS0.3567未改。

## 第8页：训练期IC强度、方向t-stat与验证图

新增两张图：

1. 62个数值候选输入的训练期 `abs(mean IC)` 与 `abs(HAC t)` 散点图，明确0.01和1.96门槛。保留38个数值输入，加4个类别控制＝42。
2. 20个保留原始因子的训练方向调整IC，在训练与2005–2014验证的均值及95%HAC区间。不把原始因子及其排名当成两个独立证据。

方向与统计量：

\[
s_j=\operatorname{sign}(\overline{IC}_{j,\mathrm{train}}),\qquad q_{j,t}=s_jIC_{j,t}.
\]

\[
t_j^{\mathrm{dir}}=\frac{\overline q_j}{SE_{\mathrm{NW},6}(\overline q_j)},
\quad
SE_{\mathrm{NW},6}^{2}(\overline q_j)=
\frac{\widehat\gamma_0+2\sum_{\ell=1}^{6}(1-\ell/7)\widehat\gamma_\ell}{T}.
\]

其中
\(\widehat\gamma_\ell=T^{-1}\sum_{t=\ell+1}^{T}(q_{j,t}-\overline q_j)(q_{j,t-\ell}-\overline q_j)\)。筛选要求 `abs(mean IC)>=0.01` 且 `t_dir>=1.96`。负IC的原始t必须相应为负；不使用未来符号修正，也不对未来数据筛选。

图表实际结果：

| 方向IC诊断 | 训练 | 验证2005–2014 |
|---|---:|---:|
| 平均20个原始因子的方向IC | 0.0656 | 0.0185 |
| 这个月度平均序列的HAC t | 6.84 | 1.08 |
| 95%HAC区间 | [0.0468,0.0844] | [−0.0152,0.0522] |

16/20个原始因子的验证期平均IC与训练方向相同，但验证期平均方向IC的区间跨零。因而PPT写“方向部分延续、验证强度变弱”，没有把训练期筛选显著性说成未来稳健性证明。训练结果有选择偏差；名义t门槛没有多重检验校正。该图统计是因子IC的平均诊断，不是模型IC或可交易组合IC。

## 第10页：Extra Trees机制

新增原生可编辑图：42输入→随机树的特征阈值分支→叶子上涨比例→平均200棵树→概率p→连续方向2p−1。标注最大深度6、最小叶子30、max_features0.7以及仅训练集拟合的中位数填补。

讲稿解释随机特征及随机切分、叶子正类概率、200树平均，以及概率不是预期收益、方向分数不是净值权重。图是机制示意，真实预2005模型的前三棵树根节点在tree_root_examples.json中供核对。

## 第12页：候选模型同口径PnL

比较ExtraTrees、RandomForest、HistGB、Logistic。全部使用同42输入、相同13,191个训练样本，最后标签2004-11-30；2004-12-31首次形成预测后冻结到2014年末。中位数填补、Logistic标准化只在训练样本拟合。参数来自已定义研究规格，未按验证表现重新搜索。

曲线是**完整四模块组合**的净值，只有30%ML袖套所用模型变化；其它信号预算、10%风险目标、无敞口上限、21营业日交易和成本相同。时间段2005–2014，124个21日期间；不使用2015年后的模型比较曲线。

| 模型 | 验证净Sharpe | 最大端点回撤 | 预测AUC |
|---|---:|---:|---:|
| Extra Trees | 1.0112 | **−10.24%** | **0.5500** |
| Random Forest | 0.9728 | −11.05% | 0.5435 |
| HistGB | 1.0019 | −11.27% | 0.5430 |
| Logistic | **1.0353** | −10.94% | 0.5491 |

在这组验证点估计中，ExtraTrees具有最高AUC、最浅验证回撤，Logistic具有最高验证组合Sharpe/CAGR；不能写“ExtraTrees在所有指标最好”。四条曲线均是2005年前拟合后的向前预测，不是模型在训练集上的拟合预测。

AUC是2005–2014所有有效工具-月份的合并分类排序指标，不是按月IC，也没有建立不同模型间差异显著性的证明。候选净值很接近，不能只选择性展示支持某个模型的曲线。当前主模型并未因这项补充对比被更换。

## 页码对应

| 原16页版 | 现19页版 |
|---|---|
| 1–7 | 1–7 |
| 新增筛选页 | **8** |
| 原8：预测到组合流程 | 9 |
| 新增树机制页 | **10** |
| 原9：时间划分 | 11 |
| 新增候选模型PnL | **12** |
| 原10：最终选择 | 13 |
| 原11：主Sharpe结果 | 14 |
| 原12：回撤 | 15 |
| 原13：敞口 | 16 |
| 原14：构造对照 | 17 |
| 原15：敞口上限敏感性 | 18 |
| 原16：结论 | 19 |

因此，因子和模型部分现在是**第6–13页**。后续页码和讲稿内的交叉引用已经顺延，既有42输入主结果及图表内容保持不变。

## 数值来源及复现

`presentation_factor_model_evidence.py`生成比较数据，输出位于`outputs/ppt_factor_model_evidence/`：

- directional_ic_statistics.csv、selected20_factor_evidence.csv：训练/验证方向IC证据。
- validation_model_performance.csv、validation_classification.csv：模型净值及预测指标。
- aligned_pre2015_returns.csv、各模型daily_pre2015.csv：收益明细。
- model_training_audit.json、tree_root_examples.json：训练边界、参数和树节点。
- 四张新增图片：directional_t_formula.png、screen_scatter.png、signed_ic_validation.png、candidate_model_pnl.png。

复现命令：
`MPLCONFIGDIR=/private/tmp/orie_mpl OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python presentation_factor_model_evidence.py`。

模型构造过程中断言训练标签严格早于首次预测形成日；ExtraTrees预测和组合收益分别与既有42输入结果核对一致。PPT包、页码与新增图表经结构检查及原生渲染检查。

扩展前16页备份：`/private/tmp/ORIE5260 Presentation.before-factor-evidence.pptx`，实际保存的是扩展前16页版。
