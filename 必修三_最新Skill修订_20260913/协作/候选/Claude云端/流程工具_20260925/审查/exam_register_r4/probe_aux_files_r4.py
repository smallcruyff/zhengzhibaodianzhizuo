#!/usr/bin/env python3
"""r4 审查探针：M-H 修法改成“逐文件独立比对、按对手卷取最强一份”后，辅助文件（参考答案/评分材料/
细则/讲评等）单独成一份分母时，会不会对“别的卷”报出 duplicate_registration；以及原卷文件的
分母（total_questions=len(qs)，只数能做指纹的块）与切块数/题库题数的差距。进程内调用被审工具的
split_and_fingerprint_one + scan_duplicates（与 scan_files_duplicates 同一路径），只读。"""
import sys
sys.dont_write_bytecode = True
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parents[1]
sys.path.insert(0, str(C))
import exam_register as er  # noqa: E402

BANK = er.REPO_ROOT / 'DeepSeek_政治题库资料库_20260918'
RAW = er.REPO_ROOT / '00_共同资料' / '原材料'
index = er.BankIndex(BANK)
index.ensure_all()
rows = er.read_csv_rows(BANK / 'indexes' / 'exam_files.csv')
out = []
for r in rows:
    if r.get('format', '').lower() not in ('pdf', 'docx') or not r['exam_id'].startswith('BJ-'):
        continue
    p = er.resolve_raw_path(r['rel_path'], RAW)
    if p is None:
        continue
    try:
        qs, reliable = er.split_and_fingerprint_one({'path': p})
    except Exception as e:
        out.append({'exam_id': r['exam_id'], 'rel': r['rel_path'], 'err': repr(e)})
        continue
    if not qs:
        continue
    against = er.scan_duplicates(index, '__NEW__', qs, exclude_exam=None, fraction_reliable=reliable,
                                 total_questions=len(qs))
    rec = {'exam_id': r['exam_id'], 'role': r['role'], 'rel': r['rel_path'], 'fp_chunks': len(qs), 'reliable': reliable,
           'hits': [(a['exam_id'], a['kind'], a['matched_questions'], a['total_questions'], a['fraction_reliable'])
                    for a in against if a['kind'] != 'needs_verification_low_confidence']}
    out.append(rec)
    other_dup = [h for h in rec['hits'] if h[1] == 'duplicate_registration' and h[0] != r['exam_id']]
    if other_dup or r['role'] not in er.ROLE_PRIORITY:
        print(r['exam_id'], r['role'], Path(r['rel_path']).name[:40], 'fp', len(qs), 'rel', reliable, rec['hits'][:4], flush=True)
Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
