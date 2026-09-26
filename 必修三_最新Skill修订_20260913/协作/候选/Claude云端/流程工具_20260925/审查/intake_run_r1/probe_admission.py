"""对抗探针：intake_run 的“该收清单”= attribution_ruled.csv 里 归属_<码>=='IN' 的全部行，不看 admission 列，也不读
各书清单_v4/<码>_漏收候选.csv 的“类别”（漏收 / 不收-无E1 / 待核证据）。统计 5 张验收卷×7 本书里被 intake_run 当成
该收、但归属表自己标为不收/待核的题。"""
import csv, json, sys
from collections import defaultdict
A = '后勤管理/20260923_脚本化与跨书工具/完整性调查_20260924/归属表_v1/'
rows = list(csv.DictReader(open(A + 'attribution_ruled.csv', encoding='utf-8-sig')))
EX = ['BJ-2023-HD-QIZHONG', 'BJ-2024-HD-QIZHONG', 'BJ-2024-CY-QIZHONG', 'BJ-2026-CY-QIZHONG', 'BJ-2026-HD-QIZHONG']
CODES = {'bixiu3': 'B3', 'philosophy': 'PH', 'culture': 'CU', 'xuanbi1': 'X1', 'xuanbi2': 'X2', 'mind': 'MI', 'reasoning': 'RE'}
lists = {}
for b, c in CODES.items():
    try:
        lists[c] = {r['unit_id']: r for r in csv.DictReader(open(A + f'各书清单_v4/{c}_漏收候选.csv', encoding='utf-8-sig'))}
    except FileNotFoundError:
        lists[c] = {}
out = defaultdict(list)
for e in EX:
    rs = [r for r in rows if e in (r['exam_id_raw'], r['exam_id_canonical'])]
    for b, c in CODES.items():
        for r in rs:
            if (r['归属_' + c] or '').strip() != 'IN':
                continue
            lr = lists[c].get(r['unit_id'])
            cat = lr['类别'] if lr else '(不在各书清单_v4漏收候选)'
            if r['admission'].startswith('不收') or cat != '漏收':
                out[f'{e}×{b}'].append({'unit_id': r['unit_id'], 'admission(归属表)': r['admission'], '类别(各书清单_v4)': cat})
tot = sum(len(v) for v in out.values())
print('intake_run 当成“该收”但归属表/各书清单标为非“漏收”的 (卷×书) 行数：', tot)
for k, v in out.items():
    print(k, json.dumps(v, ensure_ascii=False))
