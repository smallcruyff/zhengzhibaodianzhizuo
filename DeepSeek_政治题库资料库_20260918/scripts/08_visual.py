#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段3b：扫描页 / 图表页的视觉转写（OCR 为候选层）。

规范四.1 + 约束2：
  - OCR 输出属于**候选转写**，不得直接标记为已完成视觉核验
  - 需要视觉核验的对象，必须实际打开对应页面或局部图片进行对照
  - 只运行 OCR 或只生成截图，不能标记为已完成视觉核验

本脚本只负责"生成候选 OCR + 生成待核验任务清单"。
实际对照由模型读取 pages/*.png 完成，结果写入
  evidence/{sid}/visual_review.jsonl   （每页一条：看过/方法/发现的问题）
"""
import argparse
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P


def ocr_page(png, outdir, langs="zh-Hans,en-US", scale="3.0"):
    P.ensure_dirs(outdir)
    t0 = time.time()
    rc, out, err = P.run([P.OCR_VISION, "--out", outdir, "--langs", langs,
                          "--scale", scale, png], timeout=300)
    txt = ""
    base = os.path.splitext(os.path.basename(png))[0] + ".ocr.txt"
    fp = os.path.join(outdir, base)
    if os.path.isfile(fp):
        with open(fp, "r", encoding="utf-8", errors="replace") as fh:
            txt = fh.read()
    return {"rc": rc, "seconds": round(time.time() - t0, 2), "chars": len(txt),
            "out": fp, "stderr": err[:200]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only-year", default="")
    a = ap.parse_args()

    with open(os.path.join(P.INDEX_DIR, "source_manifest.csv"), "r", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["in_scope"] == "Y"]
    if a.source:
        rows = [r for r in rows if r["source_id"] == a.source]
    if a.only_year:
        rows = [r for r in rows if r["rel_path"].startswith(a.only_year)]
    if a.limit:
        rows = rows[:a.limit]

    total_pages = 0
    for i, r in enumerate(rows, 1):
        sid = r["source_id"]
        d = os.path.join(P.EVID_DIR, sid)
        mp = os.path.join(d, "meta.json")
        if not os.path.isfile(mp):
            continue
        meta = json.load(open(mp, encoding="utf-8"))
        pages = meta.get("needs_visual_check") or []
        if not pages:
            continue
        vt = os.path.join(d, "visual_transcript")
        tasks = []
        for pg in pages:
            png = os.path.join(d, "pages", "p%03d.png" % pg)
            if not os.path.isfile(png):
                tasks.append({"page": pg, "status": "no_render", "reason": "未渲染，无法视觉核验"})
                continue
            res = ocr_page(png, vt)
            total_pages += 1
            tasks.append({"page": pg, "status": "ocr_candidate", "ocr": res,
                          "png": os.path.relpath(png, P.OUT_ROOT),
                          "review_status": "pending",
                          "review_method": "",
                          "issues_found": []})
        with open(os.path.join(d, "visual_tasks.jsonl"), "w", encoding="utf-8") as fh:
            for t in tasks:
                fh.write(json.dumps(t, ensure_ascii=False) + "\n")
        # 更新 manifest 处理状态
        print("[%d/%d] %s pages=%d ocr=%d" % (i, len(rows), sid, len(pages),
                                              sum(1 for t in tasks if t["status"] == "ocr_candidate")))
    print("OCR pages total:", total_pages)


if __name__ == "__main__":
    main()
