"""r2 探针：参考复用对在“逐题 MD 全文（去掉读取指引/身份/来源等工程节）”层面有没有字面重叠，用来判断参考表是不是噪声。只读。"""
import sys, csv, re
sys.dont_write_bytecode = True
from pathlib import Path
HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE))
import exam_register as er
import qpack
R = Path('/home/user/zhengzhibaodianzhizuo')
B = R / 'DeepSeek_政治题库资料库_20260918'
SKIP = re.compile(r'读取指引|身份|来源定位|质量标记|配对状态|已排除|复核|状态')
def secs_text(p):
    _, secs = qpack.split_md(p.read_text(encoding='utf-8'))
    out = []
    for s in secs:
        if SKIP.search(s['heading']):
            continue
        out.append((s['heading'], s['body']))
    return out
rows = list(csv.DictReader(open(R / '后勤管理/20260923_脚本化与跨书工具/完整性调查_20260924/bank_duplicate_exams.csv', encoding='utf-8-sig')))
for r in rows[2:]:
    a, b = r['exam_a'], r['exam_b']
    A = [(p.stem.split('-')[-1], h, er.ngrams(er.normalize_stem(t))) for p in sorted((B/'questions'/a).glob(a+'-Q*.md')) for h, t in secs_text(p)]
    Bq = [(p.stem.split('-')[-1], h, er.ngrams(er.normalize_stem(t))) for p in sorted((B/'questions'/b).glob(b+'-Q*.md')) for h, t in secs_text(p)]
    best = []
    for qa, ha, na in A:
        if len(na) < 40: continue
        for qb, hb, nb in Bq:
            if len(nb) < 40: continue
            inter = len(na & nb)
            if inter >= 30:
                best.append((round(inter / min(len(na), len(nb)), 3), inter, qa, ha[:18], qb, hb[:18]))
    best.sort(reverse=True)
    print(f"{a} ~ {b}: top={best[:3]}")
