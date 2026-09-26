#!/usr/bin/env python3
"""审查 r2：E1 假阳精确统计（v2，含“标题正面、正文明写无E1”）。
负面判定（强语句，需人读得出“这不是E1”）：
  标题：E3|非E1|非正式|不是正式|不得当作/视为/据此/升格|严格不升格|边界|N/A
  正文：正式评分槽为0|没有为本题提供|无 E1|N/A_with_basis|不能升级为|不得升格|按 E3 保留|非E1|不是正式评分细则|
        不等同于同题独立正式评分细则|无正式(评分)?细则|无分项阅卷细则|正式评分槽.{0,4}0
“真 E1”：标题正面且不负面、正文按工具 e1_present 有实质且正文不负面。
统计：工具 e1_present=True，但全文没有任何“真 E1”节 ⇒ 过滤被绕过。只读。"""
import sys, re, json
sys.dont_write_bytecode = True
from pathlib import Path
from collections import Counter
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
from profile_lib import load_profile
BANK = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
NEG_H = re.compile(r'E3|非\s*E1|非正式|不是正式|不得(当作|视为|据此|升格)|不能(当作|升格)|严格不升格|边界|N/?A')
NEG_B = re.compile(r'正式评分槽为\s*0|正式评分槽.{0,4}0|没有为本题提供|无\s*E1|N/A_with_basis|不能升级为|不得升格|按\s*E3\s*保留|非\s*E1|'
                   r'不是正式评分细则|不等同于同题独立正式评分细则|无正式(评分)?细则|无分项阅卷细则')
POS = re.compile(r'E1(?!\d)|正式评分|阅卷细则|评分细则|评标')
prof = load_profile(str(C / 'profiles_cloud' / 'bixiu3.json'))
book = ps.load_book('/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx', prof)
book_keys = {}
for b in book['blocks']:
    for k in b.get('keys_all') or []:
        book_keys.setdefault(k.split('(')[0], []).append(b['id'])
exc = prof['sources']['no_e1_exceptions']['whole_papers']
bypass = []
hdr = Counter()
for p in sorted((BANK / 'questions').glob('*/*.md')):
    if p.name == 'README.md':
        continue
    text = p.read_text(encoding='utf-8', errors='replace')
    try:
        q = ps.parse_question_md(text, p.stem)
    except ps.InputError:
        continue
    if q['kind'] == 'choice' or not q['e1_present']:
        continue
    heads = ps.all_headings(text)
    real = []
    for i, (lvl, h, s, e) in enumerate(heads):
        if POS.search(h) and not NEG_H.search(h) and not ps.E1_EXCLUDE_TITLE_RX.search(h):
            body = ps.clean_prose(ps.section_body(text, heads, i))
            if ps.e1_present(body) and not NEG_B.search(body):
                real.append(h)
    if not real:
        why = (NEG_H.search(q['e1_header'] or '') and '标题:' + NEG_H.search(q['e1_header']).group(0)) or \
              (NEG_B.search(q['rubric']) and '正文:' + NEG_B.search(q['rubric']).group(0)) or '其他'
        bypass.append({'key': p.stem, 'e1_header': q['e1_header'], 'why': why,
                       'in_book': book_keys.get(p.stem), 'rubric_head': re.sub(r'\s+', ' ', q['rubric'])[:80]})
        hdr[q['e1_header'][:26]] += 1
print('工具判 e1_present=True、但全文无“真 E1”节的主观题:', len(bypass))
print('  其中题键已在必修三第52批书中:', sum(1 for x in bypass if x['in_book']))
print('  标题分布:', hdr.most_common(20))
print('  原因分布:', Counter(x['why'].split(':')[0] for x in bypass))
for x in bypass:
    print('  ', x['key'], '|', x['e1_header'][:40], '|', x['why'], '|', 'BOOK' if x['in_book'] else '', '|', x['rubric_head'][:60])
json.dump(bypass, open(Path(__file__).with_suffix('.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
