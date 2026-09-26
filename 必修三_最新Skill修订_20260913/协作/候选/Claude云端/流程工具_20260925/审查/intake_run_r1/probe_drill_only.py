"""对抗探针：第8步 block_index.select 默认 with_drill=True——只在题肢单练附录（drill_items）出现、没有例题题块的题，
也会被 intake_run 判成“已在书里”（第8步 DONE）。列出 bixiu3 里 IN（=该收未收）却只凭单练条目命中的题。"""
import sys, json
sys.dont_write_bytecode = True
R='/home/user/zhengzhibaodianzhizuo'
C=R+'/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
sys.path.insert(0, C)
import intake_run as ir
import block_index as bidx
attr, _ = ir.load_attribution(ir.DEFAULT_ATTRIBUTION_CSV)
allrows = {}
for rows in attr.values():
    for r in rows: allrows[r['unit_id']] = r
books = {'bixiu3':'bixiu3.json','culture':'culture.draft.json'}
for book, pf in books.items():
    prof = ir.load_book_profile(book, C+'/profiles_cloud/'+pf)
    docx, _ = ir.current_docx_for_book(prof)
    idx = bidx.build_index(str(docx), prof)
    code = ir.ATTR_CODE[book]
    res = {'IN': [], 'COLLECTED': []}
    for r in allrows.values():
        v = (r.get('归属_'+code) or '').strip()
        if v not in res: continue
        sb, sd = bidx.select(idx, keys=[ir.normalize_qid(r['unit_id'])])
        if not sb and sd:
            res[v].append((r['unit_id'], sd[0]['id'], sd[0].get('src')))
    print(book, 'IN 仅凭单练条目命中:', len(res['IN']), res['IN'][:6])
    print(book, 'COLLECTED 仅凭单练条目命中:', len(res['COLLECTED']), res['COLLECTED'][:4])
