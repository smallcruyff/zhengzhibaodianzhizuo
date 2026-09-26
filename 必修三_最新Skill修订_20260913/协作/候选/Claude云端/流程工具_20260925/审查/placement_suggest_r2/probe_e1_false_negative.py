#!/usr/bin/env python3
"""审查 r2：E1 假阴。工具判主观题 e1_present=False，但文档里有标题正面（E1|正式评分|阅卷细则|评分细则|评标，且不含
E3/非E1/候选/不得/边界 等）的节，正文含逐点分值信号（\\d分|水平|赋分|给分|采分），且正文开头 80 字内没有“未找到/未提供/
not_available/N/A”状态语。列出供人工核对（NO_E1_HINTS 是全文子串匹配，正文任何位置出现“未找到/未提供”都会整节判无）。只读。"""
import sys, re
sys.dont_write_bytecode = True
from pathlib import Path
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
BANK = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
NEG_H = re.compile(r'E3|非\s*E1|非正式|不是正式|不得|不能|严格不升格|边界|N/?A|候选|pending|状态', re.I)
POS = re.compile(r'E1(?!\d)|正式评分|阅卷细则|评分细则|评标')
SCORE = re.compile(r'\d+\s*分|水平\s*[一二三四1-4]|赋分|给分|采分')
HEADNEG = re.compile(r'未找到|未提供|not_available|N/A|没有该题|无题级|无逐点')
fn = []
n = 0
for p in sorted((BANK / 'questions').glob('*/*.md')):
    if p.name == 'README.md':
        continue
    text = p.read_text(encoding='utf-8', errors='replace')
    try:
        q = ps.parse_question_md(text, p.stem)
    except ps.InputError:
        continue
    if q['kind'] == 'choice' or q['e1_present']:
        continue
    n += 1
    heads = ps.all_headings(text)
    for i, (lvl, h, s, e) in enumerate(heads):
        if POS.search(h) and not NEG_H.search(h):
            body = ps.clean_prose(ps.section_body(text, heads, i))
            if len(re.sub(r'\s', '', body)) >= 60 and len(SCORE.findall(body)) >= 2 and not HEADNEG.search(body[:80]):
                hint = next((x for x in ps.NO_E1_HINTS if x in body), None)
                fn.append((p.stem, h[:30], hint, re.sub(r'\s+', ' ', body)[:70]))
                break
print('工具判无 E1 的主观题', n, '；其中另有正面标题节、含逐点分值且开头无“未找到”状态语的（疑似假阴）:', len(fn))
for x in fn:
    print('  ', x)
