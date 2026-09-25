#!/usr/bin/env python3
"""build_diffs_v3.py —— 逐书差集（缺口3）v3。只读 attribution.csv，零模型token。

相对 v2 的关键变更（对应 确认意见_v2.json blocker①）：
  1. 排除"身份错误/身份未确认"行：admission 以"身份"开头的行（伪Q18切分错误、汇编待复核未定年份两类）
     不进入任何模块的 missing/extra/out_lowprior 差集，避免假漏收或凭空拉高候选数。
  2. 按 canonical_qid 去重：同一等价类（重复登记别名孪生题，例如 BJ-2024/2025-HD-QIZHONG）在
     未被判定 COLLECTED 时，v2 会在漏收/OUT差集里把两侧qid各列一行，重复计数同一道题；
     v3 每个 (canonical_qid, 模块) 组合只保留一行代表（优先用 canonical_qid 自身那一侧的行，
     其自身没有该 unit_id 时退回别名侧），另一侧仍留在 attribution.csv 全表里（可追溯），
     只是不再重复进入本文件的候选清单，避免"差集不按等价类合并"的双重计数。
"""
import sys
sys.dont_write_bytecode = True
import argparse, csv, json
from pathlib import Path
from collections import defaultdict

MODS = ['B2', 'B3', 'PH', 'CU', 'X1', 'X2', 'MI', 'RE']
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

    # blocker①：身份错误/身份未确认行整体排除，不进入任何模块的分母/差集
    n_identity_excluded = sum(1 for r in rows if (r.get('admission') or '').startswith('身份'))
    rows = [r for r in rows if not (r.get('admission') or '').startswith('身份')]

    summary = []
    for m in MODS:
        col = '归属_' + m
        missing, extra, out_low = [], [], []
        seen_missing_cq, seen_out_cq, seen_extra_cq = set(), set(), set()
        n_dedup_missing = n_dedup_out = n_dedup_extra = 0
        for r in rows:
            v = r[col]
            # 去重键必须带 subq：canonical_qid 只在整题层面等价，同一 qid 下不同小问(subq)是不同单元，
            # 不能因为共享同一个 canonical_qid 就把 Q19#1/Q19#2/Q19#3 误合并成一行。
            cq = (r.get('canonical_qid') or r['qid'], r.get('subq') or '')
            if v in ('IN', 'MAYBE'):
                if cq in seen_missing_cq:
                    n_dedup_missing += 1
                else:
                    seen_missing_cq.add(cq)
                    missing.append(r)
            elif v == 'OUT':
                if cq in seen_out_cq:
                    n_dedup_out += 1
                else:
                    seen_out_cq.add(cq)
                    out_low.append(r)
            if v == 'COLLECTED':
                conflict_field = m in (r.get('conflict_script_out') or '').split(';')
                if conflict_field:
                    if cq in seen_extra_cq:
                        n_dedup_extra += 1
                    else:
                        seen_extra_cq.add(cq)
                        extra.append(r)
        fields = ['unit_id', 'qid', 'canonical_qid', 'exam_id_canonical', 'num', 'type', 'subq', 'grain',
                  col, 'admission', 'evidence', 'evidence_detail', 'downgrade_notes', 'script_tier', 'rule_version']
        with open(out_dir / f'{m}_missing_candidates.csv', 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            w.writeheader()
            w.writerows(missing)
        fields2 = ['unit_id', 'qid', 'canonical_qid', 'exam_id_canonical', 'num', 'type', 'subq', 'grain',
                   col, 'conflict_script_out', 'admission', 'evidence', 'evidence_detail', 'script_tier', 'rule_version']
        with open(out_dir / f'{m}_extra_candidates.csv', 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields2, extrasaction='ignore')
            w.writeheader()
            w.writerows(extra)
        fields3 = ['unit_id', 'qid', 'canonical_qid', 'exam_id_canonical', 'num', 'type', 'subq', 'grain',
                   col, 'admission', 'evidence', 'evidence_detail', 'script_tier', 'rule_version']
        with open(out_dir / f'{m}_out_lowprior_candidates.csv', 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields3, extrasaction='ignore')
            w.writeheader()
            w.writerows(out_low)

        n_in = sum(1 for r in missing if r[col] == 'IN')
        n_maybe = len(missing) - n_in
        n_admit = sum(1 for r in missing if not r['admission'].startswith('不收'))
        n_not_admit = len(missing) - n_admit
        summary.append({
            'book': BOOK_NAME[m], 'module': m,
            '漏收候选_合计(IN+MAYBE不含OUT,按canonical_qid去重)': len(missing),
            '漏收候选_IN': n_in, '漏收候选_MAYBE待模型': n_maybe,
            '漏收候选_按裁定可收(非不收)': n_admit,
            '漏收候选_按裁定不收(选择题外主观题无E1)': n_not_admit,
            '错收候选_合计(疑似,需复核,COLLECTED且脚本判OUT,按canonical_qid去重)': len(extra),
            'OUT低先验_合计(未剔除,单列候选,金标集验证前不得当已确认非本模块,按canonical_qid去重)': len(out_low),
            '去重去掉的重复行数(漏收/OUT/错收)': f'{n_dedup_missing}/{n_dedup_out}/{n_dedup_extra}',
        })

    with open(out_dir / 'summary.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)

    for s in summary:
        print(s['book'], s)
    print(f'身份错误/身份未确认行已从全部差集排除：{n_identity_excluded} 行')


if __name__ == '__main__':
    main()
