#!/usr/bin/env python3
"""审查 r2：全题库逐题 MD 过一遍 placement_suggest.parse_question_md，统计：
  - 解析失败（读取指引“无” / 找不到题面）及题面候选标题；
  - E1 选中节的可疑情况：标题含“非E1/E3/边界/参考”或正文明写“正式评分槽为0/非E1/不拆/方向性/无正式”等却判 e1_present=True（假阳）；
  - 题型字段取值分布与冲突；
  - 读取指引点名的题面节在文档里找不到（退回关键词）的情况。
只读，结果打印到 stdout。"""
import sys, re, json
sys.dont_write_bytecode = True
from pathlib import Path
from collections import Counter, defaultdict
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
BANK = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
mds = sorted(p for p in (BANK / 'questions').glob('*/*.md') if p.name != 'README.md')
fail = Counter(); fail_heads = Counter(); fail_exams = Counter()
kinds = Counter(); kfield = Counter(); conflicts = []
e1_fp = []; e1_hdr = Counter(); dir_missing = []
NEG_BODY = re.compile(r'正式评分槽为\s*0|非\s*E1|不是\s*E1|不拆|方向性|无正式|没有正式|E1\s*[:：]?\s*(无|N/?A|缺)|不作\s*E1|不得当作正式|不能当作正式|无分项')
NEG_HEAD = re.compile(r'非\s*E1|E3|边界|参考答案|参考作答|候选|说明|状态')
for p in mds:
    text = p.read_text(encoding='utf-8', errors='replace')
    heads = ps.all_headings(text)
    d = ps.guided_stem_directive(text, heads)
    if d and not d.startswith('无') and ps.guided_stem_index(heads, d) is None:
        dir_missing.append((p.stem, d))
    try:
        q = ps.parse_question_md(text, p.stem)
    except ps.InputError as e:
        reason = 'guide_无' if '采用题面小节' in str(e) else 'no_stem'
        fail[reason] += 1
        fail_exams[(reason, p.parent.name)] += 1
        if reason == 'no_stem':
            for lvl, h, s, e2 in heads:
                if lvl <= 3:
                    fail_heads[re.sub(r'（.*?）|\(.*?\)', '', h)[:20]] += 1
        continue
    kinds[q['kind']] += 1
    kfield[(q['kind_field_raw'] or '<缺>')[:12]] += 1
    if q['kind_conflict']:
        conflicts.append((p.stem, q['kind'], (q['kind_field_raw'] or '')[:20]))
    if q['kind'] != 'choice':
        e1_hdr[(q['e1_header'] or '<无>')[:24]] += 1
        if q['e1_present'] and (NEG_HEAD.search(q['e1_header'] or '') or NEG_BODY.search(q['rubric'] or '')):
            e1_fp.append((p.stem, q['e1_header'], (NEG_HEAD.search(q['e1_header'] or '') or NEG_BODY.search(q['rubric'])).group(0),
                          re.sub(r'\s+', ' ', q['rubric'])[:90]))
print('MD 总数', len(mds))
print('解析失败', dict(fail))
print('失败卷（前 20）', fail_exams.most_common(20))
print('no_stem 失败 MD 的 1-3 级标题（前 25）', fail_heads.most_common(25))
print('题型', dict(kinds))
print('题型字段（截 12 字，前 20）', kfield.most_common(20))
print('题型冲突', len(conflicts), conflicts[:10])
print('读取指引点名的题面节找不到（退回关键词）', len(dir_missing), dir_missing[:8])
print('主观题 e1_header 分布（前 25）', e1_hdr.most_common(25))
print('E1 可疑假阳（e1_present=True 但标题/正文明写非E1/槽为0/方向性等）', len(e1_fp))
by_exam = Counter(x[0].rsplit('-Q', 1)[0] for x in e1_fp)
print('  按卷', by_exam.most_common(30))
for x in e1_fp[:25]:
    print('  ', x)
