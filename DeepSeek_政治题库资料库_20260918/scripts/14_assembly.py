#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""约束3：汇编文件逐题确定**可核实的实际出处**，不得继承汇编文件自身信息。

背景：9 份"各区一模试题分类汇编"是跨区跨卷的题目集合。按约束3，来源文件/考试/题目
三层分开登记；汇编里的每道题必须按其真实出处（年份/地区/卷别/题号）归属，
不能因为它在汇编里就记成汇编的题。

做法（只用可核实的证据，不做相似即合并）：
  1. 用与逐题切分相同的口径把汇编切成块
  2. 把每块与**本库已登记的正式卷题目块**做 6-gram 重叠比对
  3. 只有"最佳匹配重叠足够高 且 明显优于次佳"才登记为已定位实际出处；
     否则标"待复核"，绝不凭相似性直接归属或合并

产出：
  indexes/assembly_blocks.csv        汇编内各块及其比对结果
  indexes/assembly_provenance.csv    已定位/待复核汇总
  validation/09_汇编出处核定.md
"""
import csv
import importlib.util
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

_spec = importlib.util.spec_from_file_location(
    "splitmod", os.path.join(os.path.dirname(os.path.abspath(__file__)), "09_split.py"))
S9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S9)

MIN_BLOCK = 60
HIGH = 0.60      # 最佳匹配的重叠下限
MARGIN = 0.20    # 最佳必须比次佳高出这么多，才算"唯一指向"


def ngrams(s, n=6):
    s = re.sub(r"\s+", "", s)
    return set(s[i:i + n] for i in range(max(0, len(s) - n + 1)))


def load_lines(sid, variant):
    body = S9.load_ocr(sid) if variant == "ocr_candidate" else S9.load_clean(sid)[0]
    if not body:
        return []
    return S9.strip_headers(body).splitlines()


def main():
    ef = [r for r in csv.DictReader(
        open(os.path.join(P.INDEX_DIR, "exam_files.csv"), encoding="utf-8"))
        if r["in_scope"] == "Y"]
    asm = [r for r in ef if r["is_assembly"] == "Y"]
    normal = [r for r in ef if r["is_assembly"] != "Y"]
    print("汇编文件:", len(asm), " 正式卷文件:", len(normal))

    # 1) 建立"本库正式卷题目块"比对库（只取原生抽取，OCR 候选不作归属依据）
    qs = [q for q in csv.DictReader(
        open(os.path.join(P.INDEX_DIR, "questions.csv"), encoding="utf-8"))
        if q["variant"] == "native"]
    q_lines = {}
    refs = []
    for q in qs:
        k = (q["source_id"], q["variant"])
        if k not in q_lines:
            q_lines[k] = load_lines(q["source_id"], q["variant"])
        blk = S9.build_blocks  # noqa: F841  (占位，保持与切分口径一致)
        try:
            s0, s1 = (int(x) for x in q["line_range"].split("-"))
        except Exception:
            continue
        txt = "\n".join(q_lines[k][s0:s1])
        if len(txt) < MIN_BLOCK:
            continue
        refs.append({"question_id": q["question_id"], "exam_id": q["exam_id"],
                     "rel_path": q["rel_path"], "grams": ngrams(txt)})
    print("比对库题目块:", len(refs))

    blocks_out, prov_out = [], []
    for a in asm:
        sid = a["source_id"]
        lines = load_lines(sid, "native")
        if not lines:
            prov_out.append({"assembly_id": a["exam_id"], "source_id": sid,
                             "rel_path": a["rel_path"], "status": "无法切分",
                             "reason": "无清洗/原始抽取产物"})
            continue
        bounds = S9.find_boundaries(lines)
        starts = S9.find_question_starts(lines)
        starts, dropped = S9.drop_nested_restarts(starts, bounds)
        blocks = S9.build_blocks(lines, starts, bounds)
        located, unresolved = 0, 0
        for num, blk, s0, s1, trunc in blocks:
            if len(blk) < MIN_BLOCK:
                continue
            g = ngrams(blk)
            scored = []
            for r in refs:
                inter = len(g & r["grams"])
                if not inter:
                    continue
                ov = inter / float(len(g)) if g else 0.0
                scored.append((ov, r))
            scored.sort(key=lambda x: -x[0])
            best = scored[0] if scored else None
            second = scored[1] if len(scored) > 1 else None
            best_ov = best[0] if best else 0.0
            second_ov = second[0] if second else 0.0
            if best and best_ov >= HIGH and (best_ov - second_ov) >= MARGIN:
                status = "已定位实际出处"
                located += 1
            else:
                status = "待复核"
                unresolved += 1
            blocks_out.append({
                "assembly_id": a["exam_id"], "assembly_source_id": sid,
                "assembly_rel_path": a["rel_path"],
                "block_index": num, "line_range": "%d-%d" % (s0, s1), "chars": len(blk),
                "status": status,
                "matched_question_id": best[1]["question_id"] if best else "",
                "matched_exam_id": best[1]["exam_id"] if best else "",
                "matched_rel_path": best[1]["rel_path"] if best else "",
                "best_overlap": round(best_ov, 4),
                "second_overlap": round(second_ov, 4),
                "margin": round(best_ov - second_ov, 4),
                "preview": re.sub(r"\s+", " ", blk)[:150],
            })
        prov_out.append({"assembly_id": a["exam_id"], "source_id": sid,
                         "rel_path": a["rel_path"], "blocks": len(blocks),
                         "located": located, "unresolved": unresolved,
                         "status": "部分定位" if unresolved else "全部定位"})
        print("  %-34s 块%3d 已定位%3d 待复核%3d" % (a["exam_id"], len(blocks), located, unresolved))

    with open(os.path.join(P.INDEX_DIR, "assembly_blocks.csv"), "w",
              encoding="utf-8", newline="") as fh:
        if blocks_out:
            w = csv.DictWriter(fh, fieldnames=list(blocks_out[0].keys()))
            w.writeheader()
            for r in blocks_out:
                w.writerow(r)
    with open(os.path.join(P.INDEX_DIR, "assembly_provenance.csv"), "w",
              encoding="utf-8", newline="") as fh:
        if prov_out:
            w = csv.DictWriter(fh, fieldnames=list(prov_out[0].keys()), restval="")
            w.writeheader()
            for r in prov_out:
                w.writerow(r)

    tot_loc = sum(1 for b in blocks_out if b["status"] == "已定位实际出处")
    print("汇编块合计:", len(blocks_out), " 已定位:", tot_loc,
          " 待复核:", len(blocks_out) - tot_loc)

    # 报告
    lines_md = ["# 汇编文件出处核定（约束3）", "",
                "> 汇编中的每道题按**可核实的实际出处**归属；未达核实门槛的一律标待复核，",
                "> 不因相似就直接归属，也不与正式卷题目合并。", "",
                "## 判定门槛", "",
                "- 已定位实际出处：与某道正式卷题目块的 6-gram 重叠 ≥ %.2f，且比次佳高出 ≥ %.2f"
                % (HIGH, MARGIN),
                "- 其余：待复核（保留汇编原文与比对结果，供人工裁决）", "",
                "## 逐文件结果", "",
                "| 汇编 | 块数 | 已定位 | 待复核 | 状态 |",
                "| --- | --- | --- | --- | --- |"]
    for r in prov_out:
        lines_md.append("| %s | %s | %s | %s | %s |" % (
            r["assembly_id"], r.get("blocks", "-"), r.get("located", "-"),
            r.get("unresolved", "-"), r["status"]))
    lines_md += ["", "## 明细", "",
                 "逐块比对结果见 `indexes/assembly_blocks.csv`（含最佳/次佳重叠与差值）。", ""]
    with open(os.path.join(P.VAL_DIR, "09_汇编出处核定.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines_md) + "\n")
    print("DONE")


if __name__ == "__main__":
    main()
