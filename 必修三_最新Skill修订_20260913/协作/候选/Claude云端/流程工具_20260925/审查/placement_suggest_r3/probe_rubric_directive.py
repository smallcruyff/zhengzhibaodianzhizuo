import re
from common import *
RX = re.compile(r'^-\s*(?:正式评分优先读取|采用评分小节)[:：]\s*`?([^`\n]+?)`?\s*$', re.M)
rows = []
for p in sorted((BANK / 'questions').glob('*/*.md')):
    t = p.read_text(encoding='utf-8', errors='replace')
    m = RX.search(t)
    if not m: continue
    want = m.group(1).strip()
    try:
        q = ps.parse_question_md(t, p.stem)
    except ps.InputError as e:
        rows.append((p.stem, want, 'InputError', None)); continue
    heads = [h for _, h, _, _ in ps.all_headings(t)]
    exact = any(h.strip() == want for h in heads)
    agree = (q['e1_header'] or '').strip() == want or (q['e1_header'] or '').startswith(want)
    rows.append((p.stem, want, q['kind'], q['e1_present'], q['e1_header'], 'AGREE' if agree else ('DISAGREE' if exact else 'directive-heading-not-found')))
for r in rows: print(r)
