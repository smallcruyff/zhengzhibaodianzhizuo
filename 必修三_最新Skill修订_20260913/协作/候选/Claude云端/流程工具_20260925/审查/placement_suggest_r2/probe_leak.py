#!/usr/bin/env python3
"""审查 r2：同题换键泄漏。对十题与全书留一的每个前1命中，取真实考法组里（剔除同题键后）与查询最像的题块，
算查询题面（material+ask）与该题块材料/设问的字符 3-gram 包含度（查询 3-gram 落在该块里的比例）；
>=0.6 视作“同一道题换了题键”嫌疑，列出。只读。"""
import sys, re
sys.dont_write_bytecode = True
from pathlib import Path
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
from profile_lib import load_profile
from block_index import sig
BANK = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
prof = load_profile(str(C / 'profiles_cloud' / 'bixiu3.json'))
book = ps.load_book('/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx', prof)
blocks = book['blocks']
mi = ps.build_method_intro(book['doc'], book['heads'], ps.method_desc_style_set(prof))
fields = ps.block_fields_all(blocks, mi)
idx = ps.build_indices(fields, [2, 3])
def grams(t):
    s = sig(t); return {s[i:i+3] for i in range(len(s)-2)}
cache = {}
def q_of(k):
    if k not in cache:
        p = ps.find_md_path(BANK, k)
        try:
            cache[k] = ps.parse_question_md(p.read_text(encoding='utf-8', errors='replace'), k) if p.is_file() else None
        except ps.InputError:
            cache[k] = None
    return cache[k]
TEN = ['BJ-2025-FS-YIMO-Q17', 'BJ-2025-CY-ERMO-Q19', 'BJ-2022-BJ-GAOKAO-Q20', 'BJ-2024-DC-ERMO-Q21', 'BJ-2026-DC-ERMO-Q11',
       'BJ-2024-HD-YIMO-Q8', 'BJ-2026-HD-QIZHONG-Q7', 'BJ-2024-CY-YIMO-Q16', 'BJ-2023-HD-YIMO-Q16', 'BJ-2025-FT-QIMO-Q18']
sus = []
n_hit1 = 0
for i, b in enumerate(blocks):
    k = b.get('key')
    q = q_of(k) if k else None
    if not q:
        continue
    qq = dict(q); qq['base_key'] = k
    ranked, excl, _ = ps.rank_for_query(qq, book, idx, ps.DEFAULT_PARAMS)
    if not ranked or ranked[0]['group_key'] != ps.group_key_of(b):
        continue
    n_hit1 += 1
    qg = grams(q['material'] + q['ask'])
    if len(qg) < 20:
        continue
    best = max(ranked[0]['block_idxs'], key=lambda j: len(qg & grams(fields[j]['material'] + fields[j]['ask'])))
    cont = len(qg & grams(fields[best]['material'] + fields[best]['ask'])) / len(qg)
    if cont >= 0.6:
        sus.append((b['id'], k, blocks[best]['id'], blocks[best]['key'], blocks[best]['title'][:34], round(cont, 2), k in TEN))
print('留一前1命中（题块级）', n_hit1)
print('前1命中里“最像块与查询题面3-gram包含度>=0.6”（疑似同题换键）:', len(sus))
for s in sus:
    print(' ', s)
