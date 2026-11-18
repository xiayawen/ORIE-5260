from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
from copy import deepcopy
import shutil,re,posixpath
import pandas as pd

ROOT=Path('/Users/yawenvivianxia/Desktop/证件资料/ORIE 5260');FILE=ROOT/'ppt/ORIE5260 Presentation.pptx'
BACK=Path('/private/tmp/ORIE5260 Presentation.before-42-update.pptx')
if not BACK.exists():shutil.copy2(FILE,BACK)
with ZipFile(BACK) as z:data={n:z.read(n) for n in z.namelist()}
A='http://schemas.openxmlformats.org/drawingml/2006/main';P='http://schemas.openxmlformats.org/presentationml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS={'a':A,'p':P,'r':R}
metrics=pd.read_csv(ROOT/'outputs/ppt42_update/performance_and_decomposition.csv')
caps=pd.read_csv(ROOT/'outputs/ppt42_update/cap_sensitivity.csv')
base=pd.read_csv(ROOT/'outputs/baseline/daily_baseline_stats.csv');base=base[base.strategy.eq('exante_11_sample_u58')]

def m(name,period):return metrics[(metrics.strategy==name)&metrics.period.eq(period)].iloc[0]
is42=m('Selected42','IS');oos42=m('Selected42','OOS');bis=m('Baseline','IS');boos=m('Baseline','OOS')

def dump(root):return E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
def txt(sh):return ' | '.join(sh.xpath('.//a:t/text()',namespaces=NS))
def runs(root):return root.xpath('//a:t',namespaces=NS)
def replace_text(root,old,new):
 matches=[t for t in runs(root) if t.text==old]
 if not matches:raise ValueError('Missing '+old)
 for t in matches:t.text=new

def shape_lines(root,oldprefix,lines,size=None):
 matches=[s for s in root.findall('.//p:sp',NS) if txt(s).startswith(oldprefix)]
 assert len(matches)==1,(oldprefix,len(matches))
 s=matches[0];body=s.find('p:txBody',NS);paras=body.findall('a:p',NS);template=deepcopy(paras[0])
 for p in paras:body.remove(p)
 for text in lines:
  p=deepcopy(template);r=p.find('a:r',NS)
  for child in list(p):
   if child.tag not in ['{'+A+'}pPr','{'+A+'}r']:p.remove(child)
  for rr in list(p.findall('a:r',NS))[1:]:p.remove(rr)
  if r is None:r=E.SubElement(p,'{'+A+'}r')
  t=r.find('a:t',NS)
  if t is None:t=E.SubElement(r,'{'+A+'}t')
  t.text=text
  if size:
   rp=r.find('a:rPr',NS)
   if rp is None:rp=E.SubElement(r,'{'+A+'}rPr')
   rp.set('sz',str(round(size*100)))
  pp=p.find('a:pPr',NS)
  if pp is not None:
   aft=pp.find('a:spcAft/a:spcPts',NS)
   if aft is not None:aft.set('val','0')
  body.append(p)
 return s

def set_cell(cell,value):
 ts=cell.xpath('.//a:t',namespaces=NS);assert ts
 ts[0].text=str(value)
 for t in ts[1:]:t.text=''

def table(root):return root.find('.//a:tbl',NS)
def cell_grid(root):return [r.findall('a:tc',NS) for r in table(root).findall('a:tr',NS)]

pres=E.fromstring(data['ppt/presentation.xml']);rels=E.fromstring(data['ppt/_rels/presentation.xml.rels'])
lookup={r.get('Id'):r.get('Target') for r in rels};paths={}
for page,sid in enumerate(pres.findall('p:sldIdLst/p:sldId',NS),1):
 target=lookup[sid.get('{'+R+'}id')];paths[page]=target.lstrip('/') if target.startswith('/') else 'ppt/'+target
slides={page:E.fromstring(data[path]) for page,path in paths.items()}
# 4: signal definition now identifies the classifier actually used.
replace_text(slides[4],'Extra Trees','Extra Trees (42)')
# 6: distinguish candidate library from final screened inputs.
replace_text(slides[6],'These are candidate inputs, not 31 separately funded strategies. Exact feature names are in speaker notes and extra_trees.py.',
 '31 raw factors generate 66 candidate inputs; train-only IC + t screening retains 42. Exact names are in speaker notes.')
# 7: all model counts are final42; independent skew sleeve unchanged.
s=slides[7]
replace_text(s,'The 66-feature classifier and the 20% negative-skew sleeve serve different roles','The screened 42-input classifier and the 20% negative-skew sleeve serve different roles')
replace_text(s,'Model representation: 66 inputs','Model representation: 42 inputs')
replace_text(s,'31 raw + 31 ranks + 4 class flags','20 raw + 18 ranks + 4 class flags')
shape_lines(s,'Raw factors capture absolute return behavior.',[
 'Candidate pool: 31 raw + 31 ranks + 4 class flags.',
 'Train only: |mean IC| ≥ 0.01 and |HAC t| ≥ 1.96.',
 'Retain 20 raw factors + 18 ranks + 4 class flags.',
 'Fix the 42-input list; refit the model before 2015.'
],size=12)
replace_text(s,'The standalone sleeve is one hypothesis. Its presence does not prove an incremental return benefit in every period.',
 'Screening changes ML inputs only. The independent 20% negative-skew sleeve is unchanged; no individual alpha claim.')
# 8: prediction pipeline exposes candidate-to-selected step.
replace_text(slides[8],'31 raw factors + 31 ranks','66 candidates → 42 inputs')
replace_text(slides[8],'+ 4 class indicators','Train-only IC + HAC t filter')
replace_text(slides[8],'200 shallow randomized trees','200 trees fitted on 42 inputs')
# 9: fixed feature list, refitted classifier; do not imply a38-input policy.
s=slides[9]
replace_text(s,'One pre-2005 fit, one pre-2015 refit; no rolling refit during the later interval','Screen 42 inputs before 2005; refit the model before 2015; freeze both thereafter')
replace_text(s,'Train the initial classifier','Screen inputs + train')
shape_lines(s,'Only labels observed before',['|mean IC| ≥ 0.01; |HAC t| ≥ 1.96.','Use labels known before the','first Dec-2004 formation.'],size=12)
shape_lines(s,'Generate out-of-training',['Validate the frozen 42-input','model on 2005–2014.','No later labels enter this fit.'],size=12)
shape_lines(s,'Use only earlier labels;',['Keep the same 42-input list.','Refit with pre-2015 labels;','freeze for the later interval.'],size=12)
# 10: chosen model, recent optimization evidence and updated gains.
s=slides[10]
replace_text(s,'ET66: nonlinear use of the full factor library (30%).','ET42: train IC + t-screened inputs (30%).')
shape_lines(s,'Factor substitutes and peer / cross-asset extensions.',[
 'IC-only 56 inputs; IC + t fixed 42 inputs.',
 'Other models, learned weights and slower execution.',
 'Adding both optimizers: later Sharpe 0.3057.',
 'Keep fixed budgets / full rebalance: 0.3567.'
],size=12.7)
replace_text(s,'Final blend vs baseline: IS Sharpe 1.285 vs 1.222; later 0.343 vs 0.243',
 '42 vs baseline — IS: 1.2831 vs 1.2225; later: 0.3567 vs 0.2430')
replace_text(s,'Design rationale: interpretable peer selection + nonlinear forecasts in a reproducible fixed blend.',
 'Fixed 42-input policy: fewer inputs, similar IS Sharpe and a small later-period improvement over ET66.')
replace_text(s,'The final construction was selected after later results had been viewed. Differences are within sampling uncertainty; execution optimization is an appendix comparison.',
 'The 42-input version was selected after later results were viewed. Differences remain within sampling uncertainty.')
# 11: native metric table and embedded Sharpe chart.
s=slides[11];grid=cell_grid(s)
for ri,metric,period in [(1,'annual_mean_net_return','IS'),(2,'annual_volatility','IS'),(3,'annual_mean_net_return','OOS'),(4,'annual_volatility','OOS')]:
 set_cell(grid[ri][2],f"{m('Selected42',period)[metric]:.2%}")
set_cell(grid[0][2],'Blend (42)')
replace_text(s,'Sharpe gains: +0.063 historically and +0.100 later',
 f"Sharpe gains: ≈+{is42.sharpe_zero_rf-bis.sharpe_zero_rf:.3f} historically and ≈+{oos42.sharpe_zero_rf-boos.sharpe_zero_rf:.3f} later")
# 12: endpoint and daily drawdowns are different quantities.
s=slides[12]
replace_text(s,'Maximum: 25.48% baseline / 13.58% enhanced ',f'Maximum: 25.48% baseline / {abs(oos42.max_endpoint_drawdown):.2%} enhanced ')
replace_text(s,'Drawdowns use 21-day endpoints. The enhancement’s later daily maximum drawdown is 16.73%.',
 f'Drawdowns use 21-day endpoints. The enhancement’s later daily maximum drawdown is {abs(oos42.daily_max_drawdown):.2%}.')
# 13: same period-count annualization as slide14; unlike original mixed conventions.
s=slides[13];grid=cell_grid(s);set_cell(grid[0][2],'Blend (42)')
for ri,field,fmt in [(1,'average_gross','{:.2f}×'),(2,'average_absolute_net','{:.2f}×'),(3,'annual_turnover','{:.2f}×'),(4,'annual_cost','{:.2%}')]:set_cell(grid[ri][2],fmt.format(oos42[field]))
replace_text(s,'Gross = sum of absolute weights. Net = sum of signed weights. Exposure multiples are relative to NAV.',
 'Gross = sum |weights|; net = sum weights. Turnover / cost use matched-period years (21-day count ÷ 12).')
# 14: every construction now uses42 inputs. First row is10%-target trend, not11%-target benchmark.
s=slides[14];grid=cell_grid(s)
labels=['Trend only (10%)','Four sleeves (42), 10% target (final)','Four sleeves (42), no final re-scaling','Four sleeves (42) + four limits','Four limits + cost-aware execution']
for ri,(name,label) in enumerate(zip(['Trend10','Selected42','Unscaled42','Capped42','CappedCost42'],labels),1):
 a=m(name,'IS');b=m(name,'OOS')
 for ci,value in enumerate([label,f'{a.sharpe_zero_rf:.4f}',f'{b.sharpe_zero_rf:.4f}',f'{b.annual_turnover:.1f}×']):set_cell(grid[ri][ci],value)
replace_text(s,'Same 21-day endpoints. The report selected step 2 for its highest IS Sharpe after later results had been seen.',
 '21-day endpoint Sharpe; fixed 42 inputs. Caps / γ=5 are diagnostics only; later results had already been viewed.')
# 15: chart uses fresh42 capped/cost-aware returns, not the old66 results.
s=slides[15]
replace_text(s,'Removing caps helps historically','Net-cap removal helps historically')
replace_text(s,'Daily net Sharpe of the capped, cost-aware variant','Daily net Sharpe of the 42-input capped, cost-aware variant')
# 16: conclusion now names actual model.
replace_text(slides[16],'Higher Sharpe in both periods','Fixed 42 inputs: higher Sharpe in both periods')

notes={
 1:'Time:25seconds\nSelected portfolio now uses fixed42 screened ML inputs, not the original66-input version. Main comparison uses1976–2014and2015–May2025with58markets. This deck numerical source is outputs/ppt42_update/, not the old66-inputreport. We retain fixed30/20/20/30budgets and full21-dayrebalance.\n中文：当前选定IC+t筛选固定42输入方案。',
 2:'Time:55seconds\nSame58markets,dailyprices,monthlyreturnsandfourmacrofiles. Historical1976–2014; initialIC+t screen uses1976–pre2005knownlabels. Fixed42-input classifier predicts2005–2014outoftraining; keep same inputlist,refitbefore2015andfreeze. Researchweight/executioncomparisons used2005–2009calibrationand2010–2014validationbutwere not adopted. Later2015–May2025hasalreadybeenviewedandisnotanuntouchedholdout.\n中文：模型筛选、模型训练、配重实验和绩效统计的区间须分别说明。',
 4:'Time: 45 seconds\nThe four signal budgets remain30% daily trend,20% economic trend,20% independent negative skew and30% Extra Trees. The selected ML version is now fixed42-input IC+t screened, not the original66-input classifier. No learned signal-budget allocation or cost-aware execution is used in the selected final portfolio. It still targets10% predicted volatility, fully rebalances every21 business days and has no gross/net/class caps.\nSource: outputs/ppt42_update/.',
 6:'Time: 35 seconds\nThis page describes the candidate factor library, not the selected input count:25price-path plus6peer/residual measures give31raw factors. With31within-class ranks and4class flags, the candidate pool has66inputs. Only42 are retained by the pre2005 IC+t screen:20raw,18rank,4control flags. Do not say that all31raw factors enter the final ML model.\n完整候选因子名称见原备注及extra_trees.py；最终保留名单见outputs/ic_t_feature_filter/pre2005_screen.csv。',
 7:'Time: 35 seconds\nThe final classifier uses42inputs:20raw,18class ranks and4class controls. Screen only with1976through pre2005 known labels, requiring |mean monthly RankIC|>=.01 and direction-consistent |Newey-WestHACt6|>=1.96. PositiveIC needs positivet; negativeIC negativet. Four controls exempt. The input list stays fixed thereafter; the classifier is refitted before2015. This is not the38-input re-screen policy. The separate20%negative-skew sleeve remains unchanged even though its raw/rank inputs fail the ML t screen. Nominal individual t tests are not corrected for multiple testing.\n中文：候选66，筛后42＝20原始＋18排名＋4类别。只筛ML输入，独立负偏度20%不改。',
 8:'Time: 40 seconds\nMonthly historical returns become31raw candidates,31ranks and4class flags. A train-only IC+t screen retains42before fitting Extra Trees. Predict next monthly positive-return probability, map it to2p−1, divide by instrument volatility, normalize sleeve risk, combine with fixed30/20/20/30budgets and scale the book to10%ex-ante risk. A probability0.65 gives direction0.30, not30%NAV. Monthly nonprice signals use only the latest known month-end, decisions occur every21businessdays.\nSource: frozen42-input policy, outputs/ic_t_feature_filter/.',
 9:'Time: 30 seconds\nICscreen starts1976 and uses only labels strictly before firstDec2004formation; latest label2004-11-30. Initial classifier uses all original eligible early labels and predicts2005–2014 frozen. Keep the SAME42input list when refitting before2015; latest training label2014-11-28. Freeze the model after that. There is no pre2015 re-screen to38in the selected policy. Before2005MLbudget returns to trend.\nThe research has previously inspected later results; causal label timing does not restore a pristine holdout.',
 10:'Time: 35 seconds\nSelected specification is fixed42input ET, fixed30/20/20/30budgets,10%exante scaling and full21-day rebalances without exposure caps. Entire historical Sharpe1.2831vs baseline1.2225; later0.3567vs0.2430. Weight fitting and cost-aware execution were tested on42inputs; adding both gives laterSharpe0.3057 and is not adopted. Fixed42is a research choice made after later results had already been inspected. Small measured differences are not independent evidence of persistent outperformance.\nSources: outputs/ppt42_update/; outputs/ict42_portfolio_optimization/.',
}
notes[11]=f'''Time: 80 seconds
Use identical21-business-day endpoints. BaselineIS Sharpe{bis.sharpe_zero_rf:.4f}, selected42Sharpe{is42.sharpe_zero_rf:.4f}; gain{is42.sharpe_zero_rf-bis.sharpe_zero_rf:.4f}. IS annual arithmetic net return{bis.annual_mean_net_return:.2%}to{is42.annual_mean_net_return:.2%}; vol{bis.annual_volatility:.2%}to{is42.annual_volatility:.2%}. LaterSharpe{boos.sharpe_zero_rf:.4f}to{oos42.sharpe_zero_rf:.4f}, gain{oos42.sharpe_zero_rf-boos.sharpe_zero_rf:.4f}; mean return{boos.annual_mean_net_return:.2%}to{oos42.annual_mean_net_return:.2%}; vol{boos.annual_volatility:.2%}to{oos42.annual_volatility:.2%}. CAGR is different: selectedIS{is42.cagr:.2%}, later{oos42.cagr:.2%}. Differences sit within substantial sampling uncertainty.
中文：IS1.2831，OOS0.3567；表中的收益为算术年化，不是CAGR。
Source: outputs/ppt42_update/performance_and_decomposition.csv. Original report.md still describes the old66-input version; do not cite it as the numerical source for this updated deck.'''
notes[12]=f'''Time: 65 seconds
Each evaluation interval starts at$1. Endpointmaximumdrawdown: ISbaseline{abs(bis.max_endpoint_drawdown):.2%}, selected42{abs(is42.max_endpoint_drawdown):.2%}; laterbaseline{abs(boos.max_endpoint_drawdown):.2%}, selected42{abs(oos42.max_endpoint_drawdown):.2%}. Dailyselected42maximumdrawdown is{abs(is42.daily_max_drawdown):.2%}IS and{abs(oos42.daily_max_drawdown):.2%}later. Endpoint drawdowns omit intraperiod losses. Baseline daily drawdown is not supplied on the same basis.
中文：OOS端点回撤13.74%，日度回撤17.49%，不能混用。
Source: outputs/ppt42_update/aligned_period_returns.csv and selected42_daily_returns.csv.'''
notes[13]=f'''Time: 60 seconds
Selected42 lateraveragegross{oos42.average_gross:.2f}NAV andabsolute net{oos42.average_absolute_net:.2f}NAV. Annualturnover{oos42.annual_turnover:.2f}, annualtrading/rollcost{oos42.annual_cost:.2%}. Both this table and the construction table use the numberofmatched21-dayperiods/12as years. Baseline reference remains43.47turnover,1.79%cost,11.54gross,3.46net from daily_baseline_stats.csv. Figures have not been adjusted for financing or realistic marketimpact.
中文：gross11.31，绝对net6.59，换手48.83，成本1.88%。
Source: outputs/ppt42_update/performance_and_decomposition.csv; outputs/baseline/daily_baseline_stats.csv.'''
notes[14]='Time: 75 seconds\nRecomputed every row with the selected fixed42ML policy. Firstrow is10%target trend-only, NOT the11%coursebaseline; this explains its39.4turnover versus43.47coursebaseline onslide13. Subsequent rows: selected10%-scaled blend; sameblendunscaled; fourlimits; cappedgamma5costaware. Allvalues use21-dayendpoints and periodcount/12cost/turnover years. This is separate from uncappedgamma20execution shown as a rejected optimization experiment onslide10. No mixture of42and66input diagnostics.\n'
for name in ['Trend10','Selected42','Unscaled42','Capped42','CappedCost42']:
 a=m(name,'IS');b=m(name,'OOS');notes[14]+=f'{name}: ISSharpe{a.sharpe_zero_rf:.4f}, laterSharpe{b.sharpe_zero_rf:.4f}, laterturnover{b.annual_turnover:.1f}.\n'
notes[14]+='Source: outputs/ppt42_update/performance_and_decomposition.csv. Selection followed historical laterdata inspection; no untouchedtestclaim.'
notes[15]='Time: 60 seconds\nSeparate42-input cappedgamma5costaware diagnostic. These are DAILY Sharpe ratios, not the21-day endpointSharpe onslide14. Removegross,netorbothwhilekeepingothercontrols andcosts unchanged.\n'
for name in ['Both caps','No gross cap','No net cap','Neither cap']:
 a=caps[caps.variant.eq(name)&caps.period.eq('IS')].iloc[0];b=caps[caps.variant.eq(name)&caps.period.eq('OOS')].iloc[0]
 notes[15]+=f'{name}: ISdailySharpe{a.daily_sharpe:.4f}; later{b.daily_sharpe:.4f}.\n'
notes[15]+='Netcapremoval helpsIS; grossremoval alone slightlyreducesISSharpe. EveryremovalhurtslaterSharpe. Netcapchangesabout58.6%laterformationtargets; it rescalesallweights ratherthantrimsoneside.\nSource: outputs/ppt42_update/cap_sensitivity.csv.'
notes[16]='Time: 50 seconds\nThe selected fixed42-input, fixed-budget, full-rebalance strategy showsISSharpe1.2831andlater0.3567, versusbaseline1.2225and0.2430. It does not dominate everymetric: ISreturnlower anddrawdowndeeper, withsubstantialleverage. Smallgains remainwithinsamplinguncertainty. Laterdatahasbeenviewedrepeatedly, so donotclaimanuntouchedtest. Robustnessneedsgridanchorchecks,financing,impactandindependentdata. LongISincludespre2005yearswithoutactiveML.\nSource: outputs/ppt42_update/.'

# Append full candidate factor catalog to page6 notes without leaving obsolete selected-model claims.
oldnote6=E.fromstring(data['ppt/notesSlides/notesSlide6.xml'])
oldtext='\n'.join(oldnote6.xpath('//a:t/text()',namespaces=NS))
if 'Exact 31 raw feature names:' in oldtext:notes[6]+='\nExact 31 raw feature names:'+oldtext.split('Exact 31 raw feature names:',1)[1]

def write_notes(note_path,content,page):
 root=E.fromstring(data[note_path])
 for sh in root.findall('.//p:sp',NS):
  ph=sh.find('p:nvSpPr/p:nvPr/p:ph',NS)
  if ph is None:continue
  if ph.get('type')=='body':
   tx=sh.find('p:txBody',NS)
   for child in list(tx):
    if child.tag=='{'+A+'}p':tx.remove(child)
   for line in content.split('\n'):
    p=E.SubElement(tx,'{'+A+'}p');run=E.SubElement(p,'{'+A+'}r');rp=E.SubElement(run,'{'+A+'}rPr',lang='en-US',sz='1200');E.SubElement(rp,'{'+A+'}latin',typeface='Arial');E.SubElement(run,'{'+A+'}t').text=line
  elif ph.get('type')=='sldNum':
   ts=sh.xpath('.//a:t',namespaces=NS)
   if ts:ts[0].text=str(page)
 data[note_path]=dump(root)

# Correct original exported table frames: extents were fixed3,000,000EMU
# while table-grid/row totals differed, causing native layout to overlap captions.
for page,root in slides.items():
 for frame in root.findall('.//p:graphicFrame',NS):
  tab=frame.find('.//a:tbl',NS)
  if tab is None:continue
  ext=frame.find('p:xfrm/a:ext',NS)
  if ext is not None:
   ext.set('cx',str(sum(int(c.get('w'))for c in tab.findall('a:tblGrid/a:gridCol',NS))))
   ext.set('cy',str(sum(int(r.get('h'))for r in tab.findall('a:tr',NS))))
# Keep the very long existing slide4and14titles inside the right margin.
for page in [4,14]:
 first=slides[page].find('p:cSld/p:spTree/p:sp',NS)
 for rp in first.findall('.//a:rPr',NS):rp.set('sz','2200')
# Remove the original baseline sidebar's misplaced hanging bullets.
for pp in slides[3].findall('.//p:sp/p:txBody/a:p/a:pPr',NS):
 if pp.find('a:buChar',NS)is not None:
  for tag in ['a:buChar','a:buFont','a:buSzPct']:
   for child in pp.findall(tag,NS):pp.remove(child)
  E.SubElement(pp,'{'+A+'}buNone');pp.set('marL','0');pp.set('indent','0')

for page,root in slides.items():data[paths[page]]=dump(root)
for page,content in notes.items():
 sp=paths[page];part=Path(sp).name
 relpath='ppt/slides/_rels/'+part+'.rels';rr=E.fromstring(data[relpath])
 target=next(r.get('Target') for r in rr if r.get('Type')==R+'/notesSlide')
 note_path=posixpath.normpath(posixpath.join('ppt/slides',target))
 write_notes(note_path,content,page)
for name in ['image1.png','image2.png','image3.png','image4.png']:data['ppt/media/'+name]=(ROOT/'outputs/ppt42_update'/name).read_bytes()
with ZipFile(FILE,'w',ZIP_DEFLATED) as z:
 for name,blob in data.items():z.writestr(name,blob)
# Validate references and all XML; save16single-slide packages for native previews.
preview=Path('/private/tmp/orie_ppt42_preview');preview.mkdir(exist_ok=True)
with ZipFile(FILE) as z:
 assert z.testzip() is None
 for name in z.namelist():
  if name.endswith('.xml')or name.endswith('.rels'):E.fromstring(z.read(name))
for page in slides:
 one=deepcopy(pres);ids=one.find('p:sldIdLst',NS)
 for i,sid in enumerate(list(ids),1):
  if i!=page:ids.remove(sid)
 with ZipFile(preview/f'page_{page:02d}.pptx','w',ZIP_DEFLATED)as z:
  for name,blob in data.items():z.writestr(name,dump(one)if name=='ppt/presentation.xml' else blob)
print('Updated',FILE,'16pages; backup',BACK)
