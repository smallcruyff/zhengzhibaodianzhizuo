import sys; sys.dont_write_bytecode=True
import json, subprocess, shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent; OUT=HERE/'adv_out'
C=Path('/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925')
R=Path('/home/user/zhengzhibaodianzhizuo')
SHA='c007d7198422050cdf47d1ec679a097d0b350f1bfb9c70d41672103780f76eb6'
PROF=C/'profiles_cloud/bixiu3.json'
def unit(**kw):
    ins={'id':'M1','anchor':{'after_block':{'title_contains':'例题 5　2026门头沟一模第17题'}},
         'template_block':{'title_contains':'例题 5　2026门头沟一模第17题'},'title':'例题 97　2026海淀一模第17题',
         'source_zone':'restore','reason':'对抗审查','content':[{'role':'source','text':'【题目】17．（8分）材料。'}]}
    ins.update(kw)
    return {'schema':'baodian_insert_v1','book':'bixiu3','parent_docx_sha256':SHA,'approved_by':'claude:review-r1','approval_ref':'对抗审查','inserts':[ins]}
def run(name, u, mode='check', extra=(), profile=PROF, docx=None):
    up=OUT/f'{name}_unit.json'; up.write_text(json.dumps(u,ensure_ascii=False),encoding='utf-8')
    rep=OUT/f'{name}_rep.json'
    if rep.exists(): rep.unlink()
    args=[sys.executable,str(C/'block_insert.py'),mode,'--docx',str(docx or OUT/'parent.docx'),'--insert',str(up),'--profile',str(profile),'--report',str(rep)]+list(extra)
    r=subprocess.run(args,capture_output=True,text=True)
    rj=json.loads(rep.read_text()) if rep.exists() else {}
    return r.returncode, r.stdout.strip()[-300:], r.stderr.strip()[-400:], rj
# 1 method_end ambiguous across 20 methods
rc,so,se,rj=run('m_ambig', unit(anchor={'method_end':{'method_contains':'考法1'}}))
print('method_end 考法1 (20 distinct methods) ->',rc,se, [ (p['anchor_block_title']) for p in rj.get('plan',[])])
# 1b method_contains matching 考法1 vs 考法10? check number of distinct (node,method)
# 2 title with forbidden/engineering words
for w in ['待核','占位','测试','TODO','候选']:
    rc,so,se,rj=run('title_'+w, unit(title='例题 97　2026海淀一模第17题'+w))
    print('title word',w,'->',rc,se[:150])
# 3 teaching text with same word (control)
rc,so,se,rj=run('teach_dh', unit(content=[{'role':'source','text':'【题目】材料。'},{'role':'teaching','text':'从材料选知识：待核'}]))
print('teaching 待核 ->',rc,se[:150])
# 4 table rows with approved_edit containing forbidden word
rc,so,se,rj=run('rows_dh', unit(source_zone='approved_edit',content=[{'role':'source','text':'【题目】材料。'},{'role':'table','rows':[['待核','占位']]}]))
print('rows approved_edit 待核 ->',rc,se[:150])
# 5 frozen profile in check mode (should be read-only runnable)
rc,so,se,rj=run('frozen_check', unit(), profile=C/'profiles_cloud/bixiu2_frozen_test.json')
print('frozen check ->',rc,so[:100],se[:200])
# 6 output into 00_必修三最新审查稿 (审阅入口) and 00_共同资料/原材料
for nm,target in [('review_entry',R/'00_必修三最新审查稿'/'x_block_insert.docx'),('raw',R/'00_共同资料'/'原材料'/'x_block_insert.docx'),('cloud',R/'云端'/'x.docx'),('C_root',C/'x.docx'),('C_huizhi',C/'回执'/'x.docx')]:
    if not target.parent.exists(): print(nm,'dir missing'); continue
    rc,so,se,rj=run('out_'+nm, unit(), mode='apply', extra=['--out',str(target)])
    print('out',nm,'->',rc,se[:160],'exists after:',target.exists())
