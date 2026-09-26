import re
from common import *
SCORE = re.compile(r'\d+\s*分|[（(]\s*\d+\s*分\s*[)）]|水平\s*[一二三四1-4]|给\s*\d|\+\s*\d')
HEADRX = re.compile(r'细则|评分|评标|E1|赋分|给分|阅卷')
NEGH = re.compile(r'未找到|未提供|not_available|N/A|没有该题|无题级|无逐点|正式评分槽为\s*0|没有为本题提供|pending')
prof = load_profile(str(PROFILE))
from block_index import BookCfg
out = []
for p in sorted((BANK / 'questions').glob('*/*.md')):
    if p.name == 'README.md': continue
    t = p.read_text(encoding='utf-8', errors='replace')
    try:
        q = ps.parse_question_md(t, p.stem)
    except ps.InputError:
        continue
    if q['kind'] == 'choice' or q['e1_present']: continue
    heads = ps.all_headings(t)
    for i, (lvl, h, s, e) in enumerate(heads):
        if not HEADRX.search(h): continue
        body = ps.clean_prose(ps.section_body(t, heads, i))
        n = len(SCORE.findall(body))
        if n >= 3 and not NEGH.search(body[:200]):
            out.append((p.stem, q['e1_header'], h, n, ps.E1_EXCLUDE_TITLE_RX.search(h) is not None, body[:120].replace('\n', ' / ')))
            break
print('subjective e1_present=False but some rubric-like heading has >=3 score marks & no leading negative:', len(out))
for r in out: print(r)
