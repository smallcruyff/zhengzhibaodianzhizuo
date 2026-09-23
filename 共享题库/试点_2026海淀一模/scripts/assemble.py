from pathlib import Path
from PIL import Image
import json,hashlib,html
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads((ROOT/p).read_text())
def save(p,d):
 f=ROOT/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(d,ensure_ascii=False,indent=2))
def crop(page,box,name,role='试卷'):
 src=ROOT/f'assets/pages/{role}/p{page:02}_embedded01.png' if role=='试卷' else ROOT/f'assets/pages/{role}/p{page:02}.png'
 im=Image.open(src);x0,y0,x1,y1=box;assert 0<=x0<x1<=1 and 0<=y0<y1<=1
 f=ROOT/f'assets/crops/{name}.png';im.crop((round(x0*im.width),round(y0*im.height),round(x1*im.width),round(y1*im.height))).save(f);return str(f.relative_to(ROOT))
def textof(b):
 parts=[]
 if b.get('text'):parts.append(b['text'])
 if b.get('caption'):parts.append(b['caption'])
 if b.get('alt'):parts.append(b['alt'])
 parts+=b.get('paragraphs',[])
 if b.get('headers'):parts.append(' | '.join(str(x) for x in b['headers']))
 for r in b.get('rows',[]):parts.append(' | '.join(str(x) for x in r))
 return '\n'.join(parts)
def mdblock(b):
 t=b.get('type','paragraph');out=[]
 if b.get('caption'):out.append('**'+b['caption']+'**')
 if b.get('text'):out.append(b['text'])
 if b.get('paragraphs'):out.extend(b['paragraphs'])
 if t=='table':
  h=b.get('headers',[]);rows=b.get('rows',[]);lines=[]
  if h:lines+=['| '+' | '.join(str(c) for c in h)+' |','| '+' | '.join('---' for _ in h)+' |']
  elif rows:lines+=['| '+' | '.join('列'+str(i+1) for i in range(len(rows[0])))+' |','| '+' | '.join('---' for _ in rows[0])+' |']
  lines+=['| '+' | '.join(str(c).replace('\n','<br>') for c in r)+' |' for r in rows]
  out.append('\n'.join(lines))
  if b.get('merged_cells'):out.append('原表合并单元格（行列从0起；保留共享条件）：'+json.dumps(b['merged_cells'],ensure_ascii=False))
 if t=='figure':
  out.append('!['+b.get('caption',b.get('alt','原图'))+']('+str(ROOT/b['asset'])+')')
  if b.get('alt'):out.append('图像检索描述（非原文）：'+b['alt'])
 if b.get('asset') and t!='figure':out.append('[对应原图]('+str(ROOT/b['asset'])+')')
 if b.get('data_policy'):out.append('读取限制：'+b['data_policy'])
 return '\n\n'.join(out)
MC_MODULES={1:['必修一','必修四文化'],2:['必修四哲学','必修四文化'],3:['选必三推理','选必一'],4:['必修四文化','必修四哲学'],5:['必修四哲学'],6:['选必三推理'],7:['必修四哲学','选必三思维'],8:['必修三','必修四哲学'],9:['必修三','选必二'],10:['选必二'],11:['选必二'],12:['必修二'],13:['必修二'],14:['必修二','选必一'],15:['选必一']}
MC_TAGS={1:['初心使命','长征精神'],2:['意识','审美','自然'],3:['思维的间接性','和平','国家利益'],4:['文化载体','整体与部分'],5:['社会历史条件','价值判断'],6:['演绎推理','三段论'],7:['辩证否定','客观条件','系统优化'],8:['党的性质','政绩观','调查研究'],9:['政府公共服务','公共法律服务'],10:['土地经营权','侵权','合同形式','行政复议'],11:['夫妻财产','家务补偿','举证','上诉'],12:['人工智能','手搓经济','生产效率'],13:['能源结构','绿色发展','增长率'],14:['未来能源','新质生产力','能源安全'],15:['国际关系','联合国','全球治理']}
CLAIM_MODULES={1:[['必修一'],['必修一'],['必修四文化'],['必修四文化']],2:[['必修四哲学','必修四文化'],['必修四哲学'],['必修四哲学'],['必修四哲学','必修四文化']],3:[['选必三推理'],['选必三推理'],['选必一'],['选必一']],4:[['必修四文化'],['必修四哲学'],['必修四哲学'],['必修四文化']],5:[['必修四哲学']]*4,6:[['选必三推理']]*4,7:[['必修四哲学','选必三思维'],['必修四哲学'],['必修四哲学'],['必修四哲学']],8:[['必修三'],['必修四哲学'],['必修四哲学'],['必修三']],9:[['选必二'],['必修三'],['必修三'],['必修三']],10:[['选必二']]*4,11:[['选必二']]*4,12:[['必修二']]*4,13:[['必修二']]*4,14:[['必修二'],['必修二'],['必修二'],['选必一']],15:[['选必一']]*4}
MC_MODULES[1].append('必修三')
CLAIM_MODULES[1][1].append('必修三')
MC_MODULES[3].append('必修四哲学')
CLAIM_MODULES[3][1].append('必修四哲学')
mc=load('data/mc_reviewed.json')['questions'];sub=load('data/subjective.json')['questions'];rr=load('data/rubric_reviewed.json')
assert [q['number'] for q in mc]==list(range(1,16))
parents=[];items=[];claims=[]
for q in mc:
 n=q['number'];blocks=[]
 if n in [13,14]:blocks.append({'id':f'{n}.shared','type':'paragraph','text':'能源安全事关经济社会发展全局。回答第13、14题。','shared_material_id':'energy-common'})
 for i,t in enumerate(q['stem_paragraphs']):blocks.append({'id':f'{n}.p{i}','type':'paragraph','text':t})
 for i,t in enumerate(q.get('tables',[])):
  tb=dict(t,id=f'{n}.table{i}',type='table',text=t.get('caption',''),asset=crop(t['source_page'],t['bbox_normalized'],f'Q{n}-table{i}'))
  if n==4:blocks.insert(0,tb)
  else:blocks.append(tb)
 # Preserve boxes as editable text, with one source crop; do not repeat the same material as a figure.
 if n==3:
  ps=blocks[:2];blocks[:2]=[{'id':'3.box','type':'parallel_boxes','text':'','paragraphs':[p['text'] for p in ps],'layout':{'columns':2},'asset':crop(1,q['visuals'][0]['bbox_normalized'],'Q3-box')}]
 if n in [6,7,8]:
  contents=blocks[1:-1];blocks[1:-1]=[{'id':f'{n}.box','type':'boxed_text','text':'','paragraphs':[p['text'] for p in contents],'layout':{'border':'dotted'},'asset':crop(q['source_pages'][0],q['visuals'][0]['bbox_normalized'],f'Q{n}-box')}]
 for i,t in enumerate(q.get('visuals',[])):
  if n in [3,6,7,8]:continue
  v=dict(t,id=f'{n}.visual{i}',type='figure',text='',alt=t.get('description',''),asset=crop(t['source_page'],t['bbox_normalized'],f'Q{n}-visual{i}'));blocks.append(v)
 for group in ['statements','options']:
  arr=q.get(group,[])
  if n==10:continue
  if arr:blocks.append({'id':f'{n}.{group}','type':group,'text':'','entries':arr,'layout':{'columns':2,'rows':2,'order':'row-major','book_display_rule':'AB/CD 或①②/③④；原卷布局另由题块截图保留。'}})
 selected=q.get('statements') or q['options']
 for idx,st in enumerate(selected):claims.append({'id':f'Q{n}:{st["label"]}','parent_id':f'Q{n}','label':st['label'],'text':st['text'],'modules':CLAIM_MODULES[n][idx],'drill_admission':'not_decided_for_any_book','truth_status':'not_inferred_from_answer_key','review_note':'这是知识归属索引，正式题肢单练仍须按册逐条审核；未入选不自动表示错误。'})
 parents.append(dict(number=n,points=3,source_pages=q['source_pages'],blocks=blocks,question_bbox=q.get('question_bbox',[]),uncertainties=q.get('uncertainties',[])))
 items.append({'id':f'Q{n}','parent':n,'kind':'choice','points':3,'depends_on':[b['id'] for b in blocks],'modules':MC_MODULES[n],'tags':MC_TAGS[n],'answer':rr['answer_key'][str(n)],'rubric_ids':[],'source_pages':q['source_pages']})
for p in sub:
 for b in p['blocks']:
  if b.get('bbox_normalized'):b['asset']=crop(b['source_page'],b['bbox_normalized'],b['id'])
 parents.append({k:v for k,v in p.items() if k!='items'})
 for it in p['items']:items.append(dict(it,parent=p['number'],kind='subjective',source_pages=p['source_pages']))
# Normalize independent rubric IDs without changing source wording.
rubrics=[]
for unit in rr['units']:
 if unit['id']=='R17':
  rubrics.append(dict(unit,id='R17-a',task_key='a',blocks=[unit['blocks'][i] for i in [0,1,3]]))
  rubrics.append(dict(unit,id='R17-b',task_key='b',blocks=[unit['blocks'][2]]+unit['blocks'][4:]))
 else:rubrics.append(unit)
for it in items:
 if it['id'] in ['Q17-a','Q17-b']:it['rubric_ids']=['R'+it['id'][1:]]
mapping={}
for r in rubrics:
 n=r['question'];sq=r.get('subquestion');canonical=r['id'] if n==17 else 'R'+str(n)+(('-'+str(sq)) if n==18 and sq is not None else '')
 mapping.setdefault(canonical,[]).append(r)
rnormalized=[]
for k,units in mapping.items():
 r={'id':k,'question':units[0]['question'],'carrier_pages':sorted(set(p for u in units for p in u['source_pages'])),'source_pages':sorted(set(b['source_page'] for u in units for b in u['blocks'] if b.get('type')!='student_example')),'blocks':[b for u in units for b in u['blocks']],'uncertainties':[t for u in units for t in u.get('uncertainties',[])]}
 for i,b in enumerate(r['blocks']):
  b.setdefault('id',k+f'.b{i}');b.setdefault('text','')
  if b.get('type')=='student_example':b['asset']='assets/pages/细则/'+Path(b['asset']).name
  if b.get('embedded_asset'):b['asset']=b['embedded_asset']
  elif b.get('bbox_normalized') and b.get('source_page'):b['asset']=crop(b['source_page'],b['bbox_normalized'],k+f'-b{i}','细则')
 rnormalized.append(r)
R={r['id']:r for r in rnormalized};P={p['number']:p for p in parents}
# Raw page reference is always retained. Student scripts are image assets, separate from scoring rules.
example_map={'R16':[(2,1)],'R17':[],'R18-1':[],'R18-2':[(4,1)],'R18-3':[(5,1)],'R19':[(6,1)],'R20':[(7,1)],'R21':[(8,2)]}
for r in rnormalized:r['student_examples']=[{'type':'student_example_image','source_page':p,'asset':f'assets/pages/细则/p{p:02}_embedded{i:02}.png','evidence_status':'学生样卷及阅卷批注；不可把学生原话直接认作通用评分规则'} for p,i in example_map.get(r['id'],[])]
# Include actual source crops for inspection; these are optional, not required for text-only retrieval.
for p in parents:
 for i,x in enumerate(p['question_bbox']):x['asset']=crop(x['page'],x['bbox_normalized'],f'Q{p["number"]}-source{i}')
for c in claims:
 if c['parent_id']=='Q10':
  row=next(t for t in mc if t['number']==10)['tables'][0]['rows']['ABCD'.index(c['label'])]
  c['source_cells']={'行为':row[1],'解读':row[2]};c['text_is_search_join']=True
raw={'schema_version':'0.1-pilot','exam_id':'BJ-2026-HD-YIMO-POL','display_name':'2026海淀一模','source_title':'海淀区2025—2026学年第二学期期中练习 高三思想政治','exam_date':'2026-04','cohort':2026,'sources':load('data/sources.json')['sources'],'parents':parents,'items':items,'rubrics':rnormalized,'claims':claims,'global_rules':rr.get('general_rules',[]),'coverage_note':'本卷试点，21大题、24取用单元；不是全库完成。'}
save('data/bank.json',raw);save('data/claims.json',claims)
index=[];full=[]
for it in items:
 par=P[it['parent']];blocks={b['id']:b for b in par['blocks']};assert all(k in blocks for k in it['depends_on']);assert all(k in R for k in it['rubric_ids'])
 idx={k:it[k] for k in ['id','kind','points','modules','tags']};idx['source_pages']=it['source_pages'];index.append(idx)
 out=[f'# 2026海淀一模 {it["id"]}',f'原卷第{it["parent"]}题；当前取用单元{it["points"]}分。','知识归属索引：'+'、'.join(it['modules'])+'。跨册标签不等于已收入任何宝典。']
 if it.get('cross_module_note'):out.append(it['cross_module_note'])
 if it.get('task_note'):out.append(it['task_note'])
 out+=['## 原题']
 for k in it['depends_on']:
  b=blocks[k]
  if b['type'] in ['statements','options']:out+=['\n'.join(x['label']+'．'+x['text'] for x in b['entries'])]
  else:out.append(mdblock(b))
 if it['kind']=='choice':out+=['## 答案键',it['answer']+'（细则原件第1页）；不以未入选自动判定题肢错误。']
 else:
  for rid in it['rubric_ids']:
   r=R[rid];out+=['## 正式评分材料 '+rid+'（第'+','.join(map(str,r['source_pages']))+'页）']
   last_role=None
   role_names={'reference_answer':'载体中的参考答案原文','scoring_rule':'正式评分条件原文','official_example':'评分载体提供的示例'}
   for b in r['blocks']:
    if b.get('type')=='student_example':continue
    if b.get('role')!=last_role:
     out.append('### '+role_names.get(b.get('role'),'载体原文'));last_role=b.get('role')
    out.append(mdblock(b))
   out += ['[细则原页'+str(p)+']('+str(ROOT/f'assets/pages/细则/p{p:02}.png')+')' for p in r['source_pages']]
   if r['student_examples']:out+=['学生样卷及批注单独保存：'+'；'.join('[第'+str(z['source_page'])+'页样卷]('+str(ROOT/z['asset'])+')' for z in r['student_examples'])]
 out+=['## 来源与版面依赖','原题页：'+','.join(map(str,it['source_pages']))+'；材料块：'+', '.join(it['depends_on'])+'。']
 for b in [blocks[k] for k in it['depends_on']]:
  if b.get('layout'):out.append(b['id']+' 版面：'+json.dumps(b['layout'],ensure_ascii=False))
 for nt in par.get('notes',[]):out.append('原件备注：'+nt)
 for z in par['question_bbox']:out.append('[整道题原卷对照图]('+str(ROOT/z['asset'])+')')
 for source in raw['sources']:out.append(source['role']+' SHA256：'+source['sha256'])
 out.append('仅此题包已含列明的作答材料与评分条件；图像须在初次使用或排版复核时打开。')
 packet='\n\n'.join(x for x in out if x)+'\n';f=ROOT/'packets'/f'{it["id"]}.md';f.parent.mkdir(exist_ok=True);f.write_text(packet)
# Full comparable text is unique parents + unique rubric units, not duplicated retrieval packets.
for p in parents:
 full.append(f'第{p["number"]}题')
 for b in p['blocks']:
  full.append(textof(b));full.extend(x['label']+x['text'] for x in b.get('entries',[]))
for r in rnormalized:
 full.append(r['id']);full.extend(textof(b) for b in r['blocks'])
(ROOT/'data/full_text_for_comparison.txt').write_text('\n\n'.join(full))
save('data/index.json',index)
files=[ROOT/'data/bank.json',ROOT/'data/index.json',ROOT/'data/claims.json']+list((ROOT/'packets').glob('*.md'))+list((ROOT/'assets').rglob('*.png'))
save('data/integrity.json',{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(files)})
print(json.dumps({'parents':len(parents),'items':len(items),'rubrics':len(rnormalized),'claims':len(claims),'score':sum(p['points'] for p in parents),'image_assets':len(list((ROOT/'assets').rglob('*.png')))},ensure_ascii=False))
