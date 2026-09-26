import re
from common import *
from collections import Counter
NEG = re.compile(r'未找到|未提供|not_available|N/A|无\s*E1|非\s*E1|无正式|仅有参考答案|E1_candidate_pending|pending|正式评分槽为\s*0|没有为本题提供|按\s*E3|不得升格|不能升格|无逐点|无该题|no_fixed_slots|缺失|暂无|待补|待核')
SUSP_H = re.compile(r'参考|答案|边界|候选|讲评|E2|解析|说明|状态|来源')
rows = []
fp_body, susp_head = [], []
stats = Counter()
for p in sorted((BANK / 'questions').glob('*/*.md')):
    if p.name == 'README.md': continue
    t = p.read_text(encoding='utf-8', errors='replace')
    try:
        q = ps.parse_question_md(t, p.stem)
    except ps.InputError:
        stats['inputerror'] += 1; continue
    if q['kind'] == 'choice':
        stats['choice'] += 1; continue
    stats['subj'] += 1
    if not q['e1_present']:
        stats['no_e1'] += 1; continue
    stats['e1'] += 1
    rub = q['rubric']
    m = NEG.search(rub)
    if m:
        i = m.start()
        fp_body.append((p.stem, q['e1_header'], m.group(0), rub[max(0,i-60):i+60].replace('\n',' / ')))
    if SUSP_H.search(q['e1_header'] or ''):
        susp_head.append((p.stem, q['e1_header']))
print(dict(stats))
print('\n### e1_present=True but chosen rubric body contains a negative status word somewhere:', len(fp_body))
for r in fp_body: print(' ', r)
print('\n### e1_present=True with suspicious header words:', len(susp_head))
for r in susp_head: print(' ', r)
