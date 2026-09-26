#!/usr/bin/env python3
"""审查 r2 探针（续）：按 placement_suggest 实际的题型分池（KIND_GROUPS）组组，逐组取 candidate_detail
给出的 insert_after 与 anchor，喂 block_insert.resolve_insert_anchor（ap.zones_of 现算题块），核解析出的
插入位置是否就是 insert_after.block_id 声称的“考法末尾”题块之后。只读。"""
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
assert [b['title'] for b in blocks] == [b['title'] for b in bh_blocks]
params = ps.DEFAULT_PARAMS
method_intro = ps.build_method_intro(book['doc'], book['heads'], ps.method_desc_style_set(prof))
indices = ps.build_indices(ps.block_fields_all(blocks, method_intro), params['ngram_sizes'])
combined = [0.0] * len(blocks)
tot = Counter(); bad = []
for qkind, kset in ps.KIND_GROUPS.items():
    ranked = ps.aggregate_methods(blocks, combined, kset, set(), params)
    for g in ranked:
        c = ps.candidate_detail(book, g, {}, indices, 100)
        ins = c['insert_after']
        a = dict(ins['anchor']); kind = a.pop('kind')
        wrapped = {kind: {k: v for k, v in a.items() if v is not None}}
        try:
            _, rb, pos = bi.resolve_insert_anchor(bh_blocks, wrapped)
            ok = True
        except bi.Abort as e:
            ok, rb, err = False, None, str(e)[:200]
        claimed_idx = [b['id'] for b in blocks].index(ins['block_id'])
        same = ok and bh_blocks.index(rb) == claimed_idx
        tot[(qkind, kind, ins['anchor_unique'], ok, same)] += 1
        if ins['anchor_unique'] != ok or (ok and not same):
            bad.append({'query_kind': qkind, 'label': c['label'], 'anchor': wrapped,
                        'claimed_unique': ins['anchor_unique'], 'resolved_ok': ok,
                        'claimed_insert_after': (ins['block_id'], ins['block_title'], ins['kind']),
                        'block_insert_resolves_to': (blocks[bh_blocks.index(rb)]['id'], rb['title'],
                                                     blocks[bh_blocks.index(rb)]['kind']) if ok else None,
                        'err': None if ok else err})
for k, v in sorted(tot.items(), key=str):
    print('(query_kind, anchor.kind, claimed_unique, resolved, lands_after_claimed_block)=', k, v)
print('problem groups:', len(bad))
for x in bad:
    print(' ', x)
