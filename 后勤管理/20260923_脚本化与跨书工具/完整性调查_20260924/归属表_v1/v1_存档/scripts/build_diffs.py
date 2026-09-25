#!/usr/bin/env python3
"""build_diffs.py —— 逐书差集（缺口3）。只读 attribution.csv，零模型token。

漏收候选（本册） = 归属_<模块> ∈ {IN, MAYBE}（即“本册相关但书稿未收”；不含 OUT，含待裁决——
                    因为09-24裁定只影响“收不收”，不影响“是否本册相关”，缺证据不能让题从候选里消失）。
错收候选（本册） = 归属_<模块> == COLLECTED 且该模块出现在 conflict_script_out
                    （脚本独立信号判 OUT、但书稿已收——疑似错收，需人工复核，不是自动判定为错）。

每书一份 CSV + summary.csv 汇总各类数量。
"""
import sys
sys.dont_write_bytecode = True
import argparse, csv
from pathlib import Path
from collections import defaultdict

MODS = ['B2', 'B3', 'PH', 'CU', 'X1', 'X2', 'MI', 'RE']  # B1 无书，不参与逐书差集
BOOK_NAME = {'B2': '必修二', 'B3': '必修三', 'PH': '哲学', 'CU': '文化',
             'X1': '选必一', 'X2': '选必二', 'MI': '思维', 'RE': '推理'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attribution', default='attribution.csv')
    ap.add_argument('--out-dir', default='diffs')
    a = ap.parse_args()
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(a.attribution, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))

    summary = []
    for m in MODS:
        col = '归属_' + m
        missing, extra = [], []
        for r in rows:
            v = r[col]
            if v in ('IN', 'MAYBE'):
                missing.append(r)
            elif v == 'COLLECTED' and m in (r.get('conflict_script_out') or '').split(';'):
                extra.append(r)
        fields = ['unit_id', 'qid', 'exam_id_canonical', 'num', 'type', 'subq', 'grain',
                  col, 'admission', 'evidence', 'downgrade_notes', 'script_tier', 'rule_version']
        with open(out_dir / f'{m}_missing_candidates.csv', 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            w.writeheader()
            w.writerows(missing)
        fields2 = ['unit_id', 'qid', 'exam_id_canonical', 'num', 'type', 'subq', 'grain',
                   col, 'conflict_script_out', 'admission', 'evidence', 'script_tier', 'rule_version']
        with open(out_dir / f'{m}_extra_candidates.csv', 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields2, extrasaction='ignore')
            w.writeheader()
            w.writerows(extra)
        n_in = sum(1 for r in missing if r[col] == 'IN')
        n_maybe = len(missing) - n_in
        n_admit = sum(1 for r in missing if not r['admission'].startswith('不收'))
        n_not_admit = len(missing) - n_admit
        summary.append({
            'book': BOOK_NAME[m], 'module': m,
            '漏收候选_合计': len(missing), '漏收候选_IN': n_in, '漏收候选_MAYBE待裁决': n_maybe,
            '漏收候选_按裁定应收': n_admit, '漏收候选_按裁定应不收(仅选择题会真正照收)': n_not_admit,
            '错收候选_合计(疑似,需复核)': len(extra),
        })

    with open(out_dir / 'summary.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)

    for s in summary:
        print(s['book'], s)


if __name__ == '__main__':
    main()
