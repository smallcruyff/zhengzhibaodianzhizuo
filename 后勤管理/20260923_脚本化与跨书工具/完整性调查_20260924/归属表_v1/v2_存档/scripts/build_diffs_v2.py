#!/usr/bin/env python3
"""build_diffs_v2.py —— 逐书差集（缺口3）v2。只读 attribution.csv，零模型token。

相对 v1 的关键变更（对应 审查意见.json blocker②、major④）：
  1. OUT 不再被直接剔除出差集。脚本判 OUT 的 (单元,模块) 组合单列一层
     "<MOD>_out_lowprior_candidates.csv"（“OUT-低先验”），仍然是候选，只是先验概率脚本认为较低；
     在没有分层金标集测出漏收率≤1%之前，不能把 OUT 当“已确认非本模块”直接丢弃。
  2. major④指出"错收候选只来自conflict_script_out，一共80对，COLLECTED模块的其余单元从未被复判"。
     build_diffs.py本身只是把 conflict_script_out 字段翻译成一张表，不能凭空制造 classify.py 没算出的
     冲突；本版仍原样保留这一层（作为"脚本已发现的疑似错收"下限），真正的修复是
     prep_model_batch_v2.py 把全部 COLLECTED 模块单元（不再局限于这80对）都排进模型复判队列——
     错收候选的完整定义（书稿收录－模型或人工判定的相关集合）需要那一步的复判结果才能算出，
     不是 build_diffs 这一步能单独解决的，README 对此已如实标注，不在这里假装解决。
  3. 输出 fields 增加 evidence_detail，方便人工复核时不用回查 rubric_links.csv 原始行。
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

    summary = []
    for m in MODS:
        col = '归属_' + m
        missing, extra, out_low = [], [], []
        for r in rows:
            v = r[col]
            if v in ('IN', 'MAYBE'):
                missing.append(r)
            elif v == 'OUT':
                out_low.append(r)
            if v == 'COLLECTED':
                conflict_field = m in (r.get('conflict_script_out') or '').split(';')
                if conflict_field:
                    extra.append(r)
        fields = ['unit_id', 'qid', 'exam_id_canonical', 'num', 'type', 'subq', 'grain',
                  col, 'admission', 'evidence', 'evidence_detail', 'downgrade_notes', 'script_tier', 'rule_version']
        with open(out_dir / f'{m}_missing_candidates.csv', 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            w.writeheader()
            w.writerows(missing)
        fields2 = ['unit_id', 'qid', 'exam_id_canonical', 'num', 'type', 'subq', 'grain',
                   col, 'conflict_script_out', 'admission', 'evidence', 'evidence_detail', 'script_tier', 'rule_version']
        with open(out_dir / f'{m}_extra_candidates.csv', 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields2, extrasaction='ignore')
            w.writeheader()
            w.writerows(extra)
        fields3 = ['unit_id', 'qid', 'exam_id_canonical', 'num', 'type', 'subq', 'grain',
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
            '漏收候选_合计(IN+MAYBE不含OUT)': len(missing), '漏收候选_IN': n_in, '漏收候选_MAYBE待模型': n_maybe,
            '漏收候选_按裁定可收(非不收)': n_admit,
            '漏收候选_按裁定不收(选择题外主观题无E1)': n_not_admit,
            '错收候选_合计(疑似,需复核,COLLECTED且脚本判OUT)': len(extra),
            'OUT低先验_合计(未剔除,单列候选,金标集验证前不得当已确认非本模块)': len(out_low),
        })

    with open(out_dir / 'summary.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)

    for s in summary:
        print(s['book'], s)


if __name__ == '__main__':
    main()
