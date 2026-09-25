#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段5：逐题切分（按真实结构，禁机械正则）+ 约束3 分层登记。

修订要点（v2）：
  - 题型判定改用"选项标记出现次数"（选项中常写成同一行的 A. ①② B. ①③）
  - 支持只含单个题号的分题细则 / 分题切片文件
  - 增加答案键守卫：形如 "1．A 2．D" 的答案行不得当作题目切出
  - 纳入 OCR 候选文本作为切题来源（扫描卷），产出标记 candidate_ocr

产出：
  questions/{exam_id}/{question_id}.md
  indexes/questions.csv
  indexes/split_review.jsonl
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

RE_QNUM = re.compile(r"^[*_#>\s]*(\d{1,2})\s*[．.、]\s*(?=\S)")
# 题号独占一行（扫描卷 OCR 常见：题号与题干被排版/分栏拆开，如 "3." 单独成行）
RE_QNUM_ALONE = re.compile(r"^[*_#>\s]*(\d{1,2})\s*[．.、]\s*[*_]*\s*$")
RE_SUBQ = re.compile(r"[（(]\s*(\d{1,2})\s*[）)]\s*")
RE_OPT_ANY = re.compile(r"(?:^|[\s，,；;、）)])?([A-D])\s*[．.、]")
RE_SCORE = re.compile(r"[（(]\s*(?:共\s*)?(\d{1,2})\s*分\s*[）)]")
RE_SEC2 = re.compile(r"^\s*第二部分")
# 答案键：数字后紧跟单个选项字母，且整行很短
RE_ANSWERKEY = re.compile(r"^\s*\d{1,2}\s*[．.、]?\s*[A-D]\s*$")
# 多题答案挤在同一行（"1．B 2．A 3．C 4．D …"）——整行都是答案键，不得当作题号起点。
# 不拦住它会让"1．B…"成为唯一题号起点，进而把整份答案/细则文件吞成第1题的块。
RE_ANSWERKEY_MULTI = re.compile(r"^\s*(?:\d{1,2}\s*[．.、]?\s*[A-D]\s*){3,}$")

# 块长度下限：低于此长度的块不是一道题（OCR 断页、残留符号等），
# 不登记为题，改为逐条记入切分复核清单，避免"静默丢弃"。
MIN_BLOCK_CHARS = 40

# 分节标题：形如"参考答案""评分细则"独占一行且很短。作为块硬边界，
# 防止最后一题把整节答案/评分材料吞进自己的块里（教师版 PDF 的典型缺陷）。
RE_SEC_HEAD = re.compile(
    r"^\s*[【\[（(]?\s*"
    r"(?:[一二三四五六七八九十\d]+\s*[、.．]?\s*)?"
    r"(参考答案与评分标准|参考答案及解析|参考答案与解析|答案与解析|答案及解析|"
    r"参考答案|试题解析|参考解答|评分参考|评分细则|评分标准|评分说明|阅卷总结|"
    r"细则|答案)"
    r"\s*[】\]）)]?\s*[:：]?\s*$")
# 分节标题与内容挤在同一行（教师版常见："参考答案1  2  3 …"）。这类行同样是分节边界，
# 不识别会让最后一题把整节答案吞进自己的块里（实测 2024 北京高考教师版第21题）。
RE_SEC_HEAD_INLINE = re.compile(
    r"^\s*[【\[（(]?\s*"
    r"(参考答案与评分标准|参考答案及解析|参考答案与解析|答案与解析|答案及解析|"
    r"参考答案|试题解析|参考解答|评分参考|评分细则|评分标准|评分说明|阅卷总结)"
    r"\s*[:：]?\s*\S")
# 单题选项标记上限：真实单选题最多 4 个（含解析重复至多翻倍）。超过即说明块内混入了
# 答案键/解析段，属于合并块，不得判为选择题。
MAX_OPT_FOR_CHOICE = 12

SKIP_LINE = re.compile(r"^\s*(第\s*\d+\s*页|共\s*\d+\s*页|高三(年级)?\s*[（(]?思想政治|"
                       r"思想政治\s*$|-\s*\d+\s*-|\d+\s*/\s*\d+\s*页)\s*$")

SPLITTABLE = {"原卷", "教师版", "评分材料", "参考答案", "评分细则_分题切片", "阅卷总结",
              "讲评", "分题切片_待定"}


def load_text_file(fp):
    with open(fp, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def load_clean(sid):
    for cand in (os.path.join(P.EVID_DIR, sid, "cleaned", "clean.md"),
                 os.path.join(P.EVID_DIR, sid, "native_text", "raw.md"),
                 os.path.join(P.EVID_DIR, sid, "native_text", "raw.txt")):
        if os.path.isfile(cand):
            return load_text_file(cand), cand
    return None, None


def load_ocr(sid):
    """按页序拼接 OCR 候选文本。"""
    d = os.path.join(P.EVID_DIR, sid, "visual_transcript")
    if not os.path.isdir(d):
        return None
    fs = sorted(f for f in os.listdir(d) if f.endswith(".ocr.txt"))
    if not fs:
        return None
    parts = []
    for f in fs:
        parts.append("\n\n<<<OCR %s>>>\n\n" % f + load_text_file(os.path.join(d, f)))
    return "".join(parts)


def strip_headers(text):
    return "\n".join(ln for ln in text.splitlines() if not SKIP_LINE.match(ln))


def count_options(block):
    """选项标记出现次数（同一行多个选项也算）。"""
    return len(RE_OPT_ANY.findall(block))


def classify_type(block, after_sec2):
    n = count_options(block)
    if n > MAX_OPT_FOR_CHOICE:
        # 块内混入了答案键/解析段（教师版常见），不是干净的单选题块
        return "待定", n
    if n >= 2:
        return "选择题", n
    if n == 1 and not after_sec2:
        return "选择题", n
    if after_sec2:
        return "非选择题", n
    return "待定", n


def find_boundaries(lines):
    """分节标题行号，作为块硬边界（含"标题与内容挤在同一行"的形态）。"""
    out = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            continue
        if len(s) <= 30 and RE_SEC_HEAD.match(s):
            out.append(i)
        elif RE_SEC_HEAD_INLINE.match(s):
            out.append(i)
    return out


def find_question_starts(lines):
    """返回题目起点 [(行号, 题号)]。

    只取"最长递增段"会把断链前后的题目整段丢掉：扫描卷 OCR 常在某个题号处断链
    （实测 2026海淀一模 试卷因此漏掉 1-4 题）；而评分细则里的"1、2、3"式枚举点
    又会自成一个更长的递增段，把真正的题号挤掉（实测 2024海淀一模 细则）。
    因此这里**不做递增段筛选**，改为：取 1..30 内的全部题号候选，
    同一题号只保留最早出现的起点，再交给"分节标题后的题号回退"规则去伪（见 main）。
    """
    cands = []
    for i, ln in enumerate(lines):
        if RE_ANSWERKEY.match(ln) or RE_ANSWERKEY_MULTI.match(ln):
            continue          # 答案键守卫（含多题答案挤一行）
        m = RE_QNUM.match(ln) or RE_QNUM_ALONE.match(ln)
        if m:
            v = int(m.group(1))
            if 1 <= v <= 30:
                cands.append((i, v))
    first = {}
    for i, n in cands:
        if n not in first:
            first[n] = i
    return sorted((i, n) for n, i in first.items())


def drop_nested_restarts(starts, bounds):
    """剔除"分节标题之后题号回退"的伪起点。

    评分细则常在某题的细则里再出现"1、强调分析的重要性 / 2、强调综合的重要性"这类
    节内枚举；它们位于分节标题（【细则】/参考答案…）之后，且题号回退到已出现过的
    范围，属于该题的枚举点而非新题目。返回 (保留, 剔除)。
    """
    if not bounds:
        return starts, []
    kept, dropped, max_kept = [], [], 0
    for i, n in starts:
        has_head_before = bounds[0] < i
        if has_head_before and n <= max_kept:
            dropped.append((i, n))
            continue
        kept.append((i, n))
        max_kept = max(max_kept, n)
    return kept, dropped


def build_blocks(lines, starts, bounds):
    """按题号起点切块，并在分节标题处强制截断（防止吞掉整节答案/评分材料）。
    返回 (num, text, start, end, truncated)。"""
    out = []
    for k, (idx, num) in enumerate(starts):
        nxt = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        cut = next((b for b in bounds if b > idx), None)
        end = min(nxt, cut) if cut is not None else nxt
        trunc = cut is not None and cut < nxt
        out.append((num, "\n".join(lines[idx:end]).strip(), idx, end, trunc))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exam")
    a = ap.parse_args()

    with open(os.path.join(P.INDEX_DIR, "exam_files.csv"), "r", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["in_scope"] == "Y"]
    if a.exam:
        rows = [r for r in rows if r["exam_id"] == a.exam]

    review, qrows = [], []
    exams = {}
    seen_sid = set()
    for r in rows:
        sid = r["source_id"]
        if r["is_assembly"] == "Y":
            review.append({"source_id": sid, "exam_id": r["exam_id"], "rel_path": r["rel_path"],
                           "reason": "汇编文件：按约束3 不自动切题，须逐题核实实际出处后单独登记",
                           "action": "deferred_assembly"})
            continue
        if r["role"] not in SPLITTABLE:
            continue
        if sid in seen_sid:
            continue
        seen_sid.add(sid)
        text, src = load_clean(sid)
        ocr = load_ocr(sid)
        variants = []
        if text:
            variants.append(("native", text))
        if ocr:
            variants.append(("ocr_candidate", ocr))
        if not variants:
            review.append({"source_id": sid, "rel_path": r["rel_path"],
                           "reason": "无清洗/原始抽取产物，无法切分", "action": "blocked"})
            continue
        for kind, body in variants:
            lines = strip_headers(body).splitlines()
            sec2 = next((k for k, ln in enumerate(lines) if RE_SEC2.match(ln)), None)
            starts = find_question_starts(lines)
            if len(starts) < 1:
                review.append({"source_id": sid, "exam_id": r["exam_id"], "rel_path": r["rel_path"],
                               "variant": kind, "reason": "未找到任何题号起始",
                               "action": "keep_block_needs_review"})
                continue
            if len(starts) == 1:
                review.append({"source_id": sid, "exam_id": r["exam_id"], "rel_path": r["rel_path"],
                               "variant": kind, "reason": "仅1个题号，按分题材料登记",
                               "found": starts[0][1], "action": "single_question"})
            bounds = find_boundaries(lines)
            starts, dropped_restart = drop_nested_restarts(starts, bounds)
            if dropped_restart:
                review.append({"source_id": sid, "exam_id": r["exam_id"],
                               "rel_path": r["rel_path"], "variant": kind,
                               "reason": "分节标题之后题号回退，判为该题的节内枚举点，不作为新题目",
                               "dropped": [{"line": i, "num": n} for i, n in dropped_restart],
                               "action": "dropped_nested_restart"})
            if bounds:
                after = sorted(n for i, n in starts if i > bounds[0])
                if after:
                    review.append({"source_id": sid, "exam_id": r["exam_id"],
                                   "rel_path": r["rel_path"], "variant": kind,
                                   "reason": "部分题号起点位于分节标题之后，可能来自答案/细则区，须核实",
                                   "nums": after, "action": "starts_after_section_head"})
            blocks = build_blocks(lines, starts, bounds)
            all_nums = [n for n, _, _, _, _ in blocks]
            registered = []
            trunc_nums = [n for n, _, _, _, t in blocks if t]
            if trunc_nums:
                review.append({"source_id": sid, "exam_id": r["exam_id"], "rel_path": r["rel_path"],
                               "variant": kind, "reason": "块在分节标题处被截断（防止吞并答案/评分节）",
                               "truncated_at_question": trunc_nums, "action": "boundary_truncated"})
            for num, blk, s0, s1, trunc in blocks:
                if len(blk) < MIN_BLOCK_CHARS:
                    review.append({"source_id": sid, "exam_id": r["exam_id"],
                                   "rel_path": r["rel_path"], "variant": kind,
                                   "reason": "块过短，不足以构成一道题，未登记为题",
                                   "num": num, "chars": len(blk),
                                   "line_range": "%d-%d" % (s0, s1),
                                   "preview": blk[:80], "action": "dropped_too_short"})
                    continue
                registered.append(num)
                after2 = (sec2 is not None and s0 >= sec2)
                qt, nopt = classify_type(blk, after2)
                # 本题的题型是卷级汇总结果；某个来源块的选项没被取全时，
                # 该条记录须显式标记待复核，不能让"选择题"这个标签掩盖取漏。
                opt_abnormal = (qt == "选择题" and not (2 <= nopt <= 12))
                if opt_abnormal:
                    review.append({"source_id": sid, "exam_id": r["exam_id"],
                                   "rel_path": r["rel_path"], "variant": kind,
                                   "reason": "该来源块被判为选择题但选项标记数异常，选项可能未取全",
                                   "num": num, "option_marks": nopt, "chars": len(blk),
                                   "action": "choice_options_incomplete"})
                sm = RE_SCORE.search(blk)
                qid = "%s-Q%d" % (r["exam_id"], num)
                subs = [s for s in RE_SUBQ.findall(blk) if int(s) <= 9]
                is_subj = (qt == "非选择题")
                ex = exams.setdefault(r["exam_id"], {})
                key = num
                if key not in ex:
                    ex[key] = {"qid": qid, "blocks": [], "type": qt,
                               "score": sm.group(0) if sm else "",
                               "subs": subs if is_subj else [], "types": set()}
                ex[key]["types"].add(qt)
                if qt == "选择题":
                    ex[key]["type"] = "选择题"
                elif ex[key]["type"] == "待定":
                    ex[key]["type"] = qt
                ex[key]["blocks"].append({"source_id": sid, "role": r["role"],
                                          "variant": kind, "rel_path": r["rel_path"], "text": blk,
                                          "line_range": "%d-%d" % (s0, s1),
                                          "option_marks": nopt, "boundary_truncated": trunc})
                qrows.append({
                    "question_id": qid, "exam_id": r["exam_id"], "num": num, "type": qt,
                    "score_text": sm.group(0) if sm else "",
                    "score_value": sm.group(1) if sm else "",
                    "subq_hint": "/".join(subs) if is_subj and subs else "",
                    "source_id": sid, "role": r["role"], "variant": kind,
                    "rel_path": r["rel_path"], "line_range": "%d-%d" % (s0, s1),
                    "chars": len(blk), "option_marks": nopt,
                    "needs_review": "Y" if (kind == "ocr_candidate" or qt == "待定"
                                            or opt_abnormal
                                            or (is_subj and not sm)) else "N",
                    "extraction_status": "candidate_ocr" if kind == "ocr_candidate" else "extracted",
                })
            if registered:
                missing = [x for x in range(1, max(registered) + 1) if x not in registered]
                dup = [x for x, c in Counter(registered).items() if c > 1]
            else:
                missing = []
                dup = []
            if missing:
                review.append({"source_id": sid, "exam_id": r["exam_id"], "rel_path": r["rel_path"],
                               "variant": kind, "reason": "题号序列缺号", "missing": missing,
                               "found": registered, "action": "needs_review"})
            if dup:
                review.append({"source_id": sid, "exam_id": r["exam_id"], "rel_path": r["rel_path"],
                               "variant": kind, "reason": "题号重复", "duplicated": dup,
                               "action": "needs_review"})
            if len(registered) < len(all_nums):
                review.append({"source_id": sid, "exam_id": r["exam_id"], "rel_path": r["rel_path"],
                               "variant": kind, "reason": "部分题号起点未登记为题（块过短）",
                               "kept": registered, "seen": all_nums,
                               "action": "needs_review"})

    # ---- 卷级题型推断（证据：同卷已确证的选择题范围）----
    # 部分卷（尤其高考教师版）没有"第二部分"标记，主观题会被留成"待定"。
    # 用同卷已确证的选择题最大题号做结构性推断：题号在其之后且无任何选项标记的块判为非选择题。
    # 该判定来自卷内结构证据，非凭常识补写；逐条标记 type_source 以便复核。
    inferred = 0
    for exam_id, qmap in exams.items():
        choice_nums = [n for n, q in qmap.items() if q["type"] == "选择题"]
        if not choice_nums:
            continue
        choice_max = max(choice_nums)
        for n, q in qmap.items():
            if q["type"] != "待定":
                continue
            oms = [b["option_marks"] for b in q["blocks"]]
            if n > choice_max and oms and max(oms) == 0:
                q["type"] = "非选择题"
                q["type_source"] = "inferred_from_exam_structure(同卷选择题最大题号=%d)" % choice_max
                inferred += 1
    for q in qrows:
        if q["type"] != "待定":
            continue
        qmap = exams.get(q["exam_id"], {})
        qq = qmap.get(int(q["num"]))
        if qq and qq["type"] != "待定":
            q["type"] = qq["type"]
            q["type_source"] = qq.get("type_source", "")
            # 按同一规则重算 needs_review
            q["needs_review"] = "Y" if (q["variant"] == "ocr_candidate"
                                        or q["type"] == "待定"
                                        or (q["type"] == "非选择题" and not q["score_text"])) else "N"

    # 题型在卷级汇总后才定，因此还要再走一遍：某个来源块本身被判"待定"，
    # 但整题因其他来源块被定为"选择题"时，该块的选项取漏同样必须显式标记。
    for q in qrows:
        if q["type"] != "选择题":
            continue
        om = int(q["option_marks"] or 0)
        if 2 <= om <= 12:
            continue
        q["needs_review"] = "Y"
        review.append({"source_id": q["source_id"], "exam_id": q["exam_id"],
                       "rel_path": q["rel_path"], "variant": q["variant"],
                       "reason": "整题定为选择题，但该来源块选项标记数异常，选项可能未取全",
                       "num": q["num"], "option_marks": om,
                       "action": "choice_options_incomplete"})
    print("卷级推断为非选择题的记录数:", inferred)

    for exam_id, qmap in exams.items():
        d = os.path.join(P.Q_DIR, exam_id)
        P.ensure_dirs(d)
        for num, q in sorted(qmap.items()):
            body = []
            for b in q["blocks"]:
                body.append("\n### 来源：`%s`（角色 %s / %s，位置 %s，选项标记 %d%s）\n"
                            % (b["rel_path"], b["role"], b["variant"], b["line_range"],
                               b["option_marks"],
                               "，已在分节标题处截断" if b.get("boundary_truncated") else ""))
                body.append(b["text"])
            md = ["# %s\n" % q["qid"],
                  "## 身份信息",
                  "- question_id: `%s`" % q["qid"],
                  "- exam_id: `%s`" % exam_id,
                  "- 题号: %s" % num,
                  "- 题型: %s%s" % (q["type"],
                                    "（由同卷结构推断：%s）" % q["type_source"]
                                    if q.get("type_source") else ""),
                  "- 分值: %s" % (q["score"] or "缺失（原文未标注或切分未捕获）"),
                  "- 小问: %s" % ("/".join(q["subs"]) if q["subs"] else "无（或未标注）"),
                  "- 来源文件数: %d（去重后）；来源块数: %d（同题多来源保留各自原文，不合并差异）"
                  % (len(set(b["source_id"] for b in q["blocks"])), len(q["blocks"])),
                  "\n## 题目原文",
                  "\n".join(body),
                  "\n## 正式评分材料原文",
                  "（待阶段6 配对）",
                  "\n## 参考答案原文",
                  "（待阶段6 配对；参考答案不得冒充正式细则）",
                  "\n## 其他相关原文",
                  "（讲评 / 阅卷总结 / 备注 / 勘误，待阶段6 归位）",
                  "\n## 来源定位"]
            for b in q["blocks"]:
                md.append("- `%s`（%s / %s，行 %s）" % (b["rel_path"], b["role"], b["variant"],
                                                      b["line_range"]))
            md.append("\n## 质量标记")
            st = "candidate_ocr" if all(b["variant"] == "ocr_candidate" for b in q["blocks"]) else "extracted"
            md.append("- extraction_status: %s" % st)
            md.append("- rubric_status: 暂未配对")
            md.append("- needs_review: %s" % ("Y" if st == "candidate_ocr" or q["type"] == "待定" else "N"))
            md.append("- 图像依赖: 见 `assets/%s/` 与 `evidence/%s/pages/`；图片路径须显式打开"
                      % (q["blocks"][0]["source_id"], q["blocks"][0]["source_id"]))
            with open(os.path.join(d, "%s.md" % q["qid"]), "w", encoding="utf-8") as fh:
                fh.write("\n".join(md) + "\n")

    cols = ["question_id", "exam_id", "num", "type", "type_source", "score_text", "score_value",
            "subq_hint", "source_id", "role", "variant", "rel_path", "line_range", "chars",
            "option_marks", "needs_review", "extraction_status"]
    with open(os.path.join(P.INDEX_DIR, "questions.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, restval="")
        w.writeheader()
        for q in qrows:
            w.writerow(q)
    with open(os.path.join(P.INDEX_DIR, "split_review.jsonl"), "w", encoding="utf-8") as fh:
        for x in review:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    uniq = set(q["question_id"] for q in qrows)
    print("唯一 question_id:", len(uniq), " 题-来源记录:", len(qrows), " 试卷数:", len(exams))
    print("按题型:", dict(Counter(q["type"] for q in qrows)))
    print("按抽取状态:", dict(Counter(q["extraction_status"] for q in qrows)))
    print("切分存疑记录:", len(review), dict(Counter(x["reason"][:20] for x in review)))
    print("\n各卷题数（题号范围 / 唯一题数）：")
    for e in sorted(exams):
        ns = sorted(exams[e].keys())
        print("  %-24s %2d 题  题号 %s" % (e, len(ns), ("%d-%d" % (ns[0], ns[-1])) if ns else "-"))


if __name__ == "__main__":
    main()
