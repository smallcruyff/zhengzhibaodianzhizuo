#!/usr/bin/env python3
"""审查 r2：跨模块守卫漏报。对解析成功的主观题 MD：题面节原文（含引用块）里的设问句含 stem_module_guard 词，但工具
解析出的 ask 不含 ⇒ 守卫漏报。区分原因：引用块被丢（clean_prose 跳过“>”行）/ split_ask 只取最后一个设问（前面小问的
模块限定落进 material）。只读。"""
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
guard = prof['sources']['stem_module_guard']
ASKY = re.compile(r'(运用|结合|说明|分析|阐释|阐述|评析|概括|简析|谈谈|指出|归纳|请从|请你|设计|拟写|评价|解读|为什么)')
miss = []
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
    heads = ps.all_headings(text)
    si = [i for i, h in enumerate(heads) if h[1] == q['stem_header']][0]
    raw = ps.section_body(text, heads, si)
    for line in raw.splitlines():
        s = line.strip().lstrip('>').strip()
        g = next((g for g in guard if g in s), None)
        if g and ASKY.search(s) and g not in q['ask']:
            cause = 'quote_dropped' if line.strip().startswith('>') else ('in_material_split' if g in q['material'] else 'other')
            miss.append((p.stem, g, cause, s[:60]))
            break
print('主观题：设问句含跨模块限定词、工具 ask 却不含（守卫漏报）:', len(miss))
print('  原因:', Counter(m[2] for m in miss))
for m in miss[:20]:
    print('  ', m)
