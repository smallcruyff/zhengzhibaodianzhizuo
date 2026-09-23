from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1];src=R/'review/rubric_transcript.json';d=json.loads(src.read_text());assert d['complete']
assets={'R16':[(1,1)],'R17':[(2,2)],'R18-1':[(3,1)],'R18-2':[(3,2)],'R18-3':[(4,2)],'R19':[(5,2)],'R20':[(6,2)],'R21':[(7,2),(7,3),(8,1)]}
for u in d['units']:
 u['source_notes']=u.pop('uncertainties',[]);u['uncertainties']=[]
 ti=0
 for b in u['blocks']:
  if b['type']=='table':
   p,i=assets[u['id']][ti];b['embedded_asset']=f'assets/pages/细则/p{p:02}_embedded{i:02}.png';ti+=1
  if u['id']=='R21' and b.get('caption') in ['科学制定规划','有效执行计划']:
   b['role']='official_example'
   assert b['rows'][0][0]==b['caption'];b['rows']=b['rows'][1:]
   b['merged_cells']=[dict(m,row=m['row']-1) for m in b['merged_cells'] if m['row']>0]
 if u['id']=='R18-3':assert not any('幸福感' in b.get('text','') for b in u['blocks'])
d['root_review']={'parent_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'source_pages_read':[1,2,3,4,5,6,7,8],'changes':['R18-2跨页限制仅归本小问','表格使用原尺寸嵌入图作为复核图','Q21示例与总评分条件分别标示，表题与行数据分离','Q17原件措辞差异照录；Q21“锐”按可见原字保留，已消除转录待核'],'status':'verified_against_all_pages'}
(R/'data/rubric_reviewed.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
