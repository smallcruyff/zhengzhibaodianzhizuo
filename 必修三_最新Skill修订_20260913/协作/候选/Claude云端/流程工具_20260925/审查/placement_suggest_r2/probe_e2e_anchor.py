#!/usr/bin/env python3
"""审查 r2 探针：把 placement_suggest 给出的 anchor 原样/按 block_insert 格式包装后，喂给 block_insert
真实的 resolve_insert_anchor（题块由 ap.zones_of=bh.walk 现算），核：
 (1) placement_suggest 输出的 anchor 字典形状能否直接被 block_insert 接受；
 (2) 包装成 block_insert 格式后，能否解析成功；与 anchor_unique 声明是否一致；
 (3) 解析出的题块是否就是 placement_suggest 声称的 insert_after 题块（同标题、同文档序号）。
只读；不写任何文件。"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from collections import Counter
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
import block_insert as bi
import docx_lib as dl
import apply_patch as ap
from profile_lib import load_profile

R = Path('/home/user/zhengzhibaodianzhizuo')
BOOK = R / '必修三_最新Skill修订_20260913' / '必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
PROF = C / 'profiles_cloud' / 'bixiu3.json'
prof = load_profile(str(PROF))
book = ps.load_book(str(BOOK), prof)
blocks = book['blocks']
d = dl.open_docx(str(BOOK))
_, _, bh_blocks, _ = ap.zones_of(d, prof)
print('block_index blocks', len(blocks), 'bh.walk blocks', len(bh_blocks))

# 标题序列是否一致（按文档序）
bi_titles = [b['title'] for b in blocks]
bh_titles = [b['title'] for b in bh_blocks]
print('titles identical in order:', bi_titles == bh_titles)

groups = {}
for b in blocks:
    groups.setdefault(ps.group_key_of(b), []).append(b)
raw_shape_ok = 0
stats = Counter()
bad = []
for gk, bs in groups.items():
    last_b = max(bs, key=lambda b: b['p_range'][0])
    anchor, uniq = ps.anchor_for_group(blocks, gk, last_b)
    # (1) 原样喂
    try:
        bi.resolve_insert_anchor(bh_blocks, dict(anchor))
        raw_shape_ok += 1
    except bi.Abort:
        pass
    # (2) 包装
    a = dict(anchor)
    kind = a.pop('kind')
    wrapped = {kind: {k: v for k, v in a.items() if v is not None}}
    try:
        k, rb, pos = bi.resolve_insert_anchor(bh_blocks, wrapped)
        ok = True
    except bi.Abort as e:
        ok, rb, err = False, None, str(e)[:160]
    ordinal = blocks.index(last_b)
    same = ok and rb['title'] == last_b['title'] and bh_blocks.index(rb) == ordinal
    stats[(kind, uniq, ok, same)] += 1
    if uniq != ok or (ok and not same):
        bad.append({'group': gk, 'kind': kind, 'claimed_unique': uniq, 'resolved': ok,
                    'resolved_is_last_b': same, 'last_b': (last_b['id'], last_b['title'], last_b['kind']),
                    'resolved_block': (rb['title'], bh_blocks.index(rb), rb.get('node'), rb.get('method')) if rb else None,
                    'err': None if ok else err, 'anchor': wrapped})
print('raw anchor dict accepted by block_insert as-is:', raw_shape_ok, '/', len(groups))
print('groups', len(groups))
for k, v in sorted(stats.items(), key=str):
    print('  (kind, claimed_unique, resolved, resolved_is_last_b)=', k, v)
print('mismatches:', len(bad))
for x in bad[:40]:
    print(' ', x)
