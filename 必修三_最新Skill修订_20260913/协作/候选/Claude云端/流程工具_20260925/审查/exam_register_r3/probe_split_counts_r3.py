#!/usr/bin/env python3
"""r3 探针：--files 模式对题库在册卷原件的切题块数 vs 题库题数（只读）。块数远少于题数、但 split_ok=True
的原件，在“新卷复用少数题”时会因分母过小把复用判成 duplicate_registration（fraction_reliable=True）。"""
import sys, csv, json
sys.dont_write_bytecode = True
from pathlib import Path
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import exam_register as er  # noqa
bank = er.REPO_ROOT / 'DeepSeek_政治题库资料库_20260918'
raw = er.REPO_ROOT / '00_共同资料' / '原材料'
rows = er.read_csv_rows(bank / 'indexes' / 'exam_files.csv')
res = []
for eid in er.bank_exam_ids(bank):
    rfs = er.locate_raw_files_by_csv(eid, rows, raw)
    nq = len(list((bank / 'questions' / eid).glob(f'{eid}-Q*.md')))
    for rf in rfs[:1]:
        qs, ok = er.split_and_fingerprint_files([rf])
        res.append((eid, nq, len(qs), ok, Path(rf['path']).name))
bad = [r for r in res if r[3] and r[2] < 0.5 * r[1]]
for r in res:
    print(*r)
print('split_ok 但块数 < 题数一半：', len(bad), [b[0] for b in bad])
