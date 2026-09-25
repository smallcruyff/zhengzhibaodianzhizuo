#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段7：资产抽取 + 来源映射 + 索引汇总。

产出：
  assets/{source_id}/pages/pNNN.png     含图表页的整页/局部图（硬链接，不重复占空间）
  assets/{source_id}/embedded/img*.png  PDF 内嵌位图（pdfimages 抽取）
  assets/{source_id}/figures.jsonl      该来源的图表对象与资产映射
  indexes/assets.csv
  indexes/source_map.jsonl              逐内容块可追溯映射
  indexes/exams.csv                     回填题量统计
"""
import csv
import json
import os
import re
import shutil
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P


def link_or_copy(src, dst):
    try:
        if os.path.isfile(dst):
            return True
        os.link(src, dst)
        return True
    except Exception:
        try:
            shutil.copy2(src, dst)
            return True
        except Exception:
            return False


def main():
    with open(os.path.join(P.INDEX_DIR, "source_manifest.csv"), "r", encoding="utf-8") as fh:
        man = [r for r in csv.DictReader(fh)]
    with open(os.path.join(P.INDEX_DIR, "exam_files.csv"), "r", encoding="utf-8") as fh:
        ef = [r for r in csv.DictReader(fh)]

    assets = []
    smap = []
    for r in man:
        if r["in_scope"] != "Y":
            continue
        sid = r["source_id"]
        d = os.path.join(P.EVID_DIR, sid)
        if not os.path.isdir(d):
            continue
        adir = os.path.join(P.ASSET_DIR, sid)
        meta = {}
        mp = os.path.join(d, "meta.json")
        if os.path.isfile(mp):
            try:
                meta = json.load(open(mp, encoding="utf-8"))
            except Exception:
                pass

        fig_objs = []
        fp = os.path.join(d, "figure_objects.jsonl")
        if os.path.isfile(fp):
            for ln in open(fp, encoding="utf-8"):
                try:
                    fig_objs.append(json.loads(ln))
                except Exception:
                    pass

        # 1. 含图表页的整页图 -> assets（硬链接）
        need_pages = sorted(set(f.get("page") or f.get("slide") for f in fig_objs if f.get("page") or f.get("slide")))
        made_pages = 0
        for pg in need_pages:
            src = os.path.join(d, "pages", "p%03d.png" % pg)
            if os.path.isfile(src):
                P.ensure_dirs(os.path.join(adir, "pages"))
                if link_or_copy(src, os.path.join(adir, "pages", "p%03d.png" % pg)):
                    made_pages += 1
                    assets.append({"asset_id": "%s-p%03d" % (sid, pg), "source_id": sid,
                                   "kind": "page_render", "page": pg,
                                   "path": os.path.relpath(os.path.join(adir, "pages", "p%03d.png" % pg), P.OUT_ROOT),
                                   "note": "含图表/扫描内容的整页图，供显式打开核验"})

        # 2. PDF 内嵌位图 -> assets（pdfimages）
        made_emb = 0
        if r["format"] == "pdf" and fig_objs:
            embdir = os.path.join(adir, "embedded")
            P.ensure_dirs(embdir)
            rc, out, err = P.run([P.PDFIMAGES, "-png", r["original_path"], os.path.join(embdir, "img")],
                                 timeout=600)
            if os.path.isdir(embdir):
                for f in sorted(os.listdir(embdir)):
                    if f.lower().endswith(".png"):
                        made_emb += 1
                        assets.append({"asset_id": "%s-%s" % (sid, os.path.splitext(f)[0]),
                                       "source_id": sid, "kind": "embedded_image", "page": "",
                                       "path": os.path.relpath(os.path.join(embdir, f), P.OUT_ROOT),
                                       "note": "PDF 内嵌位图（矢量线条/组合图形不在此列，须看整页图）"})
        # 3. figures.jsonl 合并
        if fig_objs:
            P.ensure_dirs(adir)
            with open(os.path.join(adir, "figures.jsonl"), "w", encoding="utf-8") as fh:
                for f in fig_objs:
                    fh.write(json.dumps(f, ensure_ascii=False) + "\n")

        # 4. 来源映射（逐内容块）
        anchor = "%s.full.md" % sid
        pages_jsonl = os.path.join(d, "native_text", "pages.jsonl")
        if os.path.isfile(pages_jsonl):
            for ln in open(pages_jsonl, encoding="utf-8"):
                try:
                    pg = json.loads(ln)
                except Exception:
                    continue
                smap.append({
                    "source_id": sid, "sha256": r["sha256"],
                    "locator_type": "pdf_page", "locator": pg["page"],
                    "page_class": pg.get("class"), "chars": pg.get("chars"),
                    "md_path": "processed_markdown/" + anchor,
                    "md_anchor": "#第-%d-页" % pg["page"],
                    "question_id": "", "extract_method": (
                        "native_text" if pg.get("class") == "text" else
                        "native_text+visual" if pg.get("class") == "mixed" else "visual_only"),
                    "render": pg.get("render", ""), "render_reason": pg.get("render_reason", ""),
                    "verify_status": "pending",
                })
        slides_jsonl = os.path.join(d, "native_text", "slides.jsonl")
        if os.path.isfile(slides_jsonl):
            for ln in open(slides_jsonl, encoding="utf-8"):
                try:
                    s = json.loads(ln)
                except Exception:
                    continue
                smap.append({
                    "source_id": sid, "sha256": r["sha256"],
                    "locator_type": "pptx_slide", "locator": s["slide"],
                    "hidden": s.get("hidden"), "shapes": s.get("shape_count"),
                    "has_notes": bool((s.get("notes") or "").strip()),
                    "md_path": "processed_markdown/" + anchor,
                    "md_anchor": "#第-%d-张" % s["slide"],
                    "question_id": "", "extract_method": "pptx_shape_text",
                    "verify_status": "pending",
                })
        parts_jsonl = os.path.join(d, "native_text", "parts.jsonl")
        if os.path.isfile(parts_jsonl):
            for ln in open(parts_jsonl, encoding="utf-8"):
                try:
                    pt = json.loads(ln)
                except Exception:
                    continue
                smap.append({
                    "source_id": sid, "sha256": r["sha256"],
                    "locator_type": "docx_" + pt.get("type", "block"),
                    "locator": pt.get("seq"), "table_index": pt.get("table_index", ""),
                    "md_path": "processed_markdown/" + anchor,
                    "md_anchor": "#块-%s" % pt.get("seq"),
                    "question_id": "", "extract_method": "docx_body_order",
                    "verify_status": "pending",
                })

    with open(os.path.join(P.INDEX_DIR, "assets.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["asset_id", "source_id", "kind", "page", "path", "note"])
        w.writeheader()
        for a in assets:
            w.writerow(a)
    with open(os.path.join(P.INDEX_DIR, "source_map.jsonl"), "w", encoding="utf-8") as fh:
        for s in smap:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")

    # 回填 exams.csv 题量
    qc = defaultdict(lambda: [0, 0, 0])
    if os.path.isfile(os.path.join(P.INDEX_DIR, "questions.csv")):
        with open(os.path.join(P.INDEX_DIR, "questions.csv"), "r", encoding="utf-8") as fh:
            for q in csv.DictReader(fh):
                qc[q["exam_id"]][0] += 1
                if q["type"] == "选择题":
                    qc[q["exam_id"]][1] += 1
                else:
                    qc[q["exam_id"]][2] += 1
    rows = []
    with open(os.path.join(P.INDEX_DIR, "exams.csv"), "r", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        cols = rd.fieldnames
        for e in rd:
            c = qc.get(e["exam_id"])
            if c:
                e["question_count"] = c[0]
                e["subq_count"] = c[2]
            rows.append(e)
    with open(os.path.join(P.INDEX_DIR, "exams.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for e in rows:
            w.writerow(e)

    print("assets:", len(assets))
    print("source_map 条目:", len(smap))
    print("回填 exams:", len(rows))


if __name__ == "__main__":
    main()
