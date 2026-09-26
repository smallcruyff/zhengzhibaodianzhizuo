#!/usr/bin/env python3
"""审查 r2：profile sources.no_e1_exceptions（2026北京高考/2024顺义二模/2026石景山期末 整卷具名例外，
SCOPE-E1“已由用户具名的无细则例外不变”）下的主观题，placement_suggest 是否仍标“按规则不收”。只读。"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
from profile_lib import load_profile
BANK = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
prof = load_profile(str(C / 'profiles_cloud' / 'bixiu3.json'))
print('no_e1_exceptions =', prof['sources'].get('no_e1_exceptions'))
for exam in ('BJ-2026-BJ-GAOKAO', 'BJ-2024-SY-ERMO', 'BJ-2026-SJS-QIMO'):
    for md in sorted((BANK / 'questions' / exam).glob(exam + '-Q*.md'), key=lambda p: int(p.stem.rsplit('Q', 1)[1])):
        try:
            q = ps.parse_question_md(md.read_text(encoding='utf-8', errors='replace'), md.stem)
        except ps.InputError as e:
            print(md.stem, 'InputError', str(e)[:80]); continue
        if q['kind'] == 'choice':
            continue
        would_flag = not q['e1_present']
        print(md.stem, 'kind=', q['kind'], 'e1_present=', q['e1_present'], 'e1_header=', q['e1_header'],
              '=> flags“按规则不收”' if would_flag else '')
