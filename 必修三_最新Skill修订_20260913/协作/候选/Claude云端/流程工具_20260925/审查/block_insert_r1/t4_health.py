import sys; sys.dont_write_bytecode=True
import json, zipfile
C='/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
sys.path.insert(0,C)
import block_insert as bi
P='/home/user/zhengzhibaodianzhizuo/其他书工作头/哲学/哲学宝典_修订稿_R10_漏节点与附录补全及触发词修正版_20260908.docx'
prof=bi.load_profile(C+'/profiles_cloud/philosophy.draft.json')
z=zipfile.ZipFile(P); print('philosophy media members',len([n for n in z.namelist() if n.startswith('word/media/')]))
h=bi.health_diff(P,'gold/philosophy_out.docx',prof)
print(json.dumps({k:v for k,v in h.items() if k!='new_FAIL'},ensure_ascii=False), [ (f['check'],f['rule'],f.get('excerpt','')[:40]) for f in h['new_FAIL']][:10])
u=json.load(open('gold/other_book_insert.json')); print(u['inserts'][0]['title'], u['inserts'][0]['anchor'], u['inserts'][0]['template_block'])
