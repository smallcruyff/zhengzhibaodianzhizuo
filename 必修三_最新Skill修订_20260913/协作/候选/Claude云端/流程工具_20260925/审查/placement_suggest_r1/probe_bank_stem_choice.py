import sys; sys.dont_write_bytecode = True  # 不留 __pycache__
from common import *
import re, glob
files = sorted(glob.glob(str(BANK / 'questions' / '*' / '*.md')))
print('bank MDs', len(files))
bad = Counter(); ex = {}
stat = Counter()
for f in files:
    t = Path(f).read_text(encoding='utf-8', errors='replace')
    hs = ps.all_headings(t)
    gi = ps.guided_stem_index(t, hs)
    try:
        q = ps.parse_question_md(t, f)
    except ps.InputError:
        stat['parse_fail'] += 1; continue
    stat['ok'] += 1
    stat['via_guide' if gi is not None else 'via_keyword'] += 1
    h = q['stem_header']
    if re.search(r'不得当作题面|答案|讲评|解析|评分', h):
        bad[h[:40]] += 1; ex.setdefault(h[:40], Path(f).name)
    # guide says 无 but keyword fallback found something
    if re.search(r'采用题面小节[：:]\s*无', t) and gi is None:
        stat['guide_says_none_but_used_keyword_stem'] += 1
        ex.setdefault('NONE:'+h[:30], Path(f).name)
print(stat)
for h, c in bad.most_common(): print(c, h, ex[h])
print([ (k,v) for k,v in ex.items() if k.startswith('NONE:')][:10])
