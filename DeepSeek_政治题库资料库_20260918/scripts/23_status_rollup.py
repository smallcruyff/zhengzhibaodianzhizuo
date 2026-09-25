#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D 阶段汇总：视觉核验覆盖率（续修 2026-09-21 修订）。

原版缺陷：
  - 分母用工作单**行数**(1781)，与唯一页(1748)混用；
  - 只统计 reviewed，不区分"打开过"与"页内问题已修"；
  - 与 15/16/PROGRESS/checkpoint 各算一套，导致 33/34/42 页三套数字并存。

现改为**只调用** scripts/30_unique_rollup.py 的唯一汇总函数，
所有下游文档从同一口径取数，不再各算一套。

视觉核验的唯一真相源仍是 evidence/{sid}/visual_review.jsonl。
questions.csv 的 extraction_status 不由本脚本改写（避免虚假已核验标记）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P
import importlib

ur = importlib.import_module("30_unique_rollup")


def main():
    summary, _sets = ur.compute()
    out = {
        "total_pages_in_worklist": summary["工作单唯一页"],
        "worklist_rows": summary["工作单行数"],
        "reviewed_pages": summary["opened_实际打开过"],
        "reviewed_pages_strong_evidence": summary["opened_强证据_实际打开具体文件或写下内容发现"],
        "reviewed_pages_weak_evidence": summary["opened_弱证据_仅有脚本默认字段"],
        "remaining_pages": summary["未打开页"],
        "percent": summary["覆盖率_实际打开过"],
        "pages_with_corrected_text": summary["corrected_文本已修"],
        "pages_with_open_findings": summary["findings_open_存在未修问题"],
        "pages_packet_deps_verified": summary["packet_deps_verified_题包依赖全部核完"],
        "pages_rubric_pending": summary["rubric_pending_评分关系待审"],
        "口径": summary["口径"],
        "唯一汇总源": "validation/续修_20260921/唯一汇总.json",
    }
    with open(os.path.join(P.VAL_DIR, "10_视觉核验汇总.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    # 同步刷新 视觉核验进度.json，避免与 24 各写一套（原版此处会保留旧 reviewed_pages）
    prog = os.path.join(P.VAL_DIR, "视觉核验进度.json")
    cur = {
        "updated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "口径": out["口径"],
        "total_pages": summary["工作单唯一页"],
        "worklist_rows": summary["工作单行数"],
        "completed_pages": summary["opened_实际打开过"],
        "completed_pages_strong_evidence": summary["opened_强证据_实际打开具体文件或写下内容发现"],
        "completed_pages_weak_evidence": summary["opened_弱证据_仅有脚本默认字段"],
        "pending_pages": summary["未打开页"],
        "percent": summary["覆盖率_实际打开过"],
        "findings_open_pages": summary["findings_open_存在未修问题"],
        "corrected_pages": summary["corrected_文本已修"],
        "rubric_pending_pages": summary["rubric_pending_评分关系待审"],
        "唯一汇总源": "validation/续修_20260921/唯一汇总.json",
    }
    with open(prog, "w", encoding="utf-8") as fh:
        json.dump(cur, fh, ensure_ascii=False, indent=2)

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
