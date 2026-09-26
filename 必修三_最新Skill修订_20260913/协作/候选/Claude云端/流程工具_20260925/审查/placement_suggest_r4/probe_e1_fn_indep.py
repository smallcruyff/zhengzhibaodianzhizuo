import sys
sys.dont_write_bytecode = True
import re, csv, json
from pathlib import Path
from collections import Counter
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
BANK = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
idx = {}
with (BANK/'indexes'/'rubric_links.csv').open(encoding='utf-8-sig', newline='') as f:
    for row in csv.DictReader(f):
        idx.setdefault(row.get('question_id','').strip(), set()).add((row.get('pair_status') or '').strip())
BROAD = re.compile(r'评分|细则|赋分|得分|SCORING|RUBRIC|阅卷|评标|给分|分值|标准答案|答案|E1', re.I)
PTS = re.compile(r'[（(]\s*\d+\s*分\s*[)）]|\d+\s*分[；;，,。]|得\s*\d+\s*分|给\s*\d+\s*分|\d分')
stats = Counter()
rows = []
for p in sorted((BANK/'questions').glob('*/*.md')):
    if p.name == 'README.md':
        continue
    text = p.read_text(encoding='utf-8', errors='replace')
    try:
        q = ps.parse_question_md(text, p.stem)
    except ps.InputError:
        stats['inputerror'] += 1
        continue
    if q['kind'] == 'choice':
        continue
    stats['subj'] += 1
    if q['e1_present']:
        stats['e1_true'] += 1
        continue
    stats['e1_false'] += 1
    heads = ps.all_headings(text)
    cands = []
    for i,(lvl,h,s,e) in enumerate(heads):
        if BROAD.search(h):
            body = ps.clean_prose(ps.section_body(text, heads, i))
            npts = len(PTS.findall(body))
            cands.append((lvl, h, npts, len(body)))
    best = max(cands, key=lambda c: c[2]) if cands else None
    rows.append({'key': p.stem, 'index': sorted(idx.get(p.stem, [])), 'e1_header': q['e1_header'],
                 'best_broad': best, 'all_broad': cands})
out = Path(__file__).with_suffix('.log')
with out.open('w', encoding='utf-8') as f:
    f.write(json.dumps(dict(stats), ensure_ascii=False)+'\n')
    # suspicious: broad-headed sections with >=3 point markers
    sus = [r for r in rows if r['best_broad'] and r['best_broad'][2] >= 3]
    f.write(f'e1_false with a broad-named section having >=3 point markers: {len(sus)}\n')
    hc = Counter()
    for r in sus:
        hc[re.sub(r'\d+|Q\d+|S[0-9a-f]{6,}|p\d+|P\d+','#', r['best_broad'][1])[:60]] += 1
    for h,c in hc.most_common(80):
        f.write(f'  {c:4d}  {h}\n')
    f.write('\n=== detail ===\n')
    for r in sus:
        f.write(json.dumps({k: r[k] for k in ('key','index','e1_header','best_broad')}, ensure_ascii=False)+'\n')
print(out.read_text()[:6000])
