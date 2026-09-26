import sys
sys.dont_write_bytecode=True
import json, hashlib
from common import *
sys.path.insert(0, str(R / '.claude/skills/beijing-gaokao-politics/scripts'))
import docx_lib as dl
from profile_lib import load_profile
victim1 = WORK/'approved_patch_victim.json'
victim1.write_text(json.dumps({'schema':'baodian_patch_v1','approved_by':'user','approval_ref':'台账R99','ops':[{'op':'replace_text','old':'a','new':'b','source_zone':'restore','reason':'x'}]},ensure_ascii=False),encoding='utf-8')
victim2 = WORK/'approved_insert_victim.json'
victim2.write_text(json.dumps(unit([{'role':'source','text':'【题目】x'}], sz='restore'),ensure_ascii=False),encoding='utf-8')
before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (victim1, victim2)}
parent = fresh('rep_parent.docx'); up = write_unit(unit([{'role':'source','text':'【题目】审查探针一句。'}]), 'rep_insert.json')
out={}
for v in (victim1, victim2):
    rc, so, se = run(['check','--docx',parent,'--insert',up,'--profile',PROF,'--report',v])
    obj=json.loads(v.read_text(encoding='utf-8'))
    out[v.name]={'rc':rc,'now_tool':obj.get('tool'),'now_schema':obj.get('schema'),'overwritten': hashlib.sha256(v.read_bytes()).hexdigest()!=before[v.name]}
print(json.dumps(out,ensure_ascii=False,indent=1))
prof = dict(load_profile(str(PROF))); prof['frozen']=False
base = C/'构建'/'baseline_20260925.json'
try:
    r = dl.guard_write(base, prof, inputs=[], kind='.json', overwrite=True)
    print('guard_write(构建/baseline_20260925.json, overwrite=True) -> ALLOWED（只调守卫、未写）', r)
except dl.GuardError as e:
    print('REFUSED', e)
