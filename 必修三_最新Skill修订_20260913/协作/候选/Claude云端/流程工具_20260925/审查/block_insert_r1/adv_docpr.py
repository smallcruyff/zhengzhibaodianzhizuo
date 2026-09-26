import sys; sys.dont_write_bytecode=True
import json, subprocess, zipfile, collections
from pathlib import Path
from lxml import etree
HERE=Path(__file__).resolve().parent; OUT=HERE/'adv_out'
C=Path('/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925')
RAW=Path('/home/user/zhengzhibaodianzhizuo/00_共同资料/原材料')
SHA='c007d7198422050cdf47d1ec679a097d0b350f1bfb9c70d41672103780f76eb6'
WP='{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
src=RAW/'2024模拟题/东城二模/细则/分题细则/阅卷总结/17题/17(1).docx'
unit={'schema':'baodian_insert_v1','book':'bixiu3','parent_docx_sha256':SHA,'approved_by':'claude:review-r1','approval_ref':'对抗审查',
  'inserts':[{'id':'X1','anchor':{'after_block':{'title_contains':'例题 5　2026门头沟一模第17题'}},
    'template_block':{'title_contains':'例题 3　2024朝阳二模第18题'},'title':'例题 96　2024东城二模第17题',
    'source_zone':'restore','reason':'对抗审查：表内图 docPr 冲突',
    'content':[{'role':'source','text':'【题目】17．（8分）阅读材料。'},{'role':'table','from':{'docx':str(src),'table_index':1}}]}]}
up=OUT/'docpr_unit.json'; up.write_text(json.dumps(unit,ensure_ascii=False),encoding='utf-8')
out=OUT/'docpr_out.docx'; rep=OUT/'docpr_rep.json'
for p in (out,rep):
    if p.exists(): p.unlink()
r=subprocess.run([sys.executable,str(C/'block_insert.py'),'apply','--docx',str(OUT/'parent.docx'),'--insert',str(up),'--out',str(out),'--profile',str(C/'profiles_cloud/bixiu3.json'),'--report',str(rep)],capture_output=True,text=True)
print('rc',r.returncode,r.stdout[-200:],r.stderr[-300:])
pz=etree.fromstring(zipfile.ZipFile(OUT/'parent.docx').read('word/document.xml'))
oz=etree.fromstring(zipfile.ZipFile(out).read('word/document.xml'))
pc=collections.Counter(e.get('id') for e in pz.iter(WP+'docPr')); oc=collections.Counter(e.get('id') for e in oz.iter(WP+'docPr'))
print('parent id1/id2 count',pc['1'],pc['2'],' output id1/id2 count',oc['1'],oc['2'])
print('report verify keys',list(json.loads(rep.read_text()).get('verify',{}).keys()))
