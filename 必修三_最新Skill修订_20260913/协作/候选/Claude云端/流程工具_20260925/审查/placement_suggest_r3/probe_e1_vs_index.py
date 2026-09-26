import csv
from collections import defaultdict, Counter
from common import *
prof, book, idx = load()
inbook = {}
for b in book['blocks']:
    for k in ([b.get('key')] + list(b.get('keys_all') or [])):
        if k: inbook.setdefault(k.split('(')[0], []).append(b['id'])
st = defaultdict(set)
with open(BANK / 'indexes' / 'rubric_links.csv', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        st[r['question_id']].add(r['pair_status'])
tab = Counter(); fn = []; fp = []
for p in sorted((BANK / 'questions').glob('*/*.md')):
    if p.name == 'README.md': continue
    t = p.read_text(encoding='utf-8', errors='replace')
    try:
        q = ps.parse_question_md(t, p.stem)
    except ps.InputError:
        continue
    if q['kind'] == 'choice': continue
    matched = '已匹配正式材料' in st.get(p.stem, set())
    tab[(matched, q['e1_present'])] += 1
    if matched and not q['e1_present']:
        exc = ps.no_e1_exception_hit(prof, BANK, p.stem)
        fn.append((p.stem, q['e1_header'], 'EXEMPT' if exc else '', inbook.get(p.stem, [])[:3]))
print('rows=(index says 已匹配正式材料, tool e1_present):', dict(tab))
print('index 已匹配正式材料 but tool e1_present=False:', len(fn))
for r in fn: print('  ', r)

print('\n--- tool e1_present=True but index lacks 已匹配正式材料 (index may be stale) ---')
from collections import Counter as C2
hdrs = C2()
for p in sorted((BANK / 'questions').glob('*/*.md')):
    if p.name == 'README.md': continue
    t = p.read_text(encoding='utf-8', errors='replace')
    try:
        q = ps.parse_question_md(t, p.stem)
    except ps.InputError:
        continue
    if q['kind'] == 'choice' or not q['e1_present']: continue
    if '已匹配正式材料' in st.get(p.stem, set()): continue
    hdrs[(q['e1_header'], tuple(sorted(st.get(p.stem, set()))))] += 1
for (h, s), n in hdrs.most_common(): print(f'  {n:3d}  {h!r}  index={s}')
