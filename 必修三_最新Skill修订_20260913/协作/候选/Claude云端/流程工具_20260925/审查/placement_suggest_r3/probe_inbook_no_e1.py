import re
from common import *
from collections import Counter
prof, book, idx = load()
blocks = book['blocks']
keys = sorted({b['key'] for b in blocks if b.get('key') and b['kind'] != 'choice'})
cnt = Counter(); rows = []
for k in keys:
    q, t = md(k)
    if q is None: cnt['no_md_or_inputerror'] += 1; continue
    if q['kind'] == 'choice': cnt['md_says_choice'] += 1; continue
    if q['e1_present']: cnt['e1_true'] += 1; continue
    exc = ps.no_e1_exception_hit(prof, BANK, k)
    if exc: cnt['no_e1_but_named_exception'] += 1; continue
    cnt['flag_no_e1'] += 1
    # does the book have a 细则 bucket for this key?
    bl = [blocks[i] for i in ps.matching_block_idxs(blocks, k)]
    has_rubric = any(any('细则' in (lab or '') for lab in ps.segment_block_labels(b['_recs'][1:]).keys()) for b in bl)
    rs = re.search(r'rubric_status[:：]\s*\**([^\n*]+)', t or '')
    rows.append((k, q['e1_header'], (rs.group(1).strip() if rs else None), has_rubric, [b['id'] for b in bl][:3]))
print(dict(cnt))
print('in-book subjective keys the tool flags “主观题未找到E1：按规则不收”:', len(rows))
by_hdr = Counter(r[1] for r in rows)
print('by e1_header:', by_hdr.most_common())
by_status = Counter(r[2] for r in rows)
print('by bank rubric_status:', by_status.most_common())
for r in rows: print(' ', r)
