"""对抗探针：归属表里标 COLLECTED（=书稿已收）的全部题，intake_run 第8步的 block_index 查法能找回多少。
找不回的 COLLECTED 在 intake_run 里会被报成 第8步 TODO（'尚未在当前稿中'）→ 下一条命令 block_insert。"""
import sys, json
sys.dont_write_bytecode = True
R='/home/user/zhengzhibaodianzhizuo'
C=R+'/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
sys.path.insert(0, C)
import intake_run as ir
import block_index as bidx
books = {'bixiu3':'bixiu3.json','philosophy':'philosophy.draft.json','culture':'culture.draft.json',
         'xuanbi1':'xuanbi1.draft.json','xuanbi2':'xuanbi2.draft.json','mind':'mind.draft.json','reasoning':'reasoning.draft.json'}
attr, _ = ir.load_attribution(ir.DEFAULT_ATTRIBUTION_CSV)
# 全部行（按 unit_id 去重）
allrows = {}
for rows in attr.values():
    for r in rows:
        allrows[r['unit_id']] = r
cache = ir.BookIndexCache()
out = {}
for book, pf in books.items():
    prof = ir.load_book_profile(book, C+'/profiles_cloud/'+pf)
    docx, err = ir.current_docx_for_book(prof)
    code = ir.ATTR_CODE[book]
    coll = [r for r in allrows.values() if (r.get('归属_'+code) or '').strip()=='COLLECTED']
    idx, e = cache.get(book, prof, docx)
    nblocks = len(idx['blocks']) if idx else None
    found = 0; miss_drill_only = 0; miss = []
    for r in coll:
        hit, _ = cache.has_key(book, prof, docx, r['unit_id'])
        if hit:
            found += 1
            sb, sd = bidx.select(idx, keys=[ir.normalize_qid(r['unit_id'])], with_drill=True)
            if not sb and sd: miss_drill_only += 1
        else:
            miss.append(r['unit_id'])
    out[book] = {'blocks': nblocks, 'collected': len(coll), 'found': found,
                 'recall': round(found/len(coll),3) if coll else None,
                 'found_only_via_drill_item': miss_drill_only, 'miss_sample': miss[:8]}
    print(book, json.dumps(out[book], ensure_ascii=False))
json.dump(out, open(sys.argv[1],'w'), ensure_ascii=False, indent=1)
