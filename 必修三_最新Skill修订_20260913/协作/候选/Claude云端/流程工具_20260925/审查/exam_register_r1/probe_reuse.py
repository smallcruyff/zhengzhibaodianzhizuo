import sys, csv
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925')
import exam_register as er
from pathlib import Path
bank = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
idx = er.BankIndex(bank); idx.ensure_all()
print('exams indexed', len(idx.by_exam), 'questions', sum(len(v) for v in idx.by_exam.values()))
print('skipped per exam (nonzero):', {k: len(v) for k, v in idx.skipped.items() if v})
ref = list(csv.DictReader(open('/home/user/zhengzhibaodianzhizuo/后勤管理/20260923_脚本化与跨书工具/完整性调查_20260924/bank_duplicate_exams.csv', encoding='utf-8-sig')))
for r in ref:
    a, b = r['exam_a'], r['exam_b']
    res_a = er.scan_duplicates(idx, a, idx.by_exam.get(a, []), exclude_exam=a)
    hit = [x for x in res_a if x['exam_id'] == b]
    res_b = er.scan_duplicates(idx, b, idx.by_exam.get(b, []), exclude_exam=b)
    hitb = [x for x in res_b if x['exam_id'] == a]
    # best raw similarity between any pair of questions a x b
    best = (0, None, None)
    for qa in idx.by_exam.get(a, []):
        for qb in idx.by_exam.get(b, []):
            s = er.containment(qa['ngrams'], qb['ngrams'])
            if s > best[0]: best = (s, qa['qid'], qb['qid'])
    print(f"{a} ~ {b} ref={r['kind']}/{r['dup_questions']} | a->b: {[(h['kind'], h['matched_questions']) for h in hit]} | b->a: {[(h['kind'], h['matched_questions']) for h in hitb]} | best_pair_sim={best[0]:.3f} {best[1]} {best[2]} | na={len(idx.by_exam.get(a,[]))} skipped_a={len(idx.skipped.get(a,[]))} nb={len(idx.by_exam.get(b,[]))} skipped_b={len(idx.skipped.get(b,[]))}")
