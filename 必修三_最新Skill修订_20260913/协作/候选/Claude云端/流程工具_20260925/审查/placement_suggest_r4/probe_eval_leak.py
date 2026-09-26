"""评测口径核对：留一评估剔除了同题键题块的“候选资格”，但 BM25 的 idf/avgdl 与逐字段归一化
（除以本次查询的最高分）仍含被剔除的本题题块。对照两种更严格的口径：
 A. 归一化分母只取未剔除题块（生产中新题本来就不在书里，最高分只会来自别的题块）
 B. 连 idf/avgdl 一起：把同题键题块从索引里删掉重建（真正的留一）
只读，不改工具。"""
import sys, json, time
sys.dont_write_bytecode = True
from pathlib import Path
from collections import Counter
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
sys.path.insert(0, str(C))
import placement_suggest as ps
import run_tests_placement_suggest as rt  # 复用其 md_for_key/strict_eval 口径（导入不跑 main）
from profile_lib import load_profile
prof, book, indices = rt.load_book_and_indices(rt.BOOK3, rt.PROFILE)
blocks = book['blocks']
params = ps.DEFAULT_PARAMS
intro = ps.build_method_intro(book['doc'], book['heads'], ps.method_desc_style_set(prof))
fields_all = ps.block_fields_all(blocks, intro)

def score_norm_excl(query_fields, indices, n, params, exclude):
    combined = [0.0] * n
    for f, idx in indices.items():
        raw = idx.score(query_fields.get(f, ''), params['bm25_k1'], params['bm25_b'])
        vals = [v for i, v in raw.items() if i not in exclude]
        mx = max(vals) if vals else 0.0
        w = params['weights'].get(f, 0.0)
        for i, v in raw.items():
            combined[i] += w * (v / mx if mx > 0 else 0.0)
    return combined

def rank_variant(q, variant):
    exclude = ps.matching_block_idxs(blocks, q['base_key'])
    kind_set = ps.KIND_GROUPS['choice' if q['kind'] == 'choice' else 'subjective']
    qf = {'material': q['material'], 'ask': q['ask'], 'rubric': q['rubric'],
          'method': (q['ask'] + '\n' + q['material']).strip()}
    if variant == 'tool':
        combined, _ = ps.score_blocks(qf, indices, len(blocks), params)
        return ps.aggregate_methods(blocks, combined, kind_set, exclude, params)
    if variant == 'A':
        combined = score_norm_excl(qf, indices, len(blocks), params, exclude)
        return ps.aggregate_methods(blocks, combined, kind_set, exclude, params)
    # B: rebuild index without excluded blocks
    keep = [i for i in range(len(blocks)) if i not in exclude]
    idx2 = ps.build_indices([fields_all[i] for i in keep], params['ngram_sizes'])
    c2, _ = ps.score_blocks(qf, idx2, len(keep), params)
    combined = [0.0] * len(blocks)
    for j, i in enumerate(keep):
        combined[i] = c2[j]
    return ps.aggregate_methods(blocks, combined, kind_set, exclude, params)

rows = {'tool': Counter(), 'A': Counter(), 'B': Counter()}
ten = [k for v in rt.pick_10(rt.keys_by_stratum(blocks)[0]).values() for k in v]
ten_rows = {'tool': [], 'A': [], 'B': []}
t0 = time.time()
idxs = [i for i, b in enumerate(blocks) if b.get('key') and rt.md_for_key(b['key']) is not None]
for i in idxs:
    b = blocks[i]
    q = dict(rt.md_for_key(b['key'])); q['base_key'] = b['key']
    if rt._kind_category(q['kind']) != rt._kind_category(b['kind']):
        continue
    gk = ps.group_key_of(b)
    for v in ('tool', 'A', 'B'):
        r = ps.true_rank_of(rank_variant(q, v), {gk})
        rows[v]['n'] += 1
        rows[v]['hit1'] += (r == 1)
        rows[v]['hit3'] += (r is not None and r <= 3)
for k in ten:
    q = dict(rt.md_for_key(k)); q['base_key'] = k
    tg = {ps.group_key_of(b) for b in blocks if b.get('key') == k}
    for v in ('tool', 'A', 'B'):
        ten_rows[v].append(ps.true_rank_of(rank_variant(q, v), tg))
out = Path(__file__).with_suffix('.log')
out.write_text(json.dumps({'loo': {v: dict(c) for v, c in rows.items()},
                           'ten_ranks': ten_rows, 'ten_keys': ten, 'seconds': round(time.time() - t0, 1)},
                          ensure_ascii=False, indent=1), encoding='utf-8')
print(out.read_text())
