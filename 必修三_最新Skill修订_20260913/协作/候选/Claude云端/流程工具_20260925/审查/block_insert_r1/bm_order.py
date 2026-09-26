import sys; sys.dont_write_bytecode=True
import json, subprocess, zipfile, hashlib, collections
from pathlib import Path
from lxml import etree
HERE=Path(__file__).resolve().parent; OUT=HERE/'adv_out'
C=Path('/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925')
sys.path.insert(0,str(C))
import block_insert as bi
W=bi.W
# synthetic parent: add a bookmark to 例题 5 title
src=OUT/'parent.docx'; bmp=OUT/'parent_bm.docx'
d=bi.dl.open_docx(src)
tp=[p for p in d.paras if bi.dl.para_text(p)=='例题 5　2026门头沟一模第17题'][0]
ppr=tp.find(W+'pPr'); pos=1 if ppr is not None else 0
tp.insert(pos, etree.Element(W+'bookmarkStart',{W+'id':'9001',W+'name':'_Ref_example5'}))
tp.append(etree.Element(W+'bookmarkEnd',{W+'id':'9001'}))
if bmp.exists(): bmp.unlink()
bi.dl.write_docx(d,bmp)
sha=hashlib.sha256(bmp.read_bytes()).hexdigest()
def ins(i,title):
    return {'id':i,'anchor':{'after_block':{'title_contains':'例题 5　2026门头沟一模第17题'}},'template_block':{'title_contains':'例题 5　2026门头沟一模第17题'},
      'title':title,'source_zone':'restore','reason':'x','content':[{'role':'source','text':'【题目】17．（8分）材料。'}]}
u={'schema':'baodian_insert_v1','book':'bixiu3','parent_docx_sha256':sha,'approved_by':'claude:review-r1','approval_ref':'x',
   'inserts':[ins('A1','例题 90　2026甲区一模第17题'),ins('A2','例题 91　2026乙区一模第17题')]}
up=OUT/'bm_unit.json'; up.write_text(json.dumps(u,ensure_ascii=False),encoding='utf-8')
out=OUT/'bm_out.docx'; rep=OUT/'bm_rep.json'
for p in (out,rep):
    if p.exists(): p.unlink()
r=subprocess.run([sys.executable,str(C/'block_insert.py'),'apply','--docx',str(bmp),'--insert',str(up),'--out',str(out),'--profile',str(C/'profiles_cloud/bixiu3.json'),'--report',str(rep)],capture_output=True,text=True)
print('rc',r.returncode,r.stderr[-300:])
if out.exists():
    root=etree.fromstring(zipfile.ZipFile(out).read('word/document.xml'))
    ts=[bi.dl.para_text(p) for p in bi.dl.para_elements(root.find(W+'body'))]
    i5=ts.index('例题 5　2026门头沟一模第17题'); 
    print('order after 例题5 block:', [t for t in ts[i5:i5+40] if t.startswith('例题')][:4])
    bms=[(b.get(W+'id'),b.get(W+'name')) for b in root.iter(W+'bookmarkStart')]
    print('new bookmarks',[b for b in bms if 'baodian' in (b[1] or '')])
    rj=json.loads(rep.read_text()); print('fallback notes',[pl['fallbacks'] for pl in rj['plan']])
