import sys; sys.dont_write_bytecode = True  # 不留 __pycache__
from common import *
import re, glob
files = sorted(glob.glob(str(BANK / 'questions' / '*' / '*.md')))
n_subj = n_flag = n_missed = 0; ex = []
for f in files:
    t = Path(f).read_text(encoding='utf-8', errors='replace')
    try: q = ps.parse_question_md(t, f)
    except ps.InputError: continue
    if q['kind'] == 'choice': continue
    n_subj += 1
    if q['e1_present']: continue
    n_flag += 1
    hs = ps.all_headings(t)
    for i, (lvl, h, s, e) in enumerate(hs):
        if re.search(r'E1|阅卷细则|评分细则|评标|评分标准', h) and not re.search(r'候选|pending|不得|N/A|无\s*E1|无题级|参考答案', h):
            body = ps.clean_prose(ps.section_body(t, hs, i))
            if ps.e1_present(body):
                n_missed += 1; ex.append((Path(f).stem, h[:40], body[:60].replace('\n',' '))); break
print('bank subjective parsed', n_subj, 'flagged no-E1', n_flag, 'of which have a substantive E1-like section elsewhere', n_missed)
for x in ex[:15]: print('  ', x)
