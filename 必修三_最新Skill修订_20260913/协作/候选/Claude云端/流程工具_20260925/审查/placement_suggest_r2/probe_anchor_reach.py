#!/usr/bin/env python3
"""审查 r2：真实题键查询（生产口径：剔除同题键）的前 3 候选里，落到“method_end 锚点声称唯一、但 block_insert
实际解析到本节点选择例题之后”的 3 个考法组的次数。只读。"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
from profile_lib import load_profile
BANK = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
prof = load_profile(str(C / 'profiles_cloud' / 'bixiu3.json'))
book = ps.load_book('/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx', prof)
blocks = book['blocks']
mi = ps.build_method_intro(book['doc'], book['heads'], ps.method_desc_style_set(prof))
idx = ps.build_indices(ps.block_fields_all(blocks, mi), [2, 3])
BAD = {('P1', '03　党员：先锋模范作用', '考法2　补出型：材料没点党员作用，自己补（2题）'),
       ('P1', '06　人大代表', '考法3　补出型：只写代表做事，身份要补（3题）'),
       ('P1', '03　司法：公正司法', '考法6　一环型：司法只是法治链条一环（6题）')}
hits = []
for k in sorted({b['key'] for b in blocks if b.get('key')}):
    p = ps.find_md_path(BANK, k)
    if not p.is_file():
        continue
    try:
        q = ps.parse_question_md(p.read_text(encoding='utf-8', errors='replace'), k)
    except ps.InputError:
        continue
    q['base_key'] = k
    if q['kind'] == 'choice':
        continue
    ranked, _, _ = ps.rank_for_query(q, book, idx, ps.DEFAULT_PARAMS)
    for i, g in enumerate(ranked[:3], 1):
        if g['group_key'] in BAD:
            c = ps.candidate_detail(book, g, {}, idx, 50)
            hits.append((k, i, c['label'][:40], c['insert_after']['block_id'], c['insert_after']['anchor_unique']))
print('主观题查询：前3候选落到这 3 个组（method_end 声称唯一、实际落到选择例题后）的次数:', len(hits))
for h in hits[:15]:
    print(' ', h)
