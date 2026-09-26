#!/usr/bin/env python3
"""审查 r2：E1 假阳精确统计。
对每道解析成功、判为主观题且 e1_present=True 的 MD：
  - chosen_negated：工具选中的 E1 节标题本身明写不是 E1（E3/非E1/非正式/不是正式/不得当作|视为|据此|升格/边界）；
  - real_e1_elsewhere：文档里是否另有一个“正面”的 E1 节（标题命中 E1|正式评分|阅卷细则|评分细则|评标，且标题
    不含上述否定词），其正文按工具自己的 e1_present 有实质内容。
chosen_negated 且无 real_e1_elsewhere ⇒ 题库只有 E3/方向性材料，工具却判“有正式细则”，“主观题无细则→不收”过滤被绕过。
另按 r1 旧口径（只认“正式评分”、取第一个命中）复算，判断是否为本轮返修新引入。只读。"""
import sys, re
sys.dont_write_bytecode = True
from pathlib import Path
from collections import Counter
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
BANK = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
NEG = re.compile(r'E3|非\s*E1|非正式|不是正式|不得(当作|视为|据此|升格)|不能(当作|升格)|边界|严格不升格')
POS = re.compile(r'E1(?!\d)|正式评分|阅卷细则|评分细则|评标')
OLD_RX = re.compile(r'正式评分')
book_keys = set()
try:
    from profile_lib import load_profile
    prof = load_profile(str(C / 'profiles_cloud' / 'bixiu3.json'))
    book = ps.load_book('/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx', prof)
    for b in book['blocks']:
        for k in b.get('keys_all') or []:
            book_keys.add(k.split('(')[0])
except Exception as e:
    print('book load failed', e)
bypass, bypass_old, samples = [], [], []
hdr = Counter()
n_subj = 0
for p in sorted((BANK / 'questions').glob('*/*.md')):
    if p.name == 'README.md':
        continue
    text = p.read_text(encoding='utf-8', errors='replace')
    try:
        q = ps.parse_question_md(text, p.stem)
    except ps.InputError:
        continue
    if q['kind'] == 'choice':
        continue
    n_subj += 1
    heads = ps.all_headings(text)
    real = False
    for i, (lvl, h, s, e) in enumerate(heads):
        if POS.search(h) and not NEG.search(h) and not ps.E1_EXCLUDE_TITLE_RX.search(h):
            if ps.e1_present(ps.clean_prose(ps.section_body(text, heads, i))):
                real = True
                break
    chosen_neg = bool(q['e1_header'] and NEG.search(q['e1_header']))
    if q['e1_present'] and chosen_neg and not real:
        bypass.append(p.stem)
        hdr[q['e1_header'][:30]] += 1
        if len(samples) < 12:
            samples.append((p.stem, q['e1_header'], re.sub(r'\s+', ' ', q['rubric'])[:70]))
    # r1 旧口径复算
    oi = ps.find_heading(heads, OLD_RX, max_level=2)
    old_present = bool(oi is not None and ps.e1_present(ps.clean_prose(ps.section_body(text, heads, oi))))
    if oi is not None and old_present and NEG.search(heads[oi][1]) and not real:
        bypass_old.append(p.stem)
print('解析成功的主观题 MD', n_subj)
print('本版：选中节标题明写非E1、全文另无正面E1节，却 e1_present=True（过滤被绕过）:', len(bypass))
print('  其中在必修三第52批书中已有同题键的:', len([k for k in bypass if k in book_keys]))
print('  选中标题分布:', hdr.most_common(15))
print('r1 旧口径（只认“正式评分”取第一个）同样绕过的:', len(bypass_old))
print('本版新增（r1 不绕过、本版绕过）:', len(set(bypass) - set(bypass_old)))
print('样例:')
for s in samples:
    print('  ', s)
print('全部题键:', bypass)
