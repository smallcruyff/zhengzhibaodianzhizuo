import sys, time, re, json
sys.dont_write_bytecode = True
from pathlib import Path
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
from profile_lib import load_profile
from block_index import render_recs, sig
BANK = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
B = '/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
prof = load_profile(str(C/'profiles_cloud'/'bixiu3.json'))
book = ps.load_book(B, prof)
blocks = book['blocks']
# precompute block texts
btxt = [render_recs(b['_recs'][1:], book['doc']['rels']) for b in blocks]
bsets = [ps._ngram_set(t) for t in btxt]
inbook = set()
for b in blocks:
    for k in (b.get('keys_all') or [b.get('key')]):
        if k: inbook.add(k.split('(')[0])
rows = []
t0 = time.time()
n = 0
for p in sorted((BANK/'questions').glob('*/*.md')):
    if p.name == 'README.md': continue
    key = p.stem
    if key in inbook: continue
    try:
        q = ps.parse_question_md(p.read_text(encoding='utf-8', errors='replace'), key)
    except ps.InputError:
        continue
    n += 1
    qs = ps._ngram_set(q['stem_full'])
    if not qs: continue
    best = None
    for i, bs in enumerate(bsets):
        r = len(qs & bs)/len(qs) if bs else 0
        if best is None or r > best[1]: best = (i, r)
    if best[1] >= 0.6:
        b = blocks[best[0]]
        # ask-level comparison: does the query's ask appear in block?
        ask = q['ask'] or ''
        ask_sig = sig(ask)
        ask_cont = ps.ngram_containment(ask, btxt[best[0]]) if ask_sig else None
        rows.append({'key': key, 'kind': q['kind'], 'block': b['id'], 'block_key': b.get('key'), 'ratio': round(best[1], 3),
                     'ask_containment': (round(ask_cont, 3) if ask_cont is not None else None), 'ask': ask[:80]})
dt = time.time() - t0
out = Path(__file__).with_suffix('.log')
with out.open('w', encoding='utf-8') as f:
    f.write(f'not-in-book parseable bank questions: {n}; flagged (>=0.6): {len(rows)}; scan {dt:.1f}s\n')
    same_qno = [r for r in rows if r['block_key'] and r['key'].rsplit('-Q',1)[1] == r['block_key'].rsplit('-Q',1)[1]]
    f.write(f'same question number as matched block key: {len(same_qno)}\n')
    low_ask = [r for r in rows if r['ask_containment'] is not None and r['ask_containment'] < 0.5]
    f.write(f'flagged but ask containment < 0.5 (same material, different ask?): {len(low_ask)}\n')
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
print(out.read_text()[:8000])
