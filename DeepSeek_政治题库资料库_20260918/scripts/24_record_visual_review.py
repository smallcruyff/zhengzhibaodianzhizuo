#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B 阶段通用工具：从 JSON 追加视觉核验记录，并更新进度。

续修 2026-09-21 修订（原版缺陷）：
  1. 原版**无条件**写 `review_status="reviewed"`，只要脚本跑过就算"已看"，
     默认值构成虚假证据。现改为：必须提供真实查看证据才写 reviewed；
     无证据的条目写 `review_status="recorded_without_view_evidence"`，不计入已核验。
  2. 原版分母用工作单**行数**(1781)，与 23 的唯一页口径(1748)不一致。
     现统一按 (source_id, page) 去重。
  3. 原版保留旧 `reviewed_pages` 字段造成多口径并存。现只从实际记录现算，
     不再沿用旧值。
  4. `method` 的默认串是脚本默认值，本身不构成证据；只有
     `viewed_file`/`viewed_files`/`opened_artifact` 或内容相关的
     `findings`/`issues_found`/`corrected_text`/`affected_questions` 才算。

用法：
  1. 把本批核验结论写到 records.json（每条含 source_id, page，
     以及 viewed_file 或 findings 等真实查看证据）
  2. /usr/bin/python3 24_record_visual_review.py records.json
     [--allow-unverified]   # 明确允许登记无证据条目（默认拒绝，需显式给出）
"""
import argparse
import datetime
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

VIEW_EVIDENCE_FIELDS = ("viewed_file", "viewed_files", "opened_artifact")
CONTENT_EVIDENCE_FIELDS = ("findings", "issues_found", "corrected_text",
                           "affected_questions", "action")


def has_view_evidence(r):
    """是否存在真实查看动作的证据（脚本默认值不算）。"""
    for k in VIEW_EVIDENCE_FIELDS:
        v = r.get(k)
        if v:
            return True, "opened_artifact"
    for k in CONTENT_EVIDENCE_FIELDS:
        v = r.get(k)
        if v:
            return True, "content_findings"
    return False, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("records")
    ap.add_argument("--allow-unverified", action="store_true",
                    help="允许登记无查看证据的条目（会写成 recorded_without_view_evidence）")
    a = ap.parse_args()

    recs_in = json.load(open(a.records, encoding="utf-8"))
    if isinstance(recs_in, dict):
        recs_in = [recs_in]
    now = datetime.datetime.now().isoformat(timespec="seconds")

    accepted, rejected = [], []
    for r in recs_in:
        ok, why = has_view_evidence(r)
        r = dict(r)
        r.setdefault("reviewed_at", now)
        if ok:
            r["review_status"] = "reviewed"
            r["view_evidence"] = why
            accepted.append(r)
        else:
            r["review_status"] = "recorded_without_view_evidence"
            r["view_evidence"] = None
            rejected.append(r)

    by_sid = {}
    for r in accepted + (rejected if a.allow_unverified else []):
        by_sid.setdefault(r["source_id"], []).append(r)

    if rejected and not a.allow_unverified:
        print("拒绝 %d 条无查看证据的记录（未写入；加 --allow-unverified 才登记）：" % len(rejected))
        for r in rejected[:10]:
            print("  %s p%s" % (r.get("source_id"), r.get("page")))
        if not accepted:
            return 2

    for sid, recs in by_sid.items():
        evf = os.path.join(P.EVID_DIR, sid, "visual_review.jsonl")
        os.makedirs(os.path.dirname(evf), exist_ok=True)
        with open(evf, "a", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        # verified 文本（只对真正看过且给了改正文本的条目）
        for r in recs:
            corr = r.get("corrected_text")
            if corr and r.get("review_status") == "reviewed":
                vdir = os.path.join(P.EVID_DIR, sid, "visual_transcript", "verified")
                os.makedirs(vdir, exist_ok=True)
                vp = os.path.join(vdir, "p%03d.verified.txt" % r["page"])
                with open(vp, "w", encoding="utf-8") as fh:
                    fh.write(corr)
        print("  %s: 追加 %d 条（reviewed %d）"
              % (sid, len(recs), sum(1 for x in recs if x["review_status"] == "reviewed")))

    # 进度：统一从 30_unique_rollup 的现算结果取，分母按 (source_id,page) 去重
    sys.path.insert(0, P.SCRIPT_DIR)
    import importlib
    ur = importlib.import_module("30_unique_rollup")
    summary, _sets = ur.compute()
    prog = os.path.join(P.VAL_DIR, "视觉核验进度.json")
    cur = {
        "updated_at": now,
        "口径": "分母=工作单按(source_id,page)去重的唯一页；reviewed 需有真实查看证据",
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
    }
    json.dump(cur, open(prog, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("进度: 已核 %d/%d (%.2f%%) 未核 %d"
          % (cur["completed_pages"], cur["total_pages"], cur["percent"], cur["pending_pages"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
