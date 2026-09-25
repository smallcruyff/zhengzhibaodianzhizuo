#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段6：题目与答案/评分材料逐题配对（约束3、规范七）。

核心规则：
  - 参考答案不得自动升级为正式细则
  - 等级或分档评分表不得拆成逐点给分
  - 题号相同/考点相近/文件名相似都不足以单独确认配对
  - 候选材料单列候选区，不得塞进正式评分区
  - 三状态相互独立：extraction_status / rubric_status / needs_review

配对证据：考试身份一致 + 题号一致 + **题目自身块文本**的关键片段重叠 + 分值一致（有则用）

v2 修订（针对实测缺陷）：
  1. nums_from_name 只在高考卷语境下套用"20NN.N 分题切片"命名；修正"2023.3高三…"这类
     把日期误读成题号的问题；排除"3-30(1)""5-10(2)"这类区间/序号尾巴的误读。
  2. 题干重叠改用**该题自身块的文本**（按 questions.csv 的 line_range 切片），
     不再拿整份来源文件当题干——原做法会把整卷与材料片段相比，重叠度不可解释。
  3. 材料文件名已显式限定题号且与本题号不符时，判为"存在冲突"，不得判"已匹配"。
  4. 单题文件里的"正式评分材料原文"写入**实际命中的材料片段**，
     不再写材料文件的开头 6000 字（原做法会把别题的细则贴到本题下）。

产出：indexes/rubric_links.csv，并回填 questions/{exam_id}/{qid}.md
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

RE_GAOKAO_SLICE = re.compile(r"^\s*20(\d{2})\s*[.．]\s*(\d{1,2})")
# "N题" / "第N题" / 独立的 "N（k）"；排除日期与区间尾巴
RE_NUM_TI = re.compile(r"(?<![\d.\-–—/])(\d{1,2})\s*题")
RE_NUM_PAREN = re.compile(r"(?<![\d.\-–—/])(\d{1,2})\s*[（(]\s*\d+\s*[）)]")
RE_BARE_PAREN = re.compile(r"^\s*(\d{1,2})\s*[（(]\s*\d+\s*[）)]\s*$")

RUBRIC_ROLES = {"评分材料", "评分细则_分题切片", "阅卷总结"}
ANSWER_ROLES = {"参考答案", "教师版"}

# 与 09_split.py 保持一致的页眉页脚过滤（保证行号可对齐）
SKIP_LINE = re.compile(r"^\s*(第\s*\d+\s*页|共\s*\d+\s*页|高三(年级)?\s*[（(]思想政治|"
                       r"思想政治\s*$|-\s*\d+\s*-|\d+\s*/\s*\d+\s*页)\s*$")


def load_text(sid):
    for cand in (os.path.join(P.EVID_DIR, sid, "cleaned", "clean.md"),
                 os.path.join(P.EVID_DIR, sid, "native_text", "raw.md"),
                 os.path.join(P.EVID_DIR, sid, "native_text", "raw.txt")):
        if os.path.isfile(cand):
            with open(cand, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
    return ""


def load_ocr(sid):
    d = os.path.join(P.EVID_DIR, sid, "visual_transcript")
    if not os.path.isdir(d):
        return ""
    fs = sorted(f for f in os.listdir(d) if f.endswith(".ocr.txt"))
    parts = []
    for f in fs:
        with open(os.path.join(d, f), "r", encoding="utf-8", errors="replace") as fh:
            parts.append("\n\n<<<OCR %s>>>\n\n" % f + fh.read())
    return "".join(parts)


def variant_lines(sid, variant):
    """复现 09_split 的行切分口径，使 line_range 可直接切片。"""
    body = load_ocr(sid) if variant == "ocr_candidate" else load_text(sid)
    if not body:
        return []
    return [ln for ln in body.splitlines() if not SKIP_LINE.match(ln)]


def block_of(lines, line_range):
    """按 's0-s1' 取出该题自身块文本。"""
    try:
        s0, s1 = (int(x) for x in line_range.split("-"))
    except Exception:
        return ""
    return "\n".join(lines[s0:s1])


def ngrams(s, n=6):
    s = re.sub(r"\s+", "", s)
    return set(s[i:i + n] for i in range(max(0, len(s) - n + 1)))


def locate_segment(t, qnum):
    """在材料正文中定位第 qnum 题的片段，返回 (片段, 定位方式)。

    选择题答案常以答案键或表格形式出现（"11．C" / "| 11 | C |"），
    单纯按"N．"找题号段会漏掉它们。多种定位方式并列，命中即记，便于复核。
    """
    if not t:
        return "", None
    # ① 题号起首（主观题细则的常见形态）
    pat = re.compile(r"(?:^|\n)\s*%d\s*[．.、]\s*" % qnum)
    m = pat.search(t)
    if m:
        m2 = re.compile(r"(?:^|\n)\s*%d\s*[．.、]\s*" % (qnum + 1)).search(t, m.end())
        return t[m.start():m2.start() if m2 else min(len(t), m.start() + 4000)], "题号起首"
    # ② 答案键行："11．C" / "11 C" / "11、C"（整行）
    m = re.search(r"(?:^|\n)[ \t]*%d\s*[．.、]?\s*[A-D]\s*(?=\n|$)" % qnum, t)
    if m:
        return m.group(0).strip(), "答案键行"
    # ③ 表格行：Markdown "| 11 | C |" 或 HTML "<td>11</td>"
    m = re.search(r"(?:^|\n)[ \t]*\|[ \t]*%d[ \t]*\|[^\n]{0,200}\|" % qnum, t)
    if m:
        return m.group(0).strip(), "表格行(Markdown)"
    m = re.search(r"<tr[^>]*>\s*<td[^>]*>\s*%d\s*</td>.{0,300}?</tr>" % qnum, t, flags=re.S)
    if m:
        return re.sub(r"\s+", " ", m.group(0)), "表格行(HTML)"
    # ④ 行内答案键："1．C 2．D 3．B …" 中的某一段
    m = re.search(r"(?:^|[\s，,；;])%d\s*[．.、]\s*[A-D](?=[\s，,；;]|$)" % qnum, t)
    if m:
        return m.group(0).strip(), "行内答案键"
    return "", None


def nums_from_name(rel_path, exam_id):
    """从文件名推断其显式限定的题号。

    仅在高考语境下才套用 "20NN.N …" 的分题切片命名；否则会把
    "2023.3高三政治一模统阅…" 里的日期误读成题号 3。
    """
    base = os.path.splitext(os.path.basename(rel_path))[0]
    if "GAOKAO" in exam_id:
        m = RE_GAOKAO_SLICE.match(base)
        if m:
            return {int(m.group(2))}
    out = set()
    for mm in RE_NUM_TI.finditer(base):
        v = int(mm.group(1))
        if 1 <= v <= 30:
            out.add(v)
    for mm in RE_NUM_PAREN.finditer(base):
        v = int(mm.group(1))
        if 1 <= v <= 30:
            out.add(v)
    m = RE_BARE_PAREN.match(base)
    if m:
        out.add(int(m.group(1)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exam")
    a = ap.parse_args()

    with open(os.path.join(P.INDEX_DIR, "exam_files.csv"), "r", encoding="utf-8") as fh:
        files = [r for r in csv.DictReader(fh) if r["in_scope"] == "Y"]
    with open(os.path.join(P.INDEX_DIR, "questions.csv"), "r", encoding="utf-8") as fh:
        qs = list(csv.DictReader(fh))

    by_exam = defaultdict(list)
    for f in files:
        by_exam[f["exam_id"]].append(f)

    text_cache, ocr_cache, lines_cache = {}, {}, {}

    def T(sid):
        if sid not in text_cache:
            text_cache[sid] = load_text(sid)
        return text_cache[sid]

    def L(sid, variant):
        k = (sid, variant)
        if k not in lines_cache:
            lines_cache[k] = variant_lines(sid, variant)
        return lines_cache[k]

    links = []
    per_q = defaultdict(dict)          # question_id -> {(material_source_id, kind): link}
    all_qids = set()
    for q in qs:
        eid = q["exam_id"]
        if a.exam and eid != a.exam:
            continue
        all_qids.add(q["question_id"])
        qnum = int(q["num"])
        qblk = block_of(L(q["source_id"], q["variant"]), q["line_range"])
        qgrams = ngrams(qblk)
        qscore = q["score_value"]
        cands = []
        for f in by_exam[eid]:
            if f["role"] not in RUBRIC_ROLES | ANSWER_ROLES:
                continue
            name_nums = nums_from_name(f["rel_path"], eid)
            explicit_other = bool(name_nums) and qnum not in name_nums
            # 材料文件名显式限定了别的题号 → 不可能是本题的正式材料
            if explicit_other and f["role"] in RUBRIC_ROLES:
                # 仍允许作为"冲突线索"登记（须有真实文本重叠才登记，避免噪声）
                pass

            seg, how = "", None
            if name_nums and qnum in name_nums:
                seg, how = T(f["source_id"]), "文件名限定本题号"
            else:
                seg, how = locate_segment(T(f["source_id"]), qnum)
            ov = 0.0
            if seg and qgrams:
                sg = ngrams(seg)
                ov = len(qgrams & sg) / float(len(qgrams)) if qgrams else 0.0
            kind = "正式评分材料" if f["role"] in RUBRIC_ROLES else "参考答案"

            long_enough = len(seg) >= 120      # 过短片段的 6-gram 重叠不可信
            # 答案键/表格行定位到的短片段：属于"位置已确认"，不是内容重叠证据
            located_short = how in ("答案键行", "表格行(Markdown)", "表格行(HTML)", "行内答案键")

            if explicit_other:
                # 材料文件名已明确限定别的题号（如"16题评分细则""21题(1)"）：
                # 这是**决定性排除证据**，不是"存在冲突"。重叠再高也不可能是本题的材料
                # （实测：Q2 与 16题评分细则 重叠 1.0，其实只是"2."这一点在细则里也出现）。
                # 仍登记一条"已排除"记录以留痕，但不参与题级状态判定。
                status = "已排除（文件名指向他题）"
            elif located_short and kind == "参考答案":
                # 在材料里实际定位到该题的答案位置 → 可确认是本题参考答案
                status = "已匹配参考答案"
            elif name_nums and qnum in name_nums and (ov >= 0.05 or len(seg) < 400):
                status = "已匹配" + ("正式材料" if kind == "正式评分材料" else "参考答案")
            elif seg and ov >= 0.15 and long_enough:
                status = "已匹配" + ("正式材料" if kind == "正式评分材料" else "参考答案")
            else:
                # 同卷存在该类材料但未能在正文定位本题号：仍登记为候选，明确说明未定位
                status = "存在候选"

            ev = ["考试身份同(%s)" % eid]
            if name_nums:
                ev.append("文件名题号{%s}与本题号%s" % (
                    ",".join(str(x) for x in sorted(name_nums)),
                    "一致" if qnum in name_nums else "不一致"))
            else:
                ev.append("文件名未限定题号")
            if how:
                ev.append("正文定位方式=%s" % how)
            else:
                ev.append("未能在材料正文定位到第%d题段，仅按同卷材料登记为候选" % qnum)
            ev.append("题干块6-gram重叠%.4f(题干%d字/材料段%d字)" % (ov, len(qblk), len(seg)))
            if qscore:
                ev.append("分值文本 %s" % qscore)
            cands.append({
                "question_id": q["question_id"], "exam_id": eid, "qnum": qnum,
                "material_source_id": f["source_id"], "material_rel_path": f["rel_path"],
                "material_role": f["role"], "material_kind": kind,
                "pair_status": status, "overlap": round(ov, 4),
                "num_from_name": "/".join(str(x) for x in sorted(name_nums)),
                "seg": seg,
                "evidence": "；".join(ev),
            })
        # 同一份材料对同一道题只能保留一条最强状态的链接。
        # 注意：同一道题可能有多个来源块（native / ocr_candidate），各自产出链接；
        # 必须在**题目层面**去重，否则同一份材料会同时出现在"正式评分材料"与"候选"两处。
        RANK = {"已匹配正式材料": 4, "已匹配参考答案": 3, "存在冲突": 2, "存在候选": 1}
        for c in cands:
            k = (c["material_source_id"], c["material_kind"])
            old = per_q[q["question_id"]].get(k)
            if old is None:
                per_q[q["question_id"]][k] = c
            elif RANK.get(c["pair_status"], 0) > RANK.get(old["pair_status"], 0):
                c["evidence"] += "；同题另一来源块状态较弱(%s)，已按最强状态归并" % old["pair_status"]
                per_q[q["question_id"]][k] = c
            else:
                old["evidence"] += "；同题另一来源块状态较弱(%s)，已按最强状态归并" % c["pair_status"]

    # 题目层面汇总状态（冲突优先）
    stats = defaultdict(int)
    conflict_q = defaultdict(int)
    for qid in all_qids:
        if qid not in per_q:
            stats["暂未找到"] += 1
    for qid, kmap in per_q.items():
        cands = list(kmap.values())
        # "已排除（文件名指向他题）"是决定性排除证据，留痕但不参与题级状态判定
        active = [c for c in cands if c["pair_status"] != "已排除（文件名指向他题）"]
        if not active:
            st = "暂未找到"
        else:
            sts = set(c["pair_status"] for c in active)
            formal = [c for c in active if c["pair_status"] == "已匹配正式材料"]
            if "存在冲突" in sts:
                st = "存在冲突"
            elif len(formal) >= 2:
                st = "存在冲突"        # 同题存在>=2份已确认正式材料且来源不同
            elif "已匹配正式材料" in sts:
                st = "已匹配正式材料"
            elif "已匹配参考答案" in sts:
                st = "仅有参考答案"
            elif "存在候选" in sts:
                st = "存在候选"
            else:
                st = "暂未找到"
        if st == "存在冲突":
            conflict_q[qid] += 1
        stats[st] += 1
        for c in cands:
            c["exam_rubric_status"] = st
            links.append(c)

    cols = ["question_id", "exam_id", "qnum", "material_source_id", "material_rel_path",
            "material_role", "material_kind", "pair_status", "exam_rubric_status",
            "overlap", "num_from_name", "evidence"]
    with open(os.path.join(P.INDEX_DIR, "rubric_links.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, restval="", extrasaction="ignore")
        w.writeheader()
        for c in links:
            w.writerow(c)

    # 冲突与排除明细单列，便于人工裁决
    with open(os.path.join(P.VAL_DIR, "06_配对冲突明细.jsonl"), "w", encoding="utf-8") as fh:
        for c in links:
            if c["pair_status"] in ("存在冲突", "已排除（文件名指向他题）"):
                x = dict(c)
                x["seg"] = x["seg"][:1500]
                fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    # 回填单题文件
    byl = defaultdict(list)
    for c in links:
        byl[c["question_id"]].append(c)
    filled = 0
    for q in qs:
        fp = os.path.join(P.Q_DIR, q["exam_id"], "%s.md" % q["question_id"])
        if not os.path.isfile(fp):
            continue
        with open(fp, "r", encoding="utf-8") as fh:
            md = fh.read()
        ls = byl.get(q["question_id"], [])
        formal = [c for c in ls if c["pair_status"] == "已匹配正式材料"]
        ans = [c for c in ls if c["pair_status"] == "已匹配参考答案"]
        cand = [c for c in ls if c["pair_status"] == "存在候选"]
        conf = [c for c in ls if c["pair_status"] == "存在冲突"]
        excl = [c for c in ls if c["pair_status"] == "已排除（文件名指向他题）"]
        st = ls[0]["exam_rubric_status"] if ls else "暂未找到"
        blk = ["\n## 正式评分材料原文\n"]
        if formal:
            for c in formal:
                blk.append("- 来源 `%s`（角色 %s）" % (c["material_rel_path"], c["material_role"]))
                blk.append("- 证据：%s" % c["evidence"])
                seg = c["seg"] or T(c["material_source_id"])
                blk.append("\n```\n%s\n```\n" % seg[:6000])
        else:
            blk.append("（未找到已确认的正式评分材料；见下方候选区）\n")
        blk.append("\n## 参考答案原文\n")
        if ans:
            for c in ans:
                blk.append("- 来源 `%s`（角色 %s）" % (c["material_rel_path"], c["material_role"]))
                blk.append("- 证据：%s" % c["evidence"])
                seg = c["seg"] or T(c["material_source_id"])
                blk.append("\n```\n%s\n```\n" % seg[:6000])
            blk.append("\n> 参考答案不等于正式细则，不得作为评分依据。\n")
        else:
            blk.append("（无）\n")
        blk.append("\n## 候选评分材料（尚未确认，不得当作正式细则）\n")
        if cand:
            for c in cand:
                blk.append("- 候选 `%s`（%s）" % (c["material_rel_path"], c["evidence"]))
        else:
            blk.append("（无候选）\n")
        if conf:
            blk.append("\n## 题号冲突线索（须人工裁决，不得直接采用）\n")
            for c in conf:
                blk.append("- 冲突 `%s`（%s）" % (c["material_rel_path"], c["evidence"]))
        if excl:
            blk.append("\n## 已排除的材料（文件名明确指向他题，非本题材料）\n")
            for c in excl:
                blk.append("- 排除 `%s`：文件名题号 {%s}，本题号 %s（%s）"
                           % (c["material_rel_path"], c["num_from_name"], c["qnum"],
                              c["evidence"]))
        blk.append("\n## 配对状态\n")
        blk.append("- rubric_status: **%s**" % st)
        blk.append("- 关联材料数: %d（正式 %d / 参考答案 %d / 候选 %d / 冲突 %d / 已排除 %d）" % (
            len(ls), len(formal), len(ans), len(cand), len(conf), len(excl)))
        md = re.sub(r"\n## 正式评分材料原文\n.*?\n## 来源定位\n",
                    "\n" + "\n".join(blk) + "\n## 来源定位\n", md, flags=re.S)
        with open(fp, "w", encoding="utf-8") as fh:
            fh.write(md)
        filled += 1

    print("配对链接数:", len(links), " 回填单题文件:", filled)
    print("rubric_status 分布:", dict(stats))
    print("存在冲突的题数:", len(conflict_q))


if __name__ == "__main__":
    main()
