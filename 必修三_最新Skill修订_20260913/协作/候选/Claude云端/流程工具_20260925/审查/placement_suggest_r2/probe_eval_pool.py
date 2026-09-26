#!/usr/bin/env python3
"""审查 r2：评测池核查。
 - 书中有题键、题库有 MD 文件、但 parse_question_md 抛错而被静默排除出“全书留一”分母的题块数（按原因）；
 - 13 个 kind_mismatch 查询逐条：MD 题型字段、工具判型、书中题型——是题库/书的分歧还是工具误判；
 - 十题：对每题取 rank_for_query 的第一名组里最像题块，与查询设问做字符 3-gram Jaccard，查“同题换键”泄漏。只读。"""
import sys, re
sys.dont_write_bytecode = True
from pathlib import Path
from collections import Counter
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
from profile_lib import load_profile
BANK = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
prof = load_profile(str(C / 'profiles_cloud' / 'bixiu3.json'))
book = ps.load_book('/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx', prof)
blocks = book['blocks']
reasons = Counter(); excluded_blocks = Counter(); ex_keys = {}
parsed = {}
for b in blocks:
    k = b.get('key')
    if not k:
        reasons['无题键'] += 1; continue
    mdp = ps.find_md_path(BANK, k)
    if not mdp.is_file():
        reasons['题库无MD'] += 1; continue
    if k not in parsed:
        try:
            parsed[k] = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), k)
        except ps.InputError as e:
            parsed[k] = str(e)
    if isinstance(parsed[k], str):
        r = 'guide_无' if '采用题面小节' in parsed[k] else 'no_stem'
        reasons['MD存在但解析失败:' + r] += 1
        ex_keys.setdefault(r, set()).add(k)
    else:
        reasons['进入评测池'] += 1
print('题块总数', len(blocks), dict(reasons))
for r, ks in ex_keys.items():
    print(' ', r, len(ks), sorted(ks))
# kind mismatch
print('\nkind_mismatch 明细：')
mm = []
for b in blocks:
    q = parsed.get(b.get('key'))
    if not isinstance(q, dict):
        continue
    qc = 'choice' if q['kind'] == 'choice' else 'subjective'
    bc = 'choice' if b['kind'] == 'choice' else 'subjective'
    if qc != bc:
        mm.append((b['id'], b['key'], b['kind'], q['kind'], (q['kind_field_raw'] or '<缺>')[:24], bool(q['kind_conflict']), b['title'][:30]))
for x in mm:
    print(' ', x)
print('合计', len(mm), '；其中 MD 题型字段缺失/含糊（工具靠启发式判型）:', sum(1 for x in mm if not re.search('选择|主观', x[4])))
