#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""双通道一致性比对（native 文字层 vs OCR 候选）。

**口径声明（重要）**：
  这是两条抽取通道之间的**自动一致性信号**，用于提示"哪一页值得重点看图"。
  它**不是视觉核验**，本脚本产出的结果**不得**用于把任何页面/题目标记为 verified。
  按用户约束 2：只有实际打开原页对照，才能算完成视觉核验。

真正有用的信号：
  OCR 读的是**渲染图**，因此图内文字、矢量文字 OCR 能看到而原生文字层看不到。
  → 若某页 OCR 明显多于文字层，说明该页很可能存在"文字层取不到的图表/图内文字"。
  → 这类页在视觉核验阶段必须重点看图。

产出：validation/双通道比对.jsonl（逐页）、validation/12b_双通道比对摘要.json
"""
import csv
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P


def norm(s):
    s = re.sub(r"\s+", "", s or "")
    return s


def load_page_texts(sid):
    """返回 {page: {"native": str, "ocr": str}}"""
    out = {}

    def put(p, k, v):
        out.setdefault(p, {"native": "", "ocr": ""})[k] = v

    pj = os.path.join(P.EVID_DIR, sid, "native_text", "pages.jsonl")
    if os.path.isfile(pj):
        for ln in open(pj, encoding="utf-8"):
            try:
                o = json.loads(ln)
            except Exception:
                continue
            if isinstance(o.get("text_blocks"), list):
                t = "\n".join((b.get("text") or "") for b in o["text_blocks"]
                              if isinstance(b, dict))
            else:
                t = o.get("text") or ""
            put(o["page"], "native", t)
    vd = os.path.join(P.EVID_DIR, sid, "visual_transcript")
    if os.path.isdir(vd):
        for fn in sorted(f for f in os.listdir(vd) if f.endswith(".ocr.txt")):
            m = re.match(r"p(\d+)\.ocr\.txt", fn)
            if not m:
                continue
            body = open(os.path.join(vd, fn), encoding="utf-8", errors="replace").read()
            body = re.sub(r"<<<OCR p\d+\.ocr\.txt>>>", "", body)
            put(int(m.group(1)), "ocr", body)
    return out


def main():
    ef = [r for r in csv.DictReader(
        open(os.path.join(P.INDEX_DIR, "exam_files.csv"), encoding="utf-8"))
        if r["in_scope"] == "Y"]
    seen = set()
    rows = []
    for r in ef:
        sid = r["source_id"]
        if sid in seen:
            continue
        seen.add(sid)
        pt = load_page_texts(sid)
        meta = os.path.join(P.EVID_DIR, sid, "meta.json")
        scan_pages = set()
        if os.path.isfile(meta):
            try:
                pc = json.load(open(meta, encoding="utf-8")).get("page_classes") or {}
            except Exception:
                pc = {}
        for pg in sorted(pt):
            nat = norm(pt[pg]["native"])
            ocr = norm(pt[pg]["ocr"])
            inter = 0
            if nat and ocr:
                # 用 6-gram 交集估计重合量
                ng = set(nat[i:i + 6] for i in range(max(0, len(nat) - 5)))
                og = set(ocr[i:i + 6] for i in range(max(0, len(ocr) - 5)))
                inter = len(ng & og)
            rows.append({
                "source_id": sid, "rel_path": r["rel_path"], "page": pg,
                "native_chars": len(nat), "ocr_chars": len(ocr),
                "shared_6gram": inter,
                "ocr_extra": max(0, len(ocr) - len(nat)),
                "both_empty": not nat and not ocr,
                "ocr_only": bool(ocr) and not nat,
                "native_only": bool(nat) and not ocr,
            })
    with open(os.path.join(P.VAL_DIR, "双通道比对.jsonl"), "w", encoding="utf-8") as fh:
        for x in rows:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    # 摘要：哪些页"OCR 明显多于文字层" → 图表文字线索
    c = Counter()
    for x in rows:
        if x["both_empty"]:
            c["两通道皆空"] += 1
        elif x["ocr_only"]:
            c["仅OCR（纯扫描页）"] += 1
        elif x["native_only"]:
            c["仅文字层（未OCR）"] += 1
        elif x["ocr_extra"] >= 80:
            c["OCR明显多于文字层(≥80字，疑似图表文字)"] += 1
        elif x["ocr_extra"] >= 30:
            c["OCR略多于文字层(30-79字)"] += 1
        else:
            c["两通道基本一致"] += 1
    hot = [x for x in rows if not x["ocr_only"] and not x["both_empty"]
           and x["ocr_extra"] >= 80]
    hot.sort(key=lambda x: -x["ocr_extra"])
    summary = {
        "说明": "自动一致性信号，不等于视觉核验，不用于标记 verified",
        "页面总数": len(rows),
        "分类": dict(c),
        "重点看图页（OCR明显多于文字层）": len(hot),
        "重点看图页示例": hot[:15],
        "纯扫描页（仅OCR）": sum(1 for x in rows if x["ocr_only"]),
    }
    with open(os.path.join(P.VAL_DIR, "12b_双通道比对摘要.json"), "w",
              encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in summary.items() if k != "重点看图页示例"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
