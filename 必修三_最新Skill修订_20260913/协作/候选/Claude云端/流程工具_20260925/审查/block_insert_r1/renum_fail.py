import sys; sys.dont_write_bytecode=True
import json, subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent; OUT=HERE/'adv_out'
C=Path('/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925')
SHA='c007d7198422050cdf47d1ec679a097d0b350f1bfb9c70d41672103780f76eb6'
u={'schema':'baodian_insert_v1','book':'bixiu3','parent_docx_sha256':SHA,'approved_by':'claude:review-r1','approval_ref':'x',
 'inserts':[{'id':'R1','anchor':{'after_block':{'title_contains':'例题 5　2026门头沟一模第17题'}},'template_block':{'title_contains':'例题 5　2026门头沟一模第17题'},
  'title':'例题 90　2026海淀一模第17题','source_zone':'restore','reason':'x','content':[{'role':'source','text':'【题目】17．（8分）材料。'}]}]}
up=OUT/'renum_unit.json'; up.write_text(json.dumps(u,ensure_ascii=False),encoding='utf-8')
out=OUT/'renum_out.docx'; blocker=OUT/'renum_out_renumbered.docx'
for p in (out,): 
    if p.exists(): p.unlink()
blocker.write_bytes(b'stale')   # 预先占位：让 layout_prepare 的守卫拒绝写出
r=subprocess.run([sys.executable,str(C/'block_insert.py'),'apply','--docx',str(OUT/'parent.docx'),'--insert',str(up),'--out',str(out),'--profile',str(C/'profiles_cloud/bixiu3.json'),'--renumber'],capture_output=True,text=True)
print('rc',r.returncode,'stdout',r.stdout[-200:],'stderr',r.stderr[-400:])
