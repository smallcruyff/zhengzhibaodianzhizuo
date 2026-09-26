import sys
sys.dont_write_bytecode = True
R='/home/user/zhengzhibaodianzhizuo'
C=R+'/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
sys.path.insert(0, C)
import intake_run as ir
import block_index as bidx
prof = ir.load_profile(C+'/profiles_cloud/bixiu3.json')
docx = R+'/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
idx = bidx.build_index(docx, prof)
pats = sys.argv[1:]
for b in idx['blocks']:
    ks = [b.get('key') or ''] + list(b.get('keys_all', []))
    if any(any(p in k for k in ks) for p in pats) or any(p in (b.get('src') or '') for p in pats):
        print(b['id'], b.get('kind'), 'key=',b.get('key'), 'subq=',b.get('subq'), 'keys_all=',b.get('keys_all'), 'src=',b.get('src')[:60])
for it in idx['drill_items']:
    ks = [it.get('key') or ''] + list(it.get('keys_all', []))
    if any(any(p in k for k in ks) for p in pats):
        print('DRILL', it['id'], it.get('key'), it.get('subq'), it.get('src','')[:50])
