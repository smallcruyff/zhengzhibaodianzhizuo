#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段3：PDF 提取（分层留证）。

用法：
  python3 03_extract_pdf.py --batch 2026_bianhao   # 处理某批
  python3 03_extract_pdf.py --source Sxxxxxxxxxxxx # 单个
  python3 03_extract_pdf.py --limit 5              # 只处理前 N 个（校准）

产出（每个 source_id 一份）：
  evidence/{sid}/meta.json                        探针与页面分类
  evidence/{sid}/native_text/raw.txt              pdftotext -layout 原始抽取（不可覆盖）
  evidence/{sid}/native_text/pages.jsonl          逐页字符数/文本块/bbox/分类
  evidence/{sid}/figure_objects.jsonl             图表对象清单（约束2）
  evidence/{sid}/pages/pNNN.png                   按需渲染页（记录渲染原因）
  processed_markdown/{sid}.full.md                文档级主档（当前=原始抽取，清洗阶段另存 cleaned）

约束2：字符密度只用于选路径；图表对象清单独立于文字密度生成。
"""
import argparse
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

# 文字密度分流阈值（仅用于选择提取路径，不用于跳过图表检查）
T_TEXT = 500
T_MIXED = 100

# 渲染条件（约束2：图表对象驱动，而非文字密度驱动）
MIN_DRAWINGS_FOR_RENDER = 12
RENDER_DPI_FIGURE = 300
RENDER_DPI_COVERAGE = 150


def sid_dir(sid):
    d = os.path.join(P.EVID_DIR, sid)
    P.ensure_dirs(d, os.path.join(d, "native_text"), os.path.join(d, "pages"),
                  os.path.join(d, "visual_transcript"), os.path.join(d, "cleaned"))
    return d


def probe(pdf):
    """返回 (pages, page_sizes, encrypted)"""
    rc, out, err = P.run([P.PDFINFO, pdf], timeout=60)
    pages = 0
    for line in out.splitlines():
        if line.startswith("Pages:"):
            try:
                pages = int(line.split(":", 1)[1].strip())
            except Exception:
                pages = 0
    return pages


def pdfimages_list(pdf):
    """返回 {page(1-based): [img...]}"""
    rc, out, err = P.run([P.PDFIMAGES, "-list", pdf], timeout=180)
    by = {}
    if rc != 0:
        return by, err
    for i, line in enumerate(out.splitlines()):
        if i < 2:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            pg = int(parts[0])
        except Exception:
            continue
        try:
            w = int(parts[3]); h = int(parts[4])
        except Exception:
            w = h = 0
        by.setdefault(pg, []).append({"w": w, "h": h, "type": parts[-1] if len(parts) > 5 else "",
                                      "raw": line.strip()})
    return by, ""


def page_texts(pdf, pages):
    """逐页 pdftotext（物理页序 1-based）"""
    res = {}
    for p in range(1, pages + 1):
        rc, out, err = P.run([P.PDFTOTEXT, "-layout", "-f", str(p), "-l", str(p), pdf, "-"], timeout=60)
        res[p] = out if rc == 0 else ""
    return res


def render(pdf, pages_to_render, outdir, dpi, reason_map):
    made = {}
    for p in sorted(pages_to_render):
        base = os.path.join(outdir, "p%03d" % p)
        if os.path.isfile(base + ".png"):
            made[p] = base + ".png"
            continue
        rc, out, err = P.run([P.PDFTOPPM, "-r", str(dpi), "-png", "-f", str(p), "-l", str(p),
                              "-singlefile", pdf, base], timeout=180)
        if os.path.isfile(base + ".png"):
            made[p] = base + ".png"
    return made


def process_one(row):
    sid = row["source_id"]
    pdf = row["original_path"]
    d = sid_dir(sid)
    t0 = time.time()
    rec = {"source_id": sid, "pdf": pdf, "rel_path": row["rel_path"]}

    # --- 1. 探针
    n_pages = probe(pdf)
    rec["pages_pdfinfo"] = n_pages
    if n_pages == 0:
        rec["status"] = "blocked"
        rec["error"] = "pdfinfo 未取到页数"
        return rec

    # --- 2. 逐页文字
    ptxt = page_texts(pdf, n_pages)
    raw_all = []
    page_rows = []
    for p in range(1, n_pages + 1):
        t = ptxt.get(p, "")
        raw_all.append("\n\n<<<PAGE %d>>>\n\n" % p + t)
        n = len(t.strip())
        cls = "text" if n >= T_TEXT else ("mixed" if n >= T_MIXED else "scan_or_empty")
        page_rows.append({"page": p, "chars": n, "class": cls})

    with open(os.path.join(d, "native_text", "raw.txt"), "w", encoding="utf-8") as fh:
        fh.write("".join(raw_all))

    # --- 3. 图表对象清单（约束2：独立于文字密度）
    imgs, ierr = pdfimages_list(pdf)
    fig_rows = []
    draw_count = {}
    try:
        import fitz
        doc = fitz.open(pdf)
        for p in range(n_pages):
            pg = doc[p]
            try:
                dr = pg.get_drawings()
                nd = len(dr)
            except Exception:
                nd = -1
            draw_count[p + 1] = nd
            # 文本块 bbox
            blocks = pg.get_text("blocks")
            page_rows[p]["text_blocks"] = [
                {"bbox": [round(x, 1) for x in b[:4]], "text": (b[4] or "")[:120]}
                for b in blocks if len(b) >= 5 and (b[4] or "").strip()
            ]
            page_rows[p]["page_size_pt"] = [round(pg.rect.width, 1), round(pg.rect.height, 1)]
            page_rows[p]["rotation"] = pg.rotation
        doc.close()
    except Exception as e:
        rec["fitz_error"] = repr(e)

    for p in range(1, n_pages + 1):
        for j, im in enumerate(imgs.get(p, [])):
            fig_rows.append({"page": p, "kind": "embedded_image", "index": j,
                             "w": im["w"], "h": im["h"], "raw": im["raw"]})
        nd = draw_count.get(p, 0)
        if nd and nd >= MIN_DRAWINGS_FOR_RENDER:
            fig_rows.append({"page": p, "kind": "vector_drawings", "count": nd})

    with open(os.path.join(d, "figure_objects.jsonl"), "w", encoding="utf-8") as fh:
        for r in fig_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # --- 4. 渲染决策
    pages_with_img = set(imgs.keys())
    pages_with_vec = set(p for p, n in draw_count.items() if n and n >= MIN_DRAWINGS_FOR_RENDER)
    pages_scan = set(r["page"] for r in page_rows if r["class"] == "scan_or_empty")
    reason = {}
    to_render = set()
    for p in sorted(pages_with_img):
        reason.setdefault(p, []).append("embedded_image")
    for p in sorted(pages_with_vec):
        reason.setdefault(p, []).append("vector_drawings>=%d" % MIN_DRAWINGS_FOR_RENDER)
    for p in sorted(pages_scan):
        reason.setdefault(p, []).append("no_text_layer")
    # 覆盖性抽样：每 5 页取 1 页（诊断用，不代表已核验全部）
    for p in range(1, n_pages + 1, 5):
        reason.setdefault(p, []).append("coverage_sample")
    to_render = set(reason.keys())

    made = render(pdf, to_render, os.path.join(d, "pages"), RENDER_DPI_FIGURE, reason)
    # 覆盖抽样页用低 dpi 另存
    for p in sorted(set(reason) - set(pages_with_img) - set(pages_with_vec) - set(pages_scan)):
        pass

    for r in page_rows:
        r["render"] = os.path.relpath(made[r["page"]], d) if r["page"] in made else ""
        r["render_reason"] = ",".join(reason.get(r["page"], []))
        r["figure_objects"] = sum(1 for f in fig_rows if f["page"] == r["page"])

    with open(os.path.join(d, "native_text", "pages.jsonl"), "w", encoding="utf-8") as fh:
        for r in page_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # --- 5. 文档级主档（当前=原始抽取；清洗阶段生成 cleaned）
    md = []
    md.append("# %s\n" % os.path.basename(pdf))
    md.append("> source_id: %s\n> 原始路径: `%s`\n> 页数: %d\n> 状态: 原始抽取（未清洗）\n" % (sid, pdf, n_pages))
    for r in page_rows:
        md.append("\n## 第 %d 页（%s，%d 字符）\n" % (r["page"], r["class"], r["chars"]))
        md.append(ptxt.get(r["page"], "").rstrip() + "\n")
    with open(os.path.join(P.MD_DIR, "%s.full.md" % sid), "w", encoding="utf-8") as fh:
        fh.write("".join(md))

    rec.update({
        "status": "extracted",
        "seconds": round(time.time() - t0, 2),
        "pages": n_pages,
        "page_classes": {c: sum(1 for r in page_rows if r["class"] == c)
                         for c in ("text", "mixed", "scan_or_empty")},
        "chars_total": sum(r["chars"] for r in page_rows),
        "figure_objects": len(fig_rows),
        "pages_with_figure": len(set(f["page"] for f in fig_rows)),
        "rendered_pages": len(made),
        "render_reasons": {str(p): reason[p] for p in sorted(reason)},
        "md_path": os.path.join(P.MD_DIR, "%s.full.md" % sid),
        "needs_visual_check": sorted(set(reason.keys())),
    })
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=2)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--top", default="", help="只处理 rel_path 含该前缀的")
    ap.add_argument("--only-year", default="")
    a = ap.parse_args()

    with open(os.path.join(P.INDEX_DIR, "source_manifest.csv"), "r", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh)
                if r["format"] == "pdf" and r["in_scope"] == "Y"]
    if a.source:
        rows = [r for r in rows if r["source_id"] == a.source]
    if a.top:
        rows = [r for r in rows if r["rel_path"].startswith(a.top)]
    if a.only_year:
        rows = [r for r in rows if r["rel_path"].startswith(a.only_year)]
    if a.limit:
        rows = rows[:a.limit]
    print("PDF to process:", len(rows))

    out = []
    for i, r in enumerate(rows, 1):
        try:
            rec = process_one(r)
        except Exception as e:
            rec = {"source_id": r["source_id"], "status": "blocked", "error": repr(e),
                   "rel_path": r["rel_path"]}
        out.append(rec)
        print("[%d/%d] %s %s pages=%s figs=%s rend=%s %ss" % (
            i, len(rows), r["source_id"], rec.get("status"), rec.get("pages"),
            rec.get("figure_objects"), rec.get("rendered_pages"), rec.get("seconds")))
        with open(os.path.join(P.VAL_DIR, "03_pdf_extract_log.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("done", len(out))


if __name__ == "__main__":
    main()
