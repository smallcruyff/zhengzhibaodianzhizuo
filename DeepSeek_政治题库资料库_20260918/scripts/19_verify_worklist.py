#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A2：生成视觉核验工作单。

把"要核验哪些页"和"每页承载哪些题"绑定起来，便于分批逐页打开对照。

字段：
  batch_no, source_id, rel_path, role, page, render, ocr_page, native_page,
  figure_objects, page_is_scan, carries（该页承载的 question_id 列表）

切批：按来源文件聚簇（同一文件的页相邻，便于连续阅读），每批约 25 页。
"""
import csv
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

BATCH = 25


def load_lines_for(sid, variant):
    for cand in (os.path.join(P.EVID_DIR, sid, "cleaned", "clean.md"),
                 os.path.join(P.EVID_DIR, sid, "native_text", "raw.md"),
                 os.path.join(P.EVID_DIR, sid, "native_text", "raw.txt")):
        if os.path.isfile(cand):
            return cand
    return None


def main():
    rows = [json.loads(l) for l in open(
        os.path.join(P.VAL_DIR, "视觉核验任务清单.jsonl"), encoding="utf-8")]
    qs = list(csv.DictReader(open(os.path.join(P.INDEX_DIR, "questions.csv"),
                                  encoding="utf-8")))

    # 把每道题映射到它所在页：OCR 变体按 <<<OCR pNNN.ocr.txt>>> 分段定位
    page_of = defaultdict(set)          # (sid,qid) -> set(page)
    bysrc = defaultdict(list)
    for q in qs:
        bysrc[(q["source_id"], q["variant"])].append(q)
    for (sid, var), qlist in bysrc.items():
        vd = os.path.join(P.EVID_DIR, sid, "visual_transcript")
        fs = sorted(f for f in os.listdir(vd) if f.endswith(".ocr.txt")) \
            if os.path.isdir(vd) else []
        marks = []
        for f in fs:
            n = len(open(os.path.join(vd, f), encoding="utf-8", errors="replace")
                    .read().splitlines())
            marks.append((int(f[1:4]), n))
        if not marks:
            continue
        for q in qlist:
            if var != "ocr_candidate":
                continue
            try:
                s0, s1 = (int(x) for x in q["line_range"].split("-"))
            except Exception:
                continue
            acc, pages = 0, set()
            for pg, n in marks:
                if acc + n <= s0:
                    acc += n
                    continue
                if acc >= s1:
                    break
                pages.add(pg)
                acc += n
            if pages:
                page_of[(sid, q["question_id"])] |= pages

    # 也把 native 题按来源粗略挂到"该来源需要核验的页"上，避免漏题
    native_by_src = defaultdict(set)
    for q in qs:
        if q["variant"] == "native":
            native_by_src[q["source_id"]].add(q["question_id"])

    out = []
    for r in rows:
        sid, pg = r["source_id"], r["page"]
        carries = sorted(qid for (s, qid), ps in page_of.items()
                         if s == sid and pg in ps)
        ocr_page = "evidence/%s/visual_transcript/p%03d.ocr.txt" % (sid, pg)
        if not os.path.isfile(os.path.join(P.OUT_ROOT, ocr_page)):
            ocr_page = ""
        out.append({
            "source_id": sid, "rel_path": r["rel_path"], "role": r.get("role", ""),
            "page": pg, "render": r["render"], "ocr_page": ocr_page,
            "figure_objects": r["figure_objects"], "page_is_scan": r["page_is_scan"],
            "carries": carries,
        })
    # 同一文件的页相邻；文件内按页序
    out.sort(key=lambda x: (x["source_id"], x["page"]))

    bn, cnt = 0, 0
    for x in out:
        if cnt % BATCH == 0:
            bn += 1
        x["batch_no"] = bn
        cnt += 1
    # 批号移到最前（写文件时保持字段顺序）
    ordered = [{k: x[k] for k in ("batch_no", "source_id", "rel_path", "role", "page",
                                  "render", "ocr_page", "figure_objects",
                                  "page_is_scan", "carries")} for x in out]

    with open(os.path.join(P.VAL_DIR, "视觉核验工作单.jsonl"), "w",
              encoding="utf-8") as fh:
        for x in ordered:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    nb = max(x["batch_no"] for x in ordered)
    with open(os.path.join(P.VAL_DIR, "视觉核验进度.json"), "w", encoding="utf-8") as fh:
        json.dump({"total_pages": len(ordered), "reviewed_pages": 0,
                   "total_batches": nb, "current_batch": 1,
                   "note": "reviewed_pages 由实际打开原页并写入 visual_review.jsonl 后累加；"
                           "只跑 OCR 或有截图不计入"}, fh, ensure_ascii=False, indent=2)
    print("工作单页数:", len(ordered), " 批数:", nb)
    print("承载题的页:", sum(1 for x in ordered if x["carries"]))
    print("纯扫描页:", sum(1 for x in ordered if x["page_is_scan"]))
    print("缺渲染图:", sum(1 for x in ordered
                          if not os.path.isfile(os.path.join(P.OUT_ROOT, x["render"]))))


if __name__ == "__main__":
    main()
