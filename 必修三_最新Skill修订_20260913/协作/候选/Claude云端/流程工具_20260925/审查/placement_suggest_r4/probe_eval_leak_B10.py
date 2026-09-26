"""真留一（把同题键题块从书里删掉后重建索引＝生产里“书中本无此题”的情形）只跑十题与固定种子抽的 120 块，
与工具评测口径对照。只读。"""
import sys, json, time, random
sys.dont_write_bytecode = True
from pathlib import Path
from collections import Counter
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
import run_tests_placement_suggest as rt
prof, book, indices = rt.load_book_and_indices(rt.BOOK3, rt.PROFILE)
blocks = book['blocks']; params = ps.DEFAULT_PARAMS
intro = ps.build_method_intro(book['doc'], book['heads'], ps.method_desc_style_set(prof))
fields_all = ps.block_fields_all(blocks, intro)
def ranks(q, true_gks):
    exclude = ps.matching_block_idxs(blocks, q['base_key'])
    kind_set = ps.KIND_GROUPS['choice' if q['kind'] == 'choice' else 'subjective']
    qf = {'material': q['material'], 'ask': q['ask'], 'rubric': q['rubric'], 'method': (q['ask'] + '\n' + q['material']).strip()}
    c_tool, _ = ps.score_blocks(qf, indices, len(blocks), params)
    r_tool = ps.true_rank_of(ps.aggregate_methods(blocks, c_tool, kind_set, exclude, params), true_gks)
    keep = [i for i in range(len(blocks)) if i not in exclude]
    idx2 = ps.build_indices([fields_all[i] for i in keep], params['ngram_sizes'])
    c2, _ = ps.score_blocks(qf, idx2, len(keep), params)
    cb = [0.0] * len(blocks)
    for j, i in enumerate(keep): cb[i] = c2[j]
    r_b = ps.true_rank_of(ps.aggregate_methods(blocks, cb, kind_set, exclude, params), true_gks)
    return r_tool, r_b
t0 = time.time()
ten = [k for v in rt.pick_10(rt.keys_by_stratum(blocks)[0]).values() for k in v]
ten_out = []
for k in ten:
    q = dict(rt.md_for_key(k)); q['base_key'] = k
    tg = {ps.group_key_of(b) for b in blocks if b.get('key') == k}
    ten_out.append((k,) + ranks(q, tg))
idxs = [i for i, b in enumerate(blocks) if b.get('key') and rt.md_for_key(b['key']) is not None
        and rt._kind_category(rt.md_for_key(b['key'])['kind']) == rt._kind_category(b['kind'])]
rnd = random.Random(4); sample = sorted(rnd.sample(idxs, 120))
cnt = Counter()
for i in sample:
    b = blocks[i]; q = dict(rt.md_for_key(b['key'])); q['base_key'] = b['key']
    rt_, rb = ranks(q, {ps.group_key_of(b)})
    cnt['n'] += 1; cnt['tool_hit1'] += (rt_ == 1); cnt['tool_hit3'] += (rt_ is not None and rt_ <= 3)
    cnt['trueLOO_hit1'] += (rb == 1); cnt['trueLOO_hit3'] += (rb is not None and rb <= 3)
def h(rs, n): return sum(1 for r in rs if r is not None and r <= n)
res = {'ten': ten_out,
       'ten_tool_hit1_hit3': [h([x[1] for x in ten_out], 1), h([x[1] for x in ten_out], 3)],
       'ten_trueLOO_hit1_hit3': [h([x[2] for x in ten_out], 1), h([x[2] for x in ten_out], 3)],
       'sample120_seed4': dict(cnt), 'seconds': round(time.time() - t0, 1)}
out = Path(__file__).with_suffix('.log'); out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
print(out.read_text())
