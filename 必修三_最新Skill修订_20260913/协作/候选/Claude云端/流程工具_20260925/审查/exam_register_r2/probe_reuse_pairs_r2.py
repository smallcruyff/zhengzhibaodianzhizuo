"""r2 探针：bank_duplicate_exams.csv 的 10 对 shared_or_reused 参考对，逐题两两算 containment（工具同一套抽取/指纹），
列最高分、双方 basis、缺题面的题。只读。"""
import sys, csv
sys.dont_write_bytecode = True
from pathlib import Path
HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE))
import exam_register as er
R = Path('/home/user/zhengzhibaodianzhizuo')
B = R / 'DeepSeek_政治题库资料库_20260918'
T, _ = er.load_bank_alias_tables(B)
rows = list(csv.DictReader(open(R / '后勤管理/20260923_脚本化与跨书工具/完整性调查_20260924/bank_duplicate_exams.csv', encoding='utf-8-sig')))
cache = {}
def load(e):
    if e not in cache:
        cache[e] = er.load_exam_questions(B, e, T)
    return cache[e]
for r in rows:
    a, b = r['exam_a'], r['exam_b']
    qa, sa, ca = load(a); qb, sb, cb = load(b)
    best = []
    for x in qa:
        for y in qb:
            s = er.containment(x['ngrams'], y['ngrams'])
            if s > 0.2:
                best.append((round(s, 3), x['qid'].split('-')[-1], x['basis'], y['qid'].split('-')[-1], y['basis']))
    best.sort(reverse=True)
    print(f"{a} ~ {b} ref={r['dup_questions']} {r['kind']} | skipped_a={[q.split('-')[-1] for q in sa]} skipped_b={[q.split('-')[-1] for q in sb]} | top={best[:4]}")
