from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from copy import deepcopy
from lxml import etree as E
import ast,shutil,re,posixpath,json
import pandas as pd
ROOT=Path('/Users/yawenvivianxia/Desktop/证件资料/ORIE 5260');FILE=ROOT/'ppt/ORIE5260 Presentation.pptx'
BACK=Path('/private/tmp/ORIE5260 Presentation.before-factor-evidence.pptx')
if not BACK.exists():shutil.copy2(FILE,BACK)
with ZipFile(BACK)as z:data={n:z.read(n)for n in z.namelist()}
A='http://schemas.openxmlformats.org/drawingml/2006/main';P='http://schemas.openxmlformats.org/presentationml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships';PKG='http://schemas.openxmlformats.org/package/2006/relationships';CT='http://schemas.openxmlformats.org/package/2006/content-types'
NS={'a':A,'p':P,'r':R};EMU=914400;NAVY='102B46';TEAL='008577';MUTED='526574';LIGHT='EFF6F6';PALE='F3F5F8';WHITE='FFFFFF'
# Reuse the native editable-shape helpers used for the previous expansion.
tree=ast.parse(Path('/private/tmp/update_orie_factor_slides.py').read_text());functions=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in ['el','sub','fill','shape','set_text']]
exec(compile(ast.Module(body=functions,type_ignores=[]),'<shape_helpers>','exec'),globals())
def dump(root):return E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
def newroot(title,page):
 root=E.fromstring(data['ppt/slides/slide13.xml']);tree=root.find('p:cSld/p:spTree',NS)
 for sh in list(tree):
  text=''.join(sh.xpath('.//a:t/text()',namespaces=NS))
  if text.startswith('Two roles:'):
   set_text(sh,title)
   for rp in sh.findall('.//a:rPr',NS):rp.set('sz','2200'if len(title)>50 else'2400')
  elif text=='07':set_text(sh,f'{page:02d}')
  elif sh.tag not in ['{'+P+'}nvGrpSpPr','{'+P+'}grpSpPr']:tree.remove(sh)
 return root
rels_new={}

def nextshape(root):return max(int(v)for v in root.xpath('//p:cNvPr/@id',namespaces=NS))+1

def picture(root,part,name,x,y,w,h):
 rels=rels_new[part];rid='rId'+str(max(int(v.get('Id')[3:])for v in rels)+1)
 E.SubElement(rels,'{'+PKG+'}Relationship',Id=rid,Type=R+'/image',Target='../media/'+name)
 source=ROOT/'outputs/ppt_factor_model_evidence'/name;data['ppt/media/'+name]=source.read_bytes()
 tree=root.find('p:cSld/p:spTree',NS);pic=sub(tree,'p:pic');nv=sub(pic,'p:nvPicPr');sub(nv,'p:cNvPr',id=nextshape(root),name=name);sub(sub(nv,'p:cNvPicPr'),'a:picLocks',noChangeAspect='1');sub(nv,'p:nvPr')
 bf=sub(pic,'p:blipFill');blip=sub(bf,'a:blip');blip.set('{'+R+'}embed',rid);sub(sub(bf,'a:stretch'),'a:fillRect')
 sp=sub(pic,'p:spPr');xf=sub(sp,'a:xfrm');sub(xf,'a:off',x=round(x*EMU),y=round(y*EMU));sub(xf,'a:ext',cx=round(w*EMU),cy=round(h*EMU));sub(sub(sp,'a:prstGeom',prst='rect'),'a:avLst')

def line(root,x1,y1,x2,y2,arrow=False):
 tree=root.find('p:cSld/p:spTree',NS);sid=nextshape(root);sp=sub(tree,'p:cxnSp');nv=sub(sp,'p:nvCxnSpPr');sub(nv,'p:cNvPr',id=sid,name=f'Connector{sid}');sub(nv,'p:cNvCxnSpPr');sub(nv,'p:nvPr')
 pr=sub(sp,'p:spPr');xf=sub(pr,'a:xfrm')
 if (x2-x1)*(y2-y1)<0:xf.set('flipV','1')
 sub(xf,'a:off',x=round(min(x1,x2)*EMU),y=round(min(y1,y2)*EMU));sub(xf,'a:ext',cx=max(1,round(abs(x2-x1)*EMU)),cy=max(1,round(abs(y2-y1)*EMU)))
 sub(sub(pr,'a:prstGeom',prst='line'),'a:avLst');ln=sub(pr,'a:ln',w='19050');fill(ln,TEAL)
 if arrow:sub(ln,'a:tailEnd',type='triangle',w='sm',len='sm')

def card(root,x,y,w,h,title,body):
 shape(root,x,y,w,h,bg=LIGHT)
 shape(root,x+.12,y+.08,w-.24,.28,title,size=14,color=TEAL,bold=True)
 shape(root,x+.12,y+.42,w-.24,h-.46,[{'text':s,'after':0}for s in body],size=11.5)

def new_table(root,values,x,y,widths,rowheight=.255):
 tree=root.find('p:cSld/p:spTree',NS);sid=nextshape(root);g=sub(tree,'p:graphicFrame');nv=sub(g,'p:nvGraphicFramePr');sub(nv,'p:cNvPr',id=sid,name=f'Model table{sid}');sub(nv,'p:cNvGraphicFramePr');sub(nv,'p:nvPr')
 xf=sub(g,'p:xfrm');sub(xf,'a:off',x=round(x*EMU),y=round(y*EMU));sub(xf,'a:ext',cx=round(sum(widths)*EMU),cy=round(len(values)*rowheight*EMU))
 graphic=sub(g,'a:graphic');gd=sub(graphic,'a:graphicData',uri='http://schemas.openxmlformats.org/drawingml/2006/table');tbl=sub(gd,'a:tbl');sub(tbl,'a:tblPr',firstRow='1',bandRow='0');grid=sub(tbl,'a:tblGrid')
 for w in widths:sub(grid,'a:gridCol',w=round(w*EMU))
 for ri,row in enumerate(values):
  tr=sub(tbl,'a:tr',h=round(rowheight*EMU))
  for ci,text in enumerate(row):
   tc=sub(tr,'a:tc');tx=sub(tc,'a:txBody');sub(tx,'a:bodyPr',anchor='ctr');sub(tx,'a:lstStyle');p=sub(tx,'a:p');pp=sub(p,'a:pPr',algn='l'if ci==0 else'ctr');sub(sub(pp,'a:lnSpc'),'a:spcPct',val='100000');sub(sub(pp,'a:spcAft'),'a:spcPts',val='0');sub(pp,'a:buNone')
   run=sub(p,'a:r');rp=sub(run,'a:rPr',lang='en-US',sz='1150',b='1'if ri==0 or ci==1 else'0');fill(rp,WHITE if ri==0 else NAVY);sub(rp,'a:latin',typeface='Arial');sub(run,'a:t').text=str(text)
   cp=sub(tc,'a:tcPr',marL='45720',marR='45720',marT='12700',marB='12700');fill(cp,NAVY if ri==0 else PALE if ri%2==0 else WHITE)

notes={};new={}
for part in [17,18,19]:
 rels=E.Element('{'+PKG+'}Relationships',nsmap={None:PKG});E.SubElement(rels,'{'+PKG+'}Relationship',Id='rId1',Type=R+'/slideLayout',Target='../slideLayouts/slideLayout12.xml');E.SubElement(rels,'{'+PKG+'}Relationship',Id='rId2',Type=R+'/notesSlide',Target=f'../notesSlides/notesSlide{part}.xml');rels_new[part]=rels
# New page8: one screening-method page, with full t-stat formula and two charts.
s=newroot('Filter on IC strength and directional evidence',8)
shape(s,.5,1.05,9,.30,'66 candidate inputs → 42 retained; screening uses only pre-2005 labels',size=13,color=MUTED)
shape(s,.5,1.47,4.5,.34,'Fix direction, then test the signed IC mean',size=14,color=TEAL,bold=True)
picture(s,17,'directional_t_formula.png',.5,1.91,4.55,2.12)
shape(s,.5,4.04,4.45,.80,bg=LIGHT)
shape(s,.63,4.13,4.19,.66,[{'text':'Keep |mean IC| ≥ 0.01 and t-direction ≥ 1.96.','after':0},{'text':'Four class controls stay; never screen on OOS.','after':0}],size=12.2,bold=True)
shape(s,.5,4.90,4.5,.22,'γℓ: lag-ℓ autocovariance of signed IC; T: training months.',size=9.1,color=MUTED)
shape(s,5.25,1.47,4.25,.27,'Training screen: 62 numeric inputs',size=12.5,color=TEAL,bold=True)
picture(s,17,'screen_scatter.png',5.25,1.77,4.25,1.70)
shape(s,5.25,3.50,4.25,.27,'Validation: 16/20 raw factors retain direction',size=11.5,color=TEAL,bold=True)
picture(s,17,'signed_ic_validation.png',5.25,3.80,4.25,1.29)
shape(s,.5,5.14,8.8,.21,'Validation signed IC = 0.0185, HAC t = 1.08: direction partly persists, but the 95% CI crosses zero. Training tests are uncorrected.',size=8.8,color=MUTED)
new[17]=s
notes[17]='''Time:55seconds
筛选是用训练期平均月度横截面RankIC的绝对值至少0.01，同时方向调整后的Newey–West t至少1.96。符号s_j只由训练期平均IC确定，q_jt=s_j IC_jt；正IC保留正t，负IC保留负t。计算月度IC，不是把工具和月份摊平当独立样本。HAC采用6滞后Bartlett权重：gamma_l=T^-1 sum_{t=l+1}^T(q_t-qbar)(q_{t-l}-qbar)，SE²=(gamma0+2sum_{l=1}^6(1-l/7)gamma_l)/T。各因子有效月数略有不同。t检验的是方向IC均值相对自相关稳健标准误，不是直接给未来稳定性打保证。
先用1976–2004严格已知标签筛选；4类别控制不筛，62数值输入剩38，加4控制共42。阈值不按2015年后表现调节，也没有多重检验校正。
右上散点是62数值输入的训练IC幅度与HACt，38保留；右下只展示20个保留原始因子的方向IC月序列的等权均值，避免把原始及排名当成独立证据。16/20原始因子在2005–2014均值方向与训练相同。训练平均方向IC0.0656、t6.84；验证0.0185、t1.08，95%区间[-0.0152,0.0522]跨零。训练结果经过筛选有选择偏差，不能凭训练显著性宣布稳健。这个平均不是可交易组合IC，也不是ExtraTrees模型IC。
Sources: outputs/ppt_factor_model_evidence/directional_ic_statistics.csv; selected20_factor_evidence.csv; outputs/ic_t_feature_filter/pre2005_screen.csv. Validation shows weaker evidence; do not describe all factors as proven robust.'''
# New page10: native editable branching tree plus probability aggregation.
s=newroot('How Extra Trees turns 42 inputs into a probability',10)
shape(s,.5,1.05,9,.30,'Predict next-month return sign; average 200 randomized classification trees',size=13,color=MUTED)
shape(s,.5,2.12,1.60,1.17,bg=LIGHT)
shape(s,.62,2.25,1.36,.30,'42 inputs',size=18,color=TEAL,bold=True,align='ctr')
shape(s,.61,2.71,1.38,.43,['20 raw + 18 ranks','+ 4 class flags'],size=11,align='ctr')
line(s,2.12,2.70,2.55,2.70,True)
shape(s,2.60,1.57,2.43,.30,'One of 200 randomized trees',size=12.1,color=TEAL,bold=True,align='ctr')
shape(s,3.10,2.02,1.43,.45,'feature k ≤ cut c?',size=12,bg=PALE,align='ctr',padding=.06)
line(s,3.65,2.48,2.99,2.94);line(s,3.98,2.48,4.63,2.94)
shape(s,2.62,2.96,.94,.43,'Yes branch',size=10.7,bg=LIGHT,align='ctr',padding=.07)
shape(s,4.15,2.96,.94,.43,'No branch',size=10.7,bg=LIGHT,align='ctr',padding=.07)
shape(s,2.61,3.48,2.49,.42,'Leaf probability: p_b = N⁺ / N',size=12,color=NAVY,align='ctr')
shape(s,3.06,2.49,.42,.24,'yes',size=9.5,color=MUTED)
shape(s,4.30,2.49,.40,.24,'no',size=9.5,color=MUTED)
line(s,5.14,2.70,5.50,2.70,True)
shape(s,5.56,2.12,1.67,1.17,bg=LIGHT)
shape(s,5.70,2.25,1.39,.28,'Average trees',size=14,color=TEAL,bold=True,align='ctr')
shape(s,5.67,2.76,1.45,.30,'p = (Σ p_b) / 200',size=12.0,align='ctr')
line(s,7.28,2.70,7.63,2.70,True)
shape(s,7.69,2.12,1.81,1.17,bg=LIGHT)
shape(s,7.81,2.25,1.57,.28,'Direction',size=14,color=TEAL,bold=True,align='ctr')
shape(s,7.81,2.69,1.57,.30,'2p − 1',size=18,bold=True,align='ctr')
card(s,.5,4.05,4.4,.84,'Nonlinear combinations',['Random features and cut points create conditional splits.'])
card(s,5.1,4.05,4.4,.84,'Controls on complexity',['Depth ≤ 6; leaf ≥ 30; max_features = 0.7.'])
shape(s,.5,5.12,8.8,.22,'Training-only median imputation; frozen chronological fits. Probability is not expected return; the direction is then volatility-adjusted.',size=9.1,color=MUTED)
new[18]=s
roots=json.loads((ROOT/'outputs/ppt_factor_model_evidence/tree_root_examples.json').read_text())
notes[18]='''Time:50seconds
ExtraTrees分类器的目标是r_{i,t+1}>0，输入是42个历史因子表示。每棵树随机选候选特征并使用随机切分阈值，再按Gini准则在候选切分里选择；图是机制示意，不是把一个真实树的全深度画出来。叶子输出其训练样本的正收益比例；200棵树平均得到p。最终方向2p−1，再除以工具波动、归一化风险并以30%信号预算进入组合。p不是预期收益，0.65不代表30%净值仓位。
参数与最终模型一致：200trees,max_depth6,min_samples_leaf30,max_features0.7,seed5260。中位数填补器只在训练样本拟合。ExtraTrees默认bootstrap=False，本实现并不对训练行做随机森林式bootstrap；随机性来自特征和阈值。相对RandomForest的差别不仅是树数量。没有通过验证/OOS调这些参数。
The diagram demonstrates nonlinear/conditional splits, not a claim that a specific interaction has been causally established. Actual first-root examples from the pre2005 fitted classifier are recorded below for inspection:
'''+json.dumps(roots,indent=2)+'\nSource: extra_trees.py; outputs/ppt_factor_model_evidence/model_training_audit.json. All comparison models fit the same rows and42features.'
# New page12: honest same-input validation PnL, metrics and limitations.
s=newroot('Candidate models: matched validation net PnL',12)
shape(s,.5,1.05,9,.30,'Pre-2005 fits, frozen through 2005–2014; only the 30% ML sleeve changes',size=13,color=MUTED)
picture(s,19,'candidate_model_pnl.png',.5,1.48,9,2.10)
perf=pd.read_csv(ROOT/'outputs/ppt_factor_model_evidence/validation_model_performance.csv').set_index('model')
cls=pd.read_csv(ROOT/'outputs/ppt_factor_model_evidence/validation_classification.csv').set_index('model')
order=['ExtraTrees','RandomForest','HistGB','Logistic']
values=[['Validation metric']+order,
 ['Net Sharpe']+[f'{perf.loc[n,"sharpe_zero_rf"]:.4f}'for n in order],
 ['Endpoint max DD']+[f'{perf.loc[n,"max_endpoint_drawdown"]:.2%}'for n in order],
 ['Prediction AUC']+[f'{cls.loc[n,"auc"]:.4f}'for n in order]]
new_table(s,values,.5,3.73,[1.8,1.8,1.8,1.8,1.8],rowheight=.255)
shape(s,.5,4.91,9,.27,'Extra Trees: highest AUC and smallest drawdown; Logistic: highest portfolio Sharpe.',size=12.3,color=TEAL,bold=True)
shape(s,.5,5.22,8.8,.18,'Same 42 inputs, budgets, 10% risk target, 21-day calendar and costs. Validation is not the full-IS or OOS interval; no universal winner.',size=8.6,color=MUTED)
new[19]=s
notes[19]='''Time:55seconds
This is a NEW apples-to-apples validation benchmark, not a selection using2015–2025. Allfourmodels use the same42features, identical eligible training rows and labels strictly before the firstDec2004formation; then freeze2005–2014. Everycurve is the wholefour-sleeveportfolio with30%ML, same10%risk scaling, noexposurecaps, full21-dayrebalances and nettrading/rollcost. The other70%signals are unchanged. Curves are not standalone classifier returns.
ExtraTrees: validationSharpe1.0112,maxendpointDD−10.24%,AUC0.5500. RandomForest:0.9728,−11.05%,0.5435. HistGB:1.0019,−11.27%,0.5430. Logistic:1.0353,−10.94%,0.5491. ExtraTrees has the shallowest maximumdrawdown and highestAUC in this sample; Logistic has the highestportfolioSharpe and CAGR. Differences are small; no claim of statistical superiority or that all tree models beat the linear model. Do not hide Logistic or relabel this as evidence ET is universally best.
2005–2014contains12421-dayperiods; theseSharpefigures are not the selectedportfolio's fullIS1.2831 or later0.3567. The selected final42ExtraTrees strategy remains unchanged by this supplementary benchmark. No laterperiod model curves are generated here.
Hyperparameters are preserved from research alternatives: RF200trees/depth6/leaf30/maxfeatures.7; HistGB100iterations/depth3/8leaves/minleaf100/l2=10/lr.05/noearlystopping; LogisticC.1/maxiter3000/trainstandardization. Allseed5260,medianimputation fit only ontraining. ETpredictions and generatedportfolio match the earlier42-input results.
Sources: outputs/ppt_factor_model_evidence/validation_model_performance.csv, validation_classification.csv, model_training_audit.json. This comparison shows trade-offs, not a guarantee of prediction or future profitability.'''

# Insert after original pages7,8,9: new pages8,10,12.
pres=E.fromstring(data['ppt/presentation.xml']);lst=pres.find('p:sldIdLst',NS);old_ids=list(lst);assert len(old_ids)==16
rels=E.fromstring(data['ppt/_rels/presentation.xml.rels']);nextrel=max(int(r.get('Id')[3:])for r in rels if re.fullmatch(r'rId\d+',r.get('Id')))+1
nextid=max(int(v.get('id'))for v in old_ids)+1
ct=E.fromstring(data['[Content_Types].xml']);new_ids={}
for part in [17,18,19]:
 rid='rId'+str(nextrel);nextrel+=1
 E.SubElement(rels,'{'+PKG+'}Relationship',Id=rid,Type=R+'/slide',Target=f'slides/slide{part}.xml')
 sid=E.Element('{'+P+'}sldId',id=str(nextid));nextid+=1;sid.set('{'+R+'}id',rid);new_ids[part]=sid
 for kind,folder in [('slide','slides'),('notesSlide','notesSlides')]:E.SubElement(ct,'{'+CT+'}Override',PartName=f'/ppt/{folder}/{kind}{part}.xml',ContentType=f'application/vnd.openxmlformats-officedocument.presentationml.{kind}+xml')
 data[f'ppt/slides/slide{part}.xml']=dump(new[part]);data[f'ppt/slides/_rels/slide{part}.xml.rels']=dump(rels_new[part])
for sid in list(lst):lst.remove(sid)
insert={7:17,8:18,9:19};old_to_new={};page_parts={};lookup={r.get('Id'):r.get('Target')for r in rels}
for oldpage,sid in enumerate(old_ids,1):
 lst.append(sid);page=len(lst);old_to_new[oldpage]=page;target=lookup[sid.get('{'+R+'}id')];partpath=target.lstrip('/')if target.startswith('/')else'ppt/'+target;page_parts[page]=partpath
 if oldpage in insert:lst.append(new_ids[insert[oldpage]]);page_parts[len(lst)]=f'ppt/slides/slide{insert[oldpage]}.xml'
assert len(lst)==19
# Update all existing visible page numbers and cross-references in notes.
for oldpage,newpage in old_to_new.items():
 path=page_parts[newpage];root=E.fromstring(data[path])
 for sh in root.findall('.//p:sp',NS):
  ts=sh.xpath('.//a:t',namespaces=NS)
  if ''.join(t.text or''for t in ts)==f'{oldpage:02d}':set_text(sh,f'{newpage:02d}')
 data[path]=dump(root)
 note_rel='ppt/slides/_rels/'+Path(path).name+'.rels'
 nr=E.fromstring(data[note_rel]);target=next(r.get('Target')for r in nr if r.get('Type')==R+'/notesSlide');note_path=posixpath.normpath(posixpath.join('ppt/slides',target))
 note=E.fromstring(data[note_path])
 for t in note.xpath('//a:t',namespaces=NS):
  if t.text:t.text=re.sub(r'(slide\s*)(\d+)',lambda m:m.group(1)+str(old_to_new.get(int(m.group(2)),int(m.group(2)))),t.text,flags=re.I)
 for sh in note.findall('.//p:sp',NS):
  ph=sh.find('p:nvSpPr/p:nvPr/p:ph',NS)
  if ph is not None and ph.get('type')=='sldNum':
   ts=sh.xpath('.//a:t',namespaces=NS)
   if ts:ts[0].text=str(newpage)
 data[note_path]=dump(note)
# New notes cloned from an existing compatible notes body.
for part,page in [(17,8),(18,10),(19,12)]:
 note=E.fromstring(data['ppt/notesSlides/notesSlide13.xml'])
 for sh in note.findall('.//p:sp',NS):
  ph=sh.find('p:nvSpPr/p:nvPr/p:ph',NS)
  if ph is None:continue
  if ph.get('type')=='body':
   tx=sh.find('p:txBody',NS)
   for child in list(tx):
    if child.tag=='{'+A+'}p':tx.remove(child)
   for line_ in notes[part].split('\n'):
    p=E.SubElement(tx,'{'+A+'}p');run=E.SubElement(p,'{'+A+'}r');E.SubElement(run,'{'+A+'}rPr',sz='1200',lang='en-US');E.SubElement(run,'{'+A+'}t').text=line_
  elif ph.get('type')=='sldNum':
   ts=sh.xpath('.//a:t',namespaces=NS)
   if ts:ts[0].text=str(page)
 data[f'ppt/notesSlides/notesSlide{part}.xml']=dump(note)
 nr=E.Element('{'+PKG+'}Relationships',nsmap={None:PKG});E.SubElement(nr,'{'+PKG+'}Relationship',Id='rId1',Type=R+'/notesMaster',Target='../notesMasters/notesMaster1.xml');E.SubElement(nr,'{'+PKG+'}Relationship',Id='rId2',Type=R+'/slide',Target=f'../slides/slide{part}.xml')
 data[f'ppt/notesSlides/_rels/notesSlide{part}.xml.rels']=dump(nr)
data['ppt/presentation.xml']=dump(pres);data['ppt/_rels/presentation.xml.rels']=dump(rels);data['[Content_Types].xml']=dump(ct)
with ZipFile(FILE,'w',ZIP_DEFLATED)as z:
 for name,blob in data.items():z.writestr(name,blob)
# Full package-reference checks and native preview packages.
with ZipFile(FILE)as z:
 assert z.testzip()is None;names=set(z.namelist())
 for name in names:
  if name.endswith('.xml')or name.endswith('.rels'):E.fromstring(z.read(name))
  if name.endswith('.rels'):
   for rel in E.fromstring(z.read(name)):
    if rel.get('TargetMode')=='External':continue
    target=rel.get('Target');base=''if name=='_rels/.rels'else posixpath.dirname(posixpath.dirname(name));dest=target.lstrip('/')if target.startswith('/')else posixpath.normpath(posixpath.join(base,target));assert dest in names,(name,dest)
preview=Path('/private/tmp/orie_evidence_preview');preview.mkdir(exist_ok=True)
for page in range(1,20):
 one=deepcopy(pres);ids=one.find('p:sldIdLst',NS)
 for i,sid in enumerate(list(ids),1):
  if i!=page:ids.remove(sid)
 with ZipFile(preview/f'page_{page:02d}.pptx','w',ZIP_DEFLATED)as z:
  for name,blob in data.items():z.writestr(name,dump(one)if name=='ppt/presentation.xml'else blob)
(ROOT/'outputs/ppt_factor_model_evidence/page_mapping.json').write_text(json.dumps(old_to_new,indent=2))
print('Updated19pages. Added8screening,10tree,12modelPnL. Backup:',BACK)
