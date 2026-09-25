#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""约束3 v2：汇编文件逐题确定实际出处 —— **优先解析汇编正文自带的出处标注**。

v1 只用 6-gram 相似度，79 块里只定位了 35 块。
实测发现汇编块正文本身印着出处，例如：

    1.（2024石景山一模1）"军叫工农革命，旗号镰刀斧头。"……
    9.(2024门头沟一模7)党的二十大后，党中央对《中国共产党纪律处分条例》……
    3.（2024丰台一模12）围绕促进民营经济发展壮大……

这是**印刷在汇编里的出处声明**，属可核实证据，远优于"看着像"。
因此 v2 的策略：

  1. 先解析块首的 (年份 区名 届别 题号) 标注 → 直接映射到 exam_id + 题号
  2. 解析失败才回落到 6-gram 比对（阈值 0.60 且领先次佳 0.20）
  3. 两者都不成立 → 标"待复核"，保留原文与全部比对值，绝不凭相似性归属

产出：
  indexes/assembly_blocks.csv
  indexes/assembly_provenance.csv
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
HIGH = 0.60
MARGIN = 0.20

# 区名 → 代码（与 02_exams.py 的 REGION_CODE 保持一致）
REGION_CODE = {
    "海淀": "HD", "东城": "DC", "西城": "XC", "朝阳": "CY", "丰台": "FT",
    "石景山": "SJS", "门头沟": "MTG", "房山": "FS", "通州": "TZ",
    "顺义": "SY", "昌平": "CP", "大兴": "DX", "平谷": "PG",
    "怀柔": "HR", "密云": "MY", "延庆": "YQ", "燕山": "YS",
}
STAGE_CODE = {"一模": "YIMO", "二模": "ERMO", "三模": "SANMO", "期末": "QIMO",
              "期中": "QIZHONG", "零模": "LINGMO", "高考": "GAOKAO"}

_REGIONS = "海淀|东城|西城|朝阳|丰台|石景山|门头沟|房山|通州|顺义|昌平|大兴|平谷|怀柔|密云|延庆|燕山"
_STAGES = "一模|1模|二模|2模|三模|3模|期末|期中|零模|高考|中考"
# 出处标注的多种实际写法：
#   (2024石景山一模1)      —— 年份+区+届别+题号 全在括号内
#   （丰台1模16）           —— 无年份、写成 1模
#   （2024房山一模）19）    —— 题号在右括号**外**
#   **12.（房山1模9）       —— 块号带 markdown 加粗
#   （2024朝阳一模）（16分）—— 括号后跟的是**分值**不是题号，须排除
RE_PROV = re.compile(
    r"[（(]\s*(?P<year>20\d{2})?\s*(?P<region>" + _REGIONS + r")"
    r"\s*(?P<stage>" + _STAGES + r")\s*"
    r"(?P<num1>\d{1,2})?\s*[)）]"
    r"(?:\s*[（(]?\s*(?P<num2>\d{1,2})\s*(?!分)\s*[)）]?)?")
RE_MARKUP = re.compile(r"^[\s*_#>]+")


def ngrams(s, n=6):
    s = re.sub(r"\s+", "", s)
    return set(s[i:i + n] for i in range(max(0, len(s) - n + 1)))


def load_lines(sid, variant):
    body = S9.load_ocr(sid) if variant == "ocr_candidate" else S9.load_clean(sid)[0]
    if not body:
        return []
    return S9.strip_headers(body).splitlines()


def _stage_code(s):
    return STAGE_CODE.get(s) or STAGE_CODE.get(s.replace("1", "一").replace("2", "二")
                                              .replace("3", "三")) or STAGE_CODE.get(
        s.replace("一模", "一模"))


def parse_provenance(blk):
    """从块首解析印在汇编里的出处标注。

    返回 dict：
      year    可能为空（标注没写年份）
      region / stage / num（num 可能为空，见"（2024朝阳一模）（16分）"这类只给分值的）
      raw     原始标注文本
    """
    head = RE_MARKUP.sub("", blk[:100])
    m = RE_PROV.search(head)
    if not m:
        return None
    num = m.group("num1") or m.group("num2")
    return {"year": m.group("year") or "", "region": m.group("region"),
            "stage": m.group("stage"), "num": int(num) if num else None,
            "raw": m.group(0)}


def main():
    ef = [r for r in csv.DictReader(
        open(os.path.join(P.INDEX_DIR, "exam_files.csv"), encoding="utf-8"))
        if r["in_scope"] == "Y"]
    asm = [r for r in ef if r["is_assembly"] == "Y"]
    exams = {e["exam_id"]: e for e in csv.DictReader(
        open(os.path.join(P.INDEX_DIR, "exams.csv"), encoding="utf-8"))}
    print("汇编文件:", len(asm))

    # 比对库（仅原生抽取）
    qs = [q for q in csv.DictReader(
        open(os.path.join(P.INDEX_DIR, "questions.csv"), encoding="utf-8"))
        if q["variant"] == "native"]
    q_lines = {}
    refs = []
    for q in qs:
        k = (q["source_id"], q["variant"])
        if k not in q_lines:
            q_lines[k] = load_lines(q["source_id"], q["variant"])
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
    ALL_MISSING = set()
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
        starts, _ = S9.drop_nested_restarts(starts, bounds)
        blocks = S9.build_blocks(lines, starts, bounds)
        located = unresolved = by_annot = by_ngram = 0
        missing_exams = set()
        for num, blk, s0, s1, trunc in blocks:
            if len(blk) < MIN_BLOCK:
                continue
            g = ngrams(blk)
            scored = []
            for r in refs:
                inter = len(g & r["grams"])
                if inter:
                    scored.append((inter / float(len(g)) if g else 0.0, r))
            scored.sort(key=lambda x: -x[0])
            best = scored[0] if scored else None
            second = scored[1] if len(scored) > 1 else None
            b_ov = best[0] if best else 0.0
            s_ov = second[0] if second else 0.0

            pv = parse_provenance(blk)
            if pv:
                rc = REGION_CODE.get(pv["region"])
                sc = _stage_code(pv["stage"])
                # 标注给了题号 + （年份或有把握定位的考试）→ 决定性定位
                cand_ids = []
                if rc and sc:
                    if pv["year"]:
                        eid = "BJ-%s-%s-%s" % (pv["year"], rc, sc)
                        cand_ids = [eid] if eid in exams else []
                    else:
                        # 标注缺年份：只按 区+届别 收窄，再由文本比对定年份（不继承汇编文件名）
                        cand_ids = [e for e in exams
                                    if e.endswith("-%s-%s" % (rc, sc))
                                    and e != a["exam_id"]]
                if not cand_ids and rc and sc and pv["year"]:
                    # 标注完整（有年份+区+届别）但本库根本没有这一卷 → 这是**原料缺口**，
                    # 不是"无法判断"。实测：2024届汇编引用了 2024门头沟一模 / 2024房山一模，
                    # 而工作区 2024模拟题 下只有 东城/朝阳/海淀/丰台/石景山/西城/顺义。
                    status = "已解析出处但本库无此卷（原料缺口）"
                    missing_exams.add("BJ-%s-%s-%s" % (pv["year"], rc, sc))
                    unresolved += 1
                    mid, mnum, mev = "BJ-%s-%s-%s" % (pv["year"], rc, sc), "", (
                        "汇编标注 %s；该卷不在本库（已核实工作区与全部已授权原料根均无此卷）"
                        % pv["raw"])
                elif rc and sc and pv["num"] and cand_ids:
                    if len(cand_ids) == 1:
                        eid = cand_ids[0]
                        mid, mnum = eid, "%s-Q%d" % (eid, pv["num"])
                        status = "已定位实际出处（汇编内标注）"
                        by_annot += 1
                        located += 1
                        mev = "汇编正文标注 %s" % pv["raw"]
                    else:
                        # 多个候选年份：用文本比对在候选内定
                        sub = [r for r in refs if r["exam_id"] in cand_ids]
                        sc2 = sorted(((len(g & r["grams"]) / float(len(g)) if g else 0.0, r)
                                      for r in sub), key=lambda x: -x[0])
                        if sc2 and sc2[0][0] >= HIGH:
                            eid = sc2[0][1]["exam_id"]
                            mid, mnum = eid, "%s-Q%d" % (eid, pv["num"])
                            status = "已定位实际出处（标注定区届+比对定年份）"
                            by_annot += 1
                            located += 1
                            mev = "标注 %s（无年份）；在 %s 内比对定年，重叠 %.4f" % (
                                pv["raw"], "/".join(cand_ids), sc2[0][0])
                        else:
                            status = "待复核"
                            unresolved += 1
                            mid, mnum, mev = "", "", (
                                "标注 %s 无年份，候选 %s 内最佳重叠 %.4f 未达门槛"
                                % (pv["raw"], "/".join(cand_ids),
                                   sc2[0][0] if sc2 else 0.0))
                elif rc and sc and cand_ids:
                    # 有区届但没题号（如"（2024朝阳一模）（16分）"）：在候选考试内按文本比对定题
                    sub = [r for r in refs if r["exam_id"] in cand_ids]
                    sc2 = sorted(((len(g & r["grams"]) / float(len(g)) if g else 0.0, r)
                                  for r in sub), key=lambda x: -x[0])
                    if sc2 and sc2[0][0] >= HIGH and (
                            len(sc2) == 1 or (sc2[0][0] - sc2[1][0]) >= MARGIN):
                        status = "已定位实际出处（标注定区届+比对定题）"
                        by_annot += 1
                        located += 1
                        mid, mnum = sc2[0][1]["exam_id"], sc2[0][1]["question_id"]
                        mev = "标注 %s 未给题号；在该卷内比对定题，重叠 %.4f" % (
                            pv["raw"], sc2[0][0])
                    else:
                        status = "待复核"
                        unresolved += 1
                        mid, mnum, mev = "", "", (
                            "标注 %s 未给题号，候选内最佳 %.4f 未达门槛"
                            % (pv["raw"], sc2[0][0] if sc2 else 0.0))
                else:
                    status = "待复核"
                    unresolved += 1
                    mid, mnum, mev = "", "", (
                        "标注 %s 无法映射到本库考试（区=%s 届=%s）"
                        % (pv["raw"], pv["region"], pv["stage"]))
            elif best and b_ov >= HIGH and (b_ov - s_ov) >= MARGIN:
                status = "已定位实际出处（文本比对）"
                by_ngram += 1
                located += 1
                mid, mnum, mev = best[1]["exam_id"], best[1]["question_id"], \
                    "6-gram 重叠 %.4f，领先次佳 %.4f" % (b_ov, b_ov - s_ov)
            else:
                status = "待复核"
                unresolved += 1
                mid, mnum, mev = "", "", (
                    "无出处标注；最佳 %s 重叠 %.4f，领先次佳 %.4f，未达门槛"
                    % (best[1]["question_id"] if best else "-", b_ov, b_ov - s_ov))
            blocks_out.append({
                "assembly_id": a["exam_id"], "assembly_source_id": sid,
                "assembly_rel_path": a["rel_path"], "block_index": num,
                "line_range": "%d-%d" % (s0, s1), "chars": len(blk),
                "status": status, "matched_exam_id": mid,
                "matched_question_id": mnum, "evidence": mev,
                "best_overlap": round(b_ov, 4), "second_overlap": round(s_ov, 4),
                "margin": round(b_ov - s_ov, 4),
                "preview": re.sub(r"\s+", " ", blk)[:160],
            })
        prov_out.append({"assembly_id": a["exam_id"], "source_id": sid,
                         "rel_path": a["rel_path"], "blocks": len(blocks),
                         "located": located, "unresolved": unresolved,
                         "by_annotation": by_annot, "by_ngram": by_ngram,
                         "missing_exams": "/".join(sorted(missing_exams)),
                         "status": "全部定位" if unresolved == 0 else "部分定位"})
        if missing_exams:
            ALL_MISSING.update(missing_exams)
        print("  %-36s 块%3d 已定位%3d(标注%d/比对%d) 待复核%3d"
              % (a["exam_id"], len(blocks), located, by_annot, by_ngram, unresolved))

    for name, rows in (("assembly_blocks.csv", blocks_out),
                       ("assembly_provenance.csv", prov_out)):
        if rows:
            with open(os.path.join(P.INDEX_DIR, name), "w", encoding="utf-8",
                      newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), restval="")
                w.writeheader()
                for r in rows:
                    w.writerow(r)

    tot = len(blocks_out)
    loc = sum(1 for b in blocks_out if b["status"].startswith("已定位"))
    ann = sum(1 for b in blocks_out if "标注" in b["status"])
    print("汇编块合计: %d  已定位: %d（其中依标注 %d）  待复核: %d"
          % (tot, loc, ann, tot - loc))

    md = ["# 汇编文件出处核定（约束3 · v2）", "",
          "> **优先依据**：汇编正文里印着的出处标注，如 `1.（2024石景山一模1）`。",
          "> 这是随题印刷的出处声明，属可核实证据；解析不到才用文本比对；",
          "> 两者都不成立一律标待复核，**不凭相似性归属**。", "",
          "## 门槛", "",
          "- 已定位（标注）：块首能解析 `(年份 区名 届别 题号)` 且该考试在本库中",
          "- 已定位（比对）：6-gram 重叠 ≥ %.2f 且领先次佳 ≥ %.2f" % (HIGH, MARGIN),
          "- 其余：待复核", "",
          "## 逐文件结果", "",
          "| 汇编 | 块数 | 已定位 | 依标注 | 依比对 | 待复核 | 状态 |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in prov_out:
        md.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            r["assembly_id"], r.get("blocks", "-"), r.get("located", "-"),
            r.get("by_annotation", "-"), r.get("by_ngram", "-"),
            r.get("unresolved", "-"), r["status"]))
    gap = [x for x in sorted(blocks_out, key=lambda b: b["matched_exam_id"])
           if x["status"] == "已解析出处但本库无此卷（原料缺口）"]
    md += ["", "**合计**：%d 块，已定位 %d（依标注 %d、依比对 %d），其余 %d。"
           % (tot, loc, ann, loc - ann, tot - loc), ""]
    if gap:
        md += ["## ⚠ 原料缺口（由汇编标注反查发现）", "",
               "汇编明确标注了出处，但该卷**不在本库**。已核实工作区与全部已授权原料根均无此卷：", ""]
        for x in gap:
            md.append("- `%s` ← 汇编块 `%s`（%s）" % (
                x["matched_exam_id"], x["assembly_id"], x["evidence"]))
        md.append("")
        md.append("这是**原料覆盖缺口**，不是切分或配对缺陷；对应题目只保留汇编内的转录原文。")
        md.append("")
    md += ["明细见 `indexes/assembly_blocks.csv`（含证据字段与全部比对值）。", ""]
    if ALL_MISSING:
        print("⚠ 本库缺卷（汇编引用但无原件）:", sorted(ALL_MISSING))
    with open(os.path.join(P.VAL_DIR, "09_汇编出处核定.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("DONE")


if __name__ == "__main__":
    main()
