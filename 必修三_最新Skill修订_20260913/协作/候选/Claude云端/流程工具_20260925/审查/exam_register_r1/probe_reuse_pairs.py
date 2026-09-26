import sys
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925')
import exam_register as er
from pathlib import Path
B = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918/questions')
def full_ng(p):
    t = p.read_text(encoding='utf-8')
    return er.ngrams(er.normalize_stem(t))
pairs = [('BJ-2025-BJ-GAOKAO','BJ-2026-FT-ERMO'),('BJ-2026-CP-QIMO','BJ-2026-FT-YIMO'),('BJ-2023-FT-YIMO','BJ-2026-FT-YIMO'),('BJ-2024-BJ-GAOKAO','BJ-2026-HD-QIZHONG'),('BJ-2024-BJ-GAOKAO','BJ-2025-FT-ERMO')]
for a, b in pairs:
    fa = {p.stem: p for p in (B/a).glob(f'{a}-Q*.md')}
    fb = {p.stem: p for p in (B/b).glob(f'{b}-Q*.md')}
    na = {k: full_ng(v) for k, v in fa.items()}; nb = {k: full_ng(v) for k, v in fb.items()}
    best = []
    for ka, ga in na.items():
        for kb, gb in nb.items():
            inter = len(ga & gb)
            best.append((inter, ka, kb))
    best.sort(reverse=True)
    inter, ka, kb = best[0]
    sa = er.extract_stem_from_md(fa[ka].read_text(encoding='utf-8')); sb = er.extract_stem_from_md(fb[kb].read_text(encoding='utf-8'))
    ga, gb = er.fingerprint_stem(sa), er.fingerprint_stem(sb)
    print(f'{a}~{b}: top full-MD 10gram overlap={inter} {ka}~{kb} (2nd={best[1][0]}) | tool stem sim={er.containment(ga or set(), gb or set()):.3f} stem_lens={len(er.normalize_stem(sa))},{len(er.normalize_stem(sb))}')
