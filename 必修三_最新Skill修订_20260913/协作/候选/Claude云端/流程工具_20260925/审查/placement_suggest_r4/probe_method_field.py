"""考法字段（考法名+考法说明）是书作者按组内已有例题写的，被留出的题本身就参与了它的措辞（如“考法6 对条型：
给法条判位阶与良法（2题）”）。看 method 权重置 0 时（归一化用生产口径 A）命中率变化，估计这层固有乐观偏差。只读。"""
import sys, json
sys.dont_write_bytecode = True
from pathlib import Path
from collections import Counter
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
import run_tests_placement_suggest as rt
prof, book, indices = rt.load_book_and_indices(rt.BOOK3, rt.PROFILE)
blocks = book['blocks']
def run(params):
    cnt = Counter()
    for i, b in enumerate(blocks):
        if not b.get('key') or rt.md_for_key(b['key']) is None: continue
        q = dict(rt.md_for_key(b['key'])); q['base_key'] = b['key']
        if rt._kind_category(q['kind']) != rt._kind_category(b['kind']): continue
        exclude = ps.matching_block_idxs(blocks, b['key'])
        kind_set = ps.KIND_GROUPS['choice' if q['kind'] == 'choice' else 'subjective']
        qf = {'material': q['material'], 'ask': q['ask'], 'rubric': q['rubric'], 'method': (q['ask'] + '\n' + q['material']).strip()}
        combined = [0.0] * len(blocks)
        for f, idx in indices.items():
            raw = idx.score(qf.get(f, ''), params['bm25_k1'], params['bm25_b'])
            vals = [v for j, v in raw.items() if j not in exclude]
            mx = max(vals) if vals else 0.0
            for j, v in raw.items():
                combined[j] += params['weights'].get(f, 0.0) * (v / mx if mx > 0 else 0.0)
        r = ps.true_rank_of(ps.aggregate_methods(blocks, combined, kind_set, exclude, params), {ps.group_key_of(b)})
        cnt['n'] += 1; cnt['hit1'] += (r == 1); cnt['hit3'] += (r is not None and r <= 3)
    return dict(cnt)
p0 = dict(ps.DEFAULT_PARAMS); p0['weights'] = dict(ps.DEFAULT_PARAMS['weights'])
p1 = dict(p0); p1['weights'] = dict(p0['weights'], method=0.0)
res = {'A_default': run(p0), 'A_method0': run(p1)}
out = Path(__file__).with_suffix('.log'); out.write_text(json.dumps(res, ensure_ascii=False), encoding='utf-8'); print(res)
