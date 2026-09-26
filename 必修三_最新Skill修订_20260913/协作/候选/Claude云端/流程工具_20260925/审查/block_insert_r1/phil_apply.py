import sys; sys.dont_write_bytecode=True
import json, subprocess, shutil, hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent; OUT=HERE/'adv_out'
C=Path('/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925')
P=Path('/home/user/zhengzhibaodianzhizuo/其他书工作头/哲学/哲学宝典_修订稿_R10_漏节点与附录补全及触发词修正版_20260908.docx')
cp=OUT/'phil_parent.docx'; shutil.copyfile(P,cp)
sha=hashlib.sha256(cp.read_bytes()).hexdigest()
XC='/home/user/zhengzhibaodianzhizuo/00_共同资料/原材料/2023模拟题/2023各区模拟题(1)/各区二模/√西城/西城-高三政治二模试卷-定(2).docx'
u={'schema':'baodian_insert_v1','book':'philosophy','parent_docx_sha256':sha,'approved_by':'claude:review-r1','approval_ref':'对抗审查',
 'inserts':[{'id':'P1','anchor':{'after_block':{'title_contains':'例题 1　2026年东城二模第16题'}},'template_block':{'title_contains':'例题 1　2026年东城二模第16题'},
  'title':'例题 2　2023年西城二模第16题','source_zone':'restore','reason':'对抗审查：其他书带图写入',
  'content':[{'role':'source','text':'【材料原文】'},{'role':'source','text':'16．（10分）北京公交集团主导的“公交便民驿栈”来了！'},
   {'role':'image','from':{'docx':XC,'rid':'rId14'}},
   {'role':'source','style':'题目设问','text':'【设问】 结合材料，分析北京市推广便民服务栈点的经济原因。'},
   {'role':'teaching','like':'为什么能想到','text':'【为什么能想到】 材料写利用场站边角空间，提示资源配置。'},
   {'role':'teaching','like':'答案落点','text':'【答案落点】 提高资源配置效率。'},
   {'role':'rubric','like':'细则说明','text':'【细则说明】 全题10分。'}]}]}
up=OUT/'phil_unit.json'; up.write_text(json.dumps(u,ensure_ascii=False),encoding='utf-8')
out=OUT/'phil_out.docx'; rep=OUT/'phil_rep.json'
for p in (out,rep):
    if p.exists(): p.unlink()
r=subprocess.run([sys.executable,str(C/'block_insert.py'),'apply','--docx',str(cp),'--insert',str(up),'--out',str(out),'--profile',str(C/'profiles_cloud/philosophy.draft.json'),'--report',str(rep),'--health'],capture_output=True,text=True)
print('rc',r.returncode,r.stdout[-300:],r.stderr[-500:])
if rep.exists():
    rj=json.loads(rep.read_text()); print(json.dumps({'fallbacks':rj.get('plan',[{}])[0].get('fallbacks'),'bic':rj.get('verify',{}).get('block_index_check'),'health':{k:v for k,v in rj.get('health',{}).items() if k!='new_FAIL'},'newfail':[(f['check'],f['rule'],f.get('excerpt','')[:30]) for f in rj.get('health',{}).get('new_FAIL',[])]},ensure_ascii=False,indent=1))
