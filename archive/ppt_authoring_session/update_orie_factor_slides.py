from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
from copy import deepcopy
from pathlib import Path
import shutil,re,posixpath

ROOT=Path('/Users/yawenvivianxia/Desktop/证件资料/ORIE 5260')
PATH=ROOT/'ppt/ORIE5260 Presentation.pptx'
BACKUP=Path('/private/tmp/ORIE5260 Presentation.before-factor-expansion.pptx')
if not BACKUP.exists():shutil.copy2(PATH,BACKUP)
with ZipFile(BACKUP) as z:data={n:z.read(n) for n in z.namelist()}
A='http://schemas.openxmlformats.org/drawingml/2006/main'
P='http://schemas.openxmlformats.org/presentationml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG='http://schemas.openxmlformats.org/package/2006/relationships'
CT='http://schemas.openxmlformats.org/package/2006/content-types'
NS={'a':A,'p':P,'r':R}
EMU=914400
NAVY='102B46';TEAL='008577';MUTED='526574';LIGHT='EFF6F6';PALE='F3F5F8';WHITE='FFFFFF'

def el(tag,**attrs):
 prefix,name=tag.split(':');return E.Element('{'+{'a':A,'p':P,'r':R}[prefix]+'}'+name,{k:str(v) for k,v in attrs.items()})
def sub(parent,tag,**attrs):
 x=el(tag,**attrs);parent.append(x);return x
def dump(root):return E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
def fill(parent,color):sub(sub(parent,'a:solidFill'),'a:srgbClr',val=color)

def shape(root,x,y,w,h,lines=(),size=15,color=NAVY,bold=False,bg=None,align='l',padding=0,shape='rect',name='Text'):
 tree=root.find('p:cSld/p:spTree',NS)
 sid=max([int(v) for v in tree.xpath('.//p:cNvPr/@id',namespaces=NS)]+[0])+1
 s=sub(tree,'p:sp');nv=sub(s,'p:nvSpPr');sub(nv,'p:cNvPr',id=sid,name=f'{name} {sid}');sub(nv,'p:cNvSpPr',txBox=1);sub(nv,'p:nvPr')
 sp=sub(s,'p:spPr');xf=sub(sp,'a:xfrm');sub(xf,'a:off',x=round(x*EMU),y=round(y*EMU));sub(xf,'a:ext',cx=round(w*EMU),cy=round(h*EMU))
 sub(sub(sp,'a:prstGeom',prst=shape),'a:avLst')
 if bg:fill(sp,bg)
 else:sub(sp,'a:noFill')
 sub(sub(sp,'a:ln'),'a:noFill')
 tx=sub(s,'p:txBody');bp=sub(tx,'a:bodyPr',wrap='square',anchor='t',lIns=round(padding*EMU),rIns=round(padding*EMU),tIns=round(padding*EMU),bIns=0)
 sub(bp,'a:noAutofit');sub(tx,'a:lstStyle')
 if isinstance(lines,str):lines=[lines]
 for line in lines or ['']:
  opts={} if isinstance(line,str) else line
  text=line if isinstance(line,str) else line.get('text','')
  pp=sub(tx,'a:p');ppr=sub(pp,'a:pPr',algn=align,marL=0,indent=0)
  sub(sub(ppr,'a:lnSpc'),'a:spcPct',val=110000)
  sub(sub(ppr,'a:spcAft'),'a:spcPts',val=opts.get('after',450));sub(ppr,'a:buNone')
  run=sub(pp,'a:r');rp=sub(run,'a:rPr',lang='en-US',sz=round(opts.get('size',size)*100),b='1' if opts.get('bold',bold) else '0')
  fill(rp,opts.get('color',color));sub(rp,'a:latin',typeface='Arial');sub(rp,'a:ea',typeface='Arial');sub(run,'a:t').text=text
 return s

def set_text(s,text):
 ts=s.xpath('.//a:t',namespaces=NS)
 ts[0].text=text
 for t in ts[1:]:t.text=''

def new_slide(title,page):
 root=E.fromstring(data['ppt/slides/slide6.xml']);tree=root.find('p:cSld/p:spTree',NS)
 shapes=list(tree)
 for s in shapes:
  txt=''.join(s.xpath('.//a:t/text()',namespaces=NS))
  if txt.startswith('Negative skew and Extra Trees'):set_text(s,title)
  elif txt=='06':set_text(s,f'{page:02d}')
  elif s.tag not in ['{'+P+'}nvGrpSpPr','{'+P+'}grpSpPr']:tree.remove(s)
 return root

def label(root,text,y=1.02):shape(root,.5,y,9,.35,text,size=13,color=MUTED)
def footer(root,text):shape(root,.5,4.96,8.85,.28,text,size=9,color=MUTED)
def card(root,x,y,w,h,title,body,size=13):
 shape(root,x,y,w,h,bg=LIGHT)
 shape(root,x+.14,y+.10,w-.28,.32,title,size=15,bold=True,color=TEAL)
 shape(root,x+.14,y+.43,w-.28,h-.46,[{'text':t,'after':0} for t in body],size=size)

slides=[];notes=[]
# Slide 6: research breadth, with counts and concrete factor names.
s=new_slide('Our factor library goes beyond momentum',6)
label(s,'31 raw factors = 25 price-path measures + 6 peer / residual measures')
cards=[
 ('Trend & price path  |  10','TSMOM; skip-month momentum; acceleration; persistence\nTrend efficiency; mean / vol; distance to high\nDrawdown; positive-month share; median / vol'),
 ('Reversal  |  3','1-month reversal; 3-month reversal\nLong-horizon reversal (months 36 to 12)'),
 ('Volatility & downside  |  5','Low volatility; low downside / upside risk\n3-to-12-month volatility compression\nLow volatility of volatility'),
 ('Tail shape  |  6','Negative skew; low kurtosis; low maximum return\nMild worst return; low tail loss; risk asymmetry'),
 ('Seasonality  |  1','Average same-calendar-month return\nfrom the previous five years'),
 ('Peer & residual information  |  6','Low peer beta / correlation; low residual volatility\nResidual momentum; peer-relative reversal\nPeer-relative skip-month momentum')]
for i,(title,body) in enumerate(cards):
 x=.5+(i%2)*4.58;y=1.47+(i//2)*1.09
 card(s,x,y,4.42,1.00,title,body.split('\n'),size=11.1 if i==0 else 11.6)
footer(s,'These are candidate inputs, not 31 separately funded strategies. Exact feature names are in speaker notes and extra_trees.py.')
slides.append(s)
notes.append('Time: 35 seconds\n我们并不是只做了负偏度。最终模型有31个原始因子：25个价格路径统计和6个同类/残差信息。按趋势、反转、波动风险、尾部、季节性、同类关系分组。它们是模型输入，不是31个独立配重策略。\nExact 31 raw feature names:\nTrend (10): TSMOM, XSMOM_12_1, ReturnPersistence_12m, TrendEfficiency_12m, TrendAcceleration_3m, MeanToVol_12m, NearWealthHigh_12m, ShallowDrawdown_12m, PositiveMonthShare_12m, MedianReturn_12m.\nReversal (3): Reversal_1m, Reversal_3m, LongReversal_36_12.\nVolatility (5): LowVol_12m, LowDownside_12m, LowUpsideRisk_12m, VolCompression_3_12, LowVolOfVol_12m.\nTail (6): NegativeSkew_12m, LowKurtosis_12m, LowMaxReturn_12m, MildWorstReturn_12m, LowTailLoss_12m, RiskAsymmetry_12m.\nSeasonality: Seasonality_5y.\nPeer (6): LowPeerBeta_36m, LowPeerCorrelation_36m, LowResidualVol_12m, ResidualMomentum_12m, PeerRelativeReversal_1m, PeerRelativeMomentum_12m.\nSource: extra_trees.py price_features() and peer_features(). Peer returns exclude the instrument itself.')
# Slide 7: distinguish model representation from standalone sleeve.
s=new_slide('Two roles: ML features and negative skew',7)
label(s,'The 66-feature classifier and the 20% negative-skew sleeve serve different roles')
shape(s,.5,1.47,4.34,3.16,bg=PALE)
shape(s,.67,1.62,4,.37,'Model representation: 66 inputs',size=18,bold=True,color=TEAL)
shape(s,.67,2.17,4,.43,'31 raw + 31 ranks + 4 class flags',size=17,bold=True)
shape(s,.67,2.83,4,1.56,[
 'Raw factors capture absolute return behavior.',
 'Ranks compare a market with its asset-class peers.',
 'Class flags identify equity, rates, FX or commodity.',
 'All 31 factors enter the model; they receive no separate sleeve budgets.'
],size=13)
shape(s,5.04,1.47,4.46,3.16,bg=LIGHT)
shape(s,5.21,1.62,4.12,.37,'Standalone negative skew: 20%',size=18,bold=True,color=TEAL)
shape(s,5.21,2.17,4.12,2.1,[
 '1  Compute negative skew from 12 monthly returns.',
 '2  Rank within class; center ranks around zero.',
 '3  Long relatively more negative-skew markets; short less negative-skew peers.',
 '4  Divide by volatility; normalize forecast risk.'
],size=13)
footer(s,'The standalone sleeve is one hypothesis. Its presence does not prove an incremental return benefit in every period.')
slides.append(s)
notes.append('Time: 35 seconds\n左边是模型输入：31个原始因子、31个类别内百分位排名、4个类别哑变量，共66个。注意31个是因子，不是31个因子类别。右边是独立负偏度策略，占20%信号预算；每个资产类别至少需要4个有效市场。负偏度也出现在ML输入里，因此去掉独立负偏度袖套，不等于删掉分类器中的负偏度特征。\nExact rank transformation in code: group by formation date and asset class; percentile rank minus 0.5. Negative-skew sleeve ranks are centered by their contemporaneous within-class mean. The four signal budgets are not risk contributions.\nSource: extra_trees.py forecasts(); negative_skew.py; report.md Sections3.3–3.4.')
# Slide 8: six-step pipeline, two parallel rows to avoid microscopic labels.
s=new_slide('From historical returns to the final portfolio',8)
label(s,'Monthly forecasts feed a daily-risk portfolio traded every 21 business days')
items=[
 ('1  Historical returns','Monthly price paths\nand same-class peer returns'),
 ('2  Factors + class ranks','31 raw factors + 31 ranks\n+ 4 class indicators'),
 ('3  Extra Trees','200 shallow randomized trees\nlearn nonlinear combinations'),
 ('4  Next-month probability','p = P(next monthly return > 0)\nThis is a forecast, not a return'),
 ('5  Direction → position','direction = 2p − 1\nDivide by volatility; risk-normalize'),
 ('6  Final combination','30% trend + 20% macro\n+ 20% skew + 30% ML')]
for i,(title,body) in enumerate(items):
 col=i%3;row=i//3;x=.5+col*3.08;y=1.55+row*1.43
 card(s,x,y,2.84,1.21,title,body.split('\n'),size=12)
 if col<2:shape(s,x+2.86,y+.46,.20,.35,'→',size=20,color=TEAL,bold=True,align='ctr')
shape(s,8.60,2.77,.35,.30,'↓',size=20,color=TEAL,bold=True,align='ctr')
# Explicit row continuation avoids a misleading 3-to-6 shortcut.
shape(s,.52,2.79,7.85,.20,'Continue 3 → 4 below; the probability is converted into a proposed position.',size=9,color=MUTED)
shape(s,.52,4.48,9,.31,'Example: p = 0.65 → direction +0.30; p = 0.50 → 0; p = 0.35 → −0.30',size=13,color=TEAL,bold=True)
footer(s,'Blend → 10% ex-ante risk scaling → full 21-business-day rebalance. The direction score is not a final NAV weight.')
slides.append(s)
notes.append('Time: 40 seconds\n流程：历史月度收益→31个原始因子及31个类别内排名，加4个类别标识→Extra Trees→下个月上涨概率→连续方向与仓位→四模块最终组合。p=0.65只代表方向分数0.30，不是直接持有30%净值。再除以工具波动率，做共同风险归一化，模型袖套以30%信号预算与其它模块相加，最后整本组合缩放至10%事前年化波动率。\n模型预测目标仍然是次月收益正负，交易日历则是每21营业日。两者不同：每次交易只使用已知的最近月末信号，风险矩阵来自此前252个日收益。最终主策略全量调仓、无敞口上限。\nSource: extra_trees.py extra_trees_sleeve(); run_final_strategy.py dated_sleeves(), final_target().')
# Slide 9: information timing.
s=new_slide('Chronological fits keep future labels out',9)
label(s,'One pre-2005 fit, one pre-2015 refit; no rolling refit during the later interval')
phases=[('Before 2005','Train the initial classifier','Only labels observed before\nthe first Dec-2004 formation.'),('2005–2014','Freeze the first fit','Generate out-of-training\nprobabilities for development\nand validation.'),('Before 2015 → later','Refit once, then freeze','Use only earlier labels;\nno 2015–2025 labels enter\nthe fitted classifier.')]
for i,(period,title,body) in enumerate(phases):
 x=.5+i*3.08
 shape(s,x,1.52,2.84,.43,period,size=18,color=TEAL,bold=True)
 card(s,x,2.08,2.84,1.73,title,body.split('\n'),size=12)
 if i<2:shape(s,x+2.87,2.67,.19,.4,'→',size=20,color=TEAL,bold=True)
shape(s,.5,4.05,9,.37,'Model: 200 trees  |  depth ≤ 6  |  min leaf = 30  |  max features = 0.7',size=15,bold=True)
shape(s,.5,4.55,9,.27,'Before 2005 there is no active ML forecast; its 30% budget returns to price trend.',size=12,color=MUTED)
footer(s,'Causal fitting prevents label leakage. It does not make repeatedly viewed later returns an untouched holdout.')
slides.append(s)
notes.append('Time: 30 seconds\n强调模型拟合没有用未来标签：最初模型只用2005年前已知标签；2005–2014预测期间不更新。2015前重训一次，随后冻结。实现中训练标签日期严格早于首次预测形成日，训练数据填补参数也在训练集上拟合。最终训练日志可查outputs/final_strategy/extra_trees_training_audit.csv。\n1976–2004没有ML的样本外预测，所以相应30%预算回到趋势。完整IS行并非四袖套从1976年开始全程同时运行。历史回测开发中我们已看过2015后数据；无标签泄露与整个研究过程保持未触碰样本外是两回事。\nSource: extra_trees.py forecasts(), report.md Section3.4 and limitations.')
# Slide 10: separate final specification from alternatives and avoid false attribution.
s=new_slide('Final specification and selection rationale',10)
label(s,'A fixed, reproducible specification; research alternatives remain separate')
card(s,.5,1.50,4.40,2.17,'Retained in the final submission',[
 'Negative skew: interpretable peer-selection sleeve (20%).',
 'ET66: nonlinear use of the full factor library (30%).',
 'Fixed 30 / 20 / 20 / 30 budgets; 10% ex-ante scaling.',
 'Full rebalance; no exposure caps.'
],size=12.7)
card(s,5.10,1.50,4.40,2.17,'Compared in the research',[
 'Factor substitutes and peer / cross-asset extensions.',
 'ET86, HistGB and Logistic model variants.',
 'Learned sleeve weights and cost-aware execution.',
 'No universal winner; fitted weights are not used.'
],size=12.7)
shape(s,.5,3.92,9,.35,'Final blend vs baseline: IS Sharpe 1.285 vs 1.222; later 0.343 vs 0.243',size=16,color=TEAL,bold=True)
shape(s,.5,4.42,9,.37,'Design rationale: interpretable peer selection + nonlinear forecasts in a reproducible fixed blend.',size=12.5)
footer(s,'The final construction was selected after later results had been viewed. Differences are within sampling uncertainty; execution optimization is an appendix comparison.')
slides.append(s)
notes.append('Time: 35 seconds\n选择解释必须诚实：最终提交保留可解释的独立负偏度袖套和我们的66特征Extra Trees，配重固定30/20/20/30。这不是声称ET66在所有时期最优，也不是采用连续配重优化学出的最优权重。ET86、HistGB、Logistic、因子替换与配重优化是研究过程中比较过的替代规格；不能把旧月度回测成绩混入现在日度版本。\n最终表对比是整套组合与baseline，不能把Sharpe增量单独归功于负偏度或ML。成本感知执行在后面的构造对照页及报告Appendix A中展示，未进入最终主策略。组合主策略是在后期数据已被看过后选定的，不应宣称全流程严格未触碰OOS。\n本页理由是角色互补、可解释和可复现的设计理由，不是重新构造未记录的盲选证据。\nSource: report.md Sections3.3–3.6, matched results and Appendix A; research history on combined-strategy. Existing slide10 explicitly disclosed selection after later returns were seen.')

# Clean up ambiguous pipeline routing: replace the downward arrow with a labeled return-to-left connector.
# Native line spans under the first row, then turns down to the fourth box.
s=slides[2];tree=s.find('p:cSld/p:spTree',NS)
for sh in list(tree):
 txt=''.join(sh.xpath('.//a:t/text()',namespaces=NS))
 if txt=='↓' or txt.startswith('Continue 3 → 4'):tree.remove(sh)
shape(s,.52,2.81,8.95,.18,'3 → 4: the model output becomes a probability, then a proposed position.',size=9,color=MUTED)

# Speaker notes, with the complete factor catalog in notes for slide6.
notes_template=E.fromstring(data['ppt/notesSlides/notesSlide6.xml'])
def make_notes(text,page):
 root=deepcopy(notes_template)
 for sh in root.findall('.//p:sp',NS):
  ph=sh.find('p:nvSpPr/p:nvPr/p:ph',NS)
  if ph is not None and ph.get('type')=='body':
   tx=sh.find('p:txBody',NS)
   for child in list(tx):
    if child.tag=='{'+A+'}p':tx.remove(child)
   for line in text.split('\n'):
    p=sub(tx,'a:p');run=sub(p,'a:r');rp=sub(run,'a:rPr',sz=1200,lang='en-US');sub(rp,'a:latin',typeface='Arial');sub(run,'a:t').text=line
  elif ph is not None and ph.get('type')=='sldNum':
   ts=sh.xpath('.//a:t',namespaces=NS)
   if ts:ts[0].text=str(page)
 return root

pres=E.fromstring(data['ppt/presentation.xml']);lst=pres.find('p:sldIdLst',NS)
original=list(lst)
assert len(original)==12
rels=E.fromstring(data['ppt/_rels/presentation.xml.rels'])
nextrel=max(int(r.get('Id')[3:]) for r in rels if re.match(r'rId\d+$',r.get('Id')))+1
nextid=max(int(s.get('id')) for s in original)+1
content=E.fromstring(data['[Content_Types].xml'])
parts=[6,13,14,15,16]
for j,(root,note,num) in enumerate(zip(slides,notes,parts)):
 data[f'ppt/slides/slide{num}.xml']=dump(root)
 data[f'ppt/notesSlides/notesSlide{num}.xml']=dump(make_notes(note,6+j))
 sr=E.Element('{'+PKG+'}Relationships',nsmap={None:PKG})
 E.SubElement(sr,'{'+PKG+'}Relationship',Id='rId1',Type=R+'/slideLayout',Target='../slideLayouts/slideLayout12.xml')
 E.SubElement(sr,'{'+PKG+'}Relationship',Id='rId2',Type=R+'/notesSlide',Target=f'../notesSlides/notesSlide{num}.xml')
 data[f'ppt/slides/_rels/slide{num}.xml.rels']=dump(sr)
 nr=E.Element('{'+PKG+'}Relationships',nsmap={None:PKG})
 E.SubElement(nr,'{'+PKG+'}Relationship',Id='rId1',Type=R+'/notesMaster',Target='../notesMasters/notesMaster1.xml')
 E.SubElement(nr,'{'+PKG+'}Relationship',Id='rId2',Type=R+'/slide',Target=f'../slides/slide{num}.xml')
 data[f'ppt/notesSlides/_rels/notesSlide{num}.xml.rels']=dump(nr)
 if j:
  rid='rId'+str(nextrel);nextrel+=1
  E.SubElement(rels,'{'+PKG+'}Relationship',Id=rid,Type=R+'/slide',Target=f'slides/slide{num}.xml')
  ss=el('p:sldId',id=nextid);nextid+=1;ss.set('{'+R+'}id',rid);lst.insert(5+j,ss)
  for part,kind in [(f'/ppt/slides/slide{num}.xml','slide'),(f'/ppt/notesSlides/notesSlide{num}.xml','notesSlide')]:
   E.SubElement(content,'{'+CT+'}Override',PartName=part,ContentType=f'application/vnd.openxmlformats-officedocument.presentationml.{kind}+xml')
# Update visible and notes page numbers for the untouched trailing slides.
for num in range(7,13):
 root=E.fromstring(data[f'ppt/slides/slide{num}.xml'])
 for sh in root.findall('.//p:sp',NS):
  if ''.join(sh.xpath('.//a:t/text()',namespaces=NS))==f'{num:02d}':set_text(sh,f'{num+4:02d}')
 data[f'ppt/slides/slide{num}.xml']=dump(root)
 # Keep original notes content, only update a slide-number placeholder if present.
 path=f'ppt/notesSlides/notesSlide{num}.xml'
 if path in data:
  note=E.fromstring(data[path])
  for sh in note.findall('.//p:sp',NS):
   ph=sh.find('p:nvSpPr/p:nvPr/p:ph',NS)
   if ph is not None and ph.get('type')=='sldNum':
    ts=sh.xpath('.//a:t',namespaces=NS)
    if ts:ts[0].text=str(num+4)
  data[path]=dump(note)
data['ppt/presentation.xml']=dump(pres);data['ppt/_rels/presentation.xml.rels']=dump(rels);data['[Content_Types].xml']=dump(content)
# Remove custom show refs to an obsolete slide only if there were any (none in original).
assert len(lst)==16
with ZipFile(PATH,'w',ZIP_DEFLATED) as z:
 for name,blob in data.items():z.writestr(name,blob)
# Validate all XML and all package relationship destinations.
with ZipFile(PATH) as z:
 assert z.testzip() is None
 names=set(z.namelist())
 for name in names:
  if name.endswith('.xml') or name.endswith('.rels'):E.fromstring(z.read(name))
  if name.endswith('.rels'):
   for r in E.fromstring(z.read(name)):
    if r.get('TargetMode')=='External':continue
    target=r.get('Target')
    if target.startswith('/'):dest=target[1:]
    else:
     base='' if name=='_rels/.rels' else posixpath.dirname(posixpath.dirname(name))
     dest=posixpath.normpath(posixpath.join(base,target))
    assert dest in names,(name,dest)
 # Original non-target slide payloads are preserved except page-number text.
 for num in list(range(1,6))+list(range(7,13)):
  old=E.fromstring(ZipFile(BACKUP).read(f'ppt/slides/slide{num}.xml'));new=E.fromstring(z.read(f'ppt/slides/slide{num}.xml'))
  oldtexts=old.xpath('//a:t/text()',namespaces=NS);newtexts=new.xpath('//a:t/text()',namespaces=NS)
  expected=[f'{num+4:02d}' if t==f'{num:02d}' and num>=7 else t for t in oldtexts]
  assert newtexts==expected,num
print('Updated',PATH,'slides',len(lst),'backup',BACKUP)
# Single-slide packages enable native QuickLook previews of inserted slides.
preview=Path('/private/tmp/orie_factor_slide_preview');preview.mkdir(exist_ok=True)
for num in parts:
 one=deepcopy(pres);one_lst=one.find('p:sldIdLst',NS)
 wanted=next(r.get('Id') for r in rels if r.get('Target')==f'slides/slide{num}.xml')
 for ss in list(one_lst):
  if ss.get('{'+R+'}id')!=wanted:one_lst.remove(ss)
 with ZipFile(preview/f'slide_{num}.pptx','w',ZIP_DEFLATED) as z:
  for name,blob in data.items():z.writestr(name,dump(one) if name=='ppt/presentation.xml' else blob)
