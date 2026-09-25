#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检索与任务包生成（规范九.3）。

用法：
  python3 bank.py list [--year 2026] [--region 海淀] [--stage 一模] [--type 选择题]
  python3 bank.py exams
  python3 bank.py get BJ-2026-HD-YIMO-Q1            # 输出单题全文
  python3 bank.py packet BJ-2026-HD-YIMO-Q1 [-o DIR] # 生成任务包
  python3 bank.py search 桑基鱼塘                    # 原文关键词检索
  python3 bank.py verify                            # 自检

任务包内容：题目完整材料 + 已确认评分材料 + 参考答案（单独标注）+ 候选材料（提示未确认）
          + 来源表 + 所需图片清单（须显式打开）
"""
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
from urllib.parse import unquote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P


def read_csv(name):
    p = os.path.join(P.INDEX_DIR, name)
    if not os.path.isfile(p):
        return []
    # questions.csv may carry a UTF-8 BOM; utf-8-sig is also safe for files
    # without one and keeps the first field name stable as ``question_id``.
    with open(p, "r", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def q_path(qid):
    rows = []
    with open(os.path.join(P.INDEX_DIR, "questions.csv"), "r", encoding="utf-8-sig") as fh:
        for q in csv.DictReader(fh):
            if q["question_id"] == qid:
                rows.append(q)
    if not rows:
        return None, None
    # The index can contain rubric/PPT/OCR slices before the authoritative
    # visual review row.  Keep the same file path, but use the explicitly
    # marked visual_checked_shared row for packet source metadata when present.
    q = next((row for row in rows if row.get("variant") == "visual_checked_shared"), rows[0])
    return os.path.join(P.Q_DIR, q["exam_id"], "%s.md" % qid), q


def cmd_exams(a):
    ex = read_csv("exams.csv")
    print("%-24s %-5s %-7s %-7s %-6s %5s %5s %s" % (
        "exam_id", "year", "region", "stage", "paper", "files", "qs", "rubric"))
    for e in ex:
        if e.get("is_assembly") == "Y":
            continue
        print("%-24s %-5s %-7s %-7s %-6s %5s %5s %s" % (
            e["exam_id"], e["year"], e["region"], e["stage"], e["has_paper"],
            e["file_count"], e["question_count"] or "-", e["has_rubric"]))


def cmd_list(a):
    qs = read_csv("questions.csv")
    ex = {e["exam_id"]: e for e in read_csv("exams.csv")}
    n = 0
    for q in qs:
        e = ex.get(q["exam_id"], {})
        if a.year and e.get("year") != a.year:
            continue
        if a.region and a.region not in (e.get("region") or ""):
            continue
        if a.stage and e.get("stage") != a.stage:
            continue
        if a.type and q["type"] != a.type:
            continue
        if a.status and q["extraction_status"] != a.status:
            continue
        n += 1
        if not a.count:
            print("%-26s %-6s %-4s %-8s %-16s %s" % (
                q["question_id"], e.get("year"), q["num"], q["type"],
                q["extraction_status"], os.path.basename(q["rel_path"])[:34]))
    print("命中:", n)


STEM_SECTIONS = [
    "原题文字（视觉核对候选；页图为保真主证据）",
    "原卷视觉核对结构化转写",
    "题目原文（原卷·native，读取优先）",
    "题目原文（原卷·视觉核校转写）",
    "题目原文（原卷·已对照页图）",
    "题目原文（原卷·native；文字为已核对的缓存转写，原页图为保真依据）",
    "题目原文（原卷·native）",
    "题目原文（原卷·native，完整保留）",
    "题目原文（原卷·native，跨页完整保留）",
    "题目原文（原卷·native，完整候选）",
    "题目原文（原卷·视觉核验候选）",
    "题目原文（原卷 p004；视觉复核，不静默规范化）",
    "原题保真转写",
    "题面（教师版混合载体p1-p10的完整试卷区）",
    "题面（E0｜教师版题面来源）",
    "已核题面（原卷逐页核对，读取优先）",
    "题面（Luna/max独立复核通过，verified）",
    "题面（原页双重核验，verified）",
]
NON_STEM_SECTIONS = [
    "评分材料来源块（原样保留，配对状态见下）",
    "参考答案来源块（不得当作评分依据）",
    "讲评来源块（含答案与解析，不得当作题面）",
]
LEGACY_STEM = "题目原文"

# Controlled aliases only: exact-title matching prevents unknown source roles
# from being promoted to E1/E3.  The old titles remain first-class aliases.
# Explicit guide selections retain the old accepted source-specific titles;
# fallback is narrower and only accepts an actual original-question title.
GUIDED_STEM_ALIASES = tuple(dict.fromkeys([
    "题目原文",
    "原题文字（视觉核对候选；页图为保真主证据）",
    "原卷视觉核对结构化转写",
    "题目原文（原卷·native，读取优先）",
    "题目原文（主卷 PDF E0；原生文字层＋原卷页图）",
    "题目原文（原卷·native，修复候选）",
    "题目原文（原卷·视觉核校转写）",
    "题目原文（原卷·已对照页图）",
    "题目原文（原卷·native；文字为已核对的缓存转写，原页图为保真依据）",
    "题目原文（原卷·native）",
    "题目原文（原卷·native，完整保留）",
    "题目原文（原卷·native，跨页完整保留）",
    "题目原文（原卷·native，完整候选）",
    "题目原文（原卷·视觉核验候选）",
    "题目原文（原卷 p004；视觉复核，不静默规范化）",
    "原题保真转写",
    "题面（教师版混合载体p1-p10的完整试卷区）",
    "题面（E0｜教师版题面来源）",
    "已核题面（原卷逐页核对，读取优先）",
    "题面（Luna/max独立复核通过，verified）",
    "题面（原页双重核验，verified）",
    "原卷题面（原卷·native，读取优先）",
    "原卷题面（视觉核校转写）",
    "原卷题面（逐页视觉核验后的可读转写）",
    "原卷视觉核验候选题面",
    "原卷逐字转写",
    "原题转录（视觉核对候选）",
    "题面（不含内附答案、分析、详解）",
    # Current accepted question-file titles. Exact-title aliases only.
    "题面（教师版混合载体 p1-p7 的原卷区，已逐页视觉核对）",
    "题面（教师版混合载体p1-p7的完整试卷区）",
    "题面（原卷native主读版）",
    "题面（视觉核对候选转写）",
    "题面（原卷视觉核对转写）",
    "题面（教师版 p1，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p2，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p3，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p4，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p5，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p6，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p7，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p8，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p1-p2，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p2-p3，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p3-p4，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p4-p5，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p5-p6，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p7-p8，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（原卷第一部分，已逐页视觉核对，与文本层比对一致）",
    "题面（原卷第二部分，已逐页视觉核对，与文本层比对一致）",
    "原卷完整题面（以原卷 PDF 和页面图为准）",
    "题目原文（原卷·native＋原图视觉核验）",
    "E0教师版有界题面（不含答案/解析）",
    "题目原文（原卷 native；未以答案/细则反推）",
    "题目原文（原卷·逐页对照）",
    "原题文字（已对照原卷页）",
    "题目原文（原卷·native，补足缺失的原卷角色）",
    "原题题面（依据教师版 p1-p11）",
    "题目原文（原卷·native，逐页视觉核对版）",
    "题面原文（教师版）",
    "视觉核定完整题面（覆盖缓存缺失/污染）",
    "来源角色：ORIGINAL_QUESTION（原卷视觉回源）",
    "原题完整候选文字（原卷页级对照）",
    "原题（E0：原卷）",
    "题库缓存转写（逐页视觉核定清洁文本）",
    # Generic exact heading is trusted only when a machine-readable guide selects it.
    "题面",
]))
STEM_ALIASES = tuple(dict.fromkeys([
    LEGACY_STEM,
    "原题文字（视觉核对候选；页图为保真主证据）",
    "原卷视觉核对结构化转写",
    "题目原文（原卷·native，读取优先）",
    "题目原文（主卷 PDF E0；原生文字层＋原卷页图）",
    "题目原文（原卷·native，修复候选）",
    "题目原文（原卷·视觉核校转写）",
    "题目原文（原卷·已对照页图）",
    "题目原文（原卷·native；文字为已核对的缓存转写，原页图为保真依据）",
    "题目原文（原卷·native）",
    "题目原文（原卷·native，完整保留）",
    "题目原文（原卷·native，跨页完整保留）",
    "题目原文（原卷·native，完整候选）",
    "题目原文（原卷·视觉核验候选）",
    "题目原文（原卷 p004；视觉复核，不静默规范化）",
    "原题保真转写",
    "题面（教师版混合载体p1-p10的完整试卷区）",
    "题面（E0｜教师版题面来源）",
    "已核题面（原卷逐页核对，读取优先）",
    "题面（Luna/max独立复核通过，verified）",
    "题面（原页双重核验，verified）",
    "原卷题面（按原卷物理页视觉核定）",
    "原卷题面（原卷·native，读取优先）",
    "原卷题面（视觉核校转写）",
    "原卷题面（逐页视觉核验后的可读转写）",
    "题目原文（原卷·PDF权威，修复候选）",
    "原卷视觉核验候选题面",
    "原卷逐字转写",
    "原题转录（视觉核对候选）",
    "题面（不含内附答案、分析、详解）",
    # Current accepted question-file titles. Exact-title aliases only.
    "题面（教师版混合载体 p1-p7 的原卷区，已逐页视觉核对）",
    "题面（教师版混合载体p1-p7的完整试卷区）",
    "题面（原卷native主读版）",
    "题面（视觉核对候选转写）",
    "题面（原卷视觉核对转写）",
    "题面（教师版 p1，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p2，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p3，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p4，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p5，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p6，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p7，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p8，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p1-p2，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p2-p3，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p3-p4，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p4-p5，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p5-p6，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（教师版 p7-p8，已逐页视觉核对；本卷无独立原卷文件，教师版题干区即唯一题面来源）",
    "题面（原卷第一部分，已逐页视觉核对，与文本层比对一致）",
    "题面（原卷第二部分，已逐页视觉核对，与文本层比对一致）",
    "原卷完整题面（以原卷 PDF 和页面图为准）",
    "题目原文（原卷·native＋原图视觉核验）",
    "E0教师版有界题面（不含答案/解析）",
    "题目原文（原卷 native；未以答案/细则反推）",
    "题目原文（原卷·逐页对照）",
    "原题文字（已对照原卷页）",
    "题目原文（原卷·native，补足缺失的原卷角色）",
    "原题题面（依据教师版 p1-p11）",
    "题目原文（原卷·native，逐页视觉核对版）",
    "题面原文（教师版）",
    "视觉核定完整题面（覆盖缓存缺失/污染）",
    "来源角色：ORIGINAL_QUESTION（原卷视觉回源）",
    "原题完整候选文字（原卷页级对照）",
    "原题（E0：原卷）",
    "题库缓存转写（逐页视觉核定清洁文本）",
]))
ROLE_SECTION_ALIASES = {
    "e1": (
        "正式评分材料原文",
        "E1 正式评分材料原文",
        "正式评分材料原文（E1）",
        "正式评分材料原文（E1，按小问闭合）",
        "正式评分材料原文（E1，细则.docx）",
        "正式评分材料原文（E1，细则表2）",
        "正式评分材料（E1）",
        "正式评分材料（E1；S54715a1e650d）",
        "正式评分材料（E1；与候选答案层分离）",
        "正式评分细则（E1）",
    ),
    "e3": (
        "参考答案原文",
        "E3 参考答案原文",
        "参考答案（E3）",
        "参考答案原文/答案键（E3；非E1）",
        "参考答案原文（参考答案层，不等同正式细则）",
        "参考答案原文（非评分依据）",
        "参考答案（E3，不得当作正式评分依据）",
        "参考答案（E3，不是正式评分细则）",
        "参考答案（E3；不是正式评分细则）",
        "参考答案（E3；不得据此拆分E1）",
        "参考答案（E3／答案键层，与E1分层）",
        "参考答案（独立裁定：参考答案；附通用等级描述，非E1）",
        "参考答案（附通用等级描述，非E1）（S85）",
        "同卷答案及评分参考（E3；非E1）",
    ),
    "student": (
        "学生原答及教师批注",
        "学生原答、批注与评分标记",
        "学生原答、教师批注、实得分",
        "学生示例、原答、批注与实得分",
        "学生示例、批注与实得分",
        "学生示例、教师批注与实得分",
        "学生示例与批注",
        "学生证据与批注",
        "学生样卷、教师批注、实得分",
        "学生样卷、批注与实得分",
        "学生样卷、批注、评分标记与实得分",
        "学生示例与教师批注层",
        "学生样卷、教师批注与实得分图像",
        "学生示例与教师批注（独立样卷层；不作为标准答案）",
        "学生样卷、教师批注与评分标记（评分材料嵌图；非标准答案）",
    ),
}
ROLE_SECTION_QID_ALIASES = {
    "e1": {
        "BJ-2023-DC-ERMO-Q16": ("正式评分材料（E1，限同题等级标准）",),
        "BJ-2023-DC-ERMO-Q21": ("正式评分材料（E1，限同题等级标准）",),
    },
}
STRUCTURE_SECTIONS = (
    "原卷页图（不可替代的完整保真载荷）",
    "原题图、表、框线与结构转写",
    "原题页图",
    "原卷图像与题内图表",
    "原卷页面图（文字层与原图并存）",
    "图像与原页证据",
    "原卷图像与来源覆盖",
    "原页版式标记（非题面文字）",
    "原卷嵌入图（题面组成部分）",
    "图片、图中文字、表格、箭头与版面关系",
    "本轮结构差分（仅补图形关系，不改六个1分节点）",
    "原题图片、表格与结构",
)
PASSTHROUGH_SECTIONS = (
    "评分材料（与题面分层）",
    "评分材料来源块（原样保留，配对状态见下）",
    "评分材料来源块（原样保留）",
    "参考答案来源块（不得当作评分依据）",
    "参考答案及正式评分材料",
    "参考答案层（来自正式评分材料中的答案键或答案段）",
    "答案来源层级与学生证据",
    "参考答案原文（来源冲突，必须并列保留）",
    "讲评来源块（含答案与解析，不得当作题面）",
    "教师讲评／解题提示（非E1补充层）",
    "教师示例/讲评示例（不是学生答卷）",
    "Source specific DOCX 题面层 不覆盖上方 PDF 层",
    "正式评分材料",
    "正式评分材料（无题级E1）",
    "评分材料答案键（非独立参考答案）",
    "原卷嵌入式参考答案（非独立答案源）",
    "原卷嵌入式参考答案摘录（非题面；非正式评分材料）",
    "原卷嵌入式参考答案与等级材料（非独立答案源）",
    "嵌入式参考答案（原卷 p007；不是正式评分细则）",
    "内附答案（来源载体内容；非独立参考答案）",
    "原卷 OCR 候选（未逐字对照，不得直接采用）",
    "教师版题面来源（含答案，须回原卷核实）",
    "原卷 native 文本层提取变体（原样保留，不作为视觉替代）",
    "答案层（与评分细则分层）",
    "1. 范围、题面与角色隔离",
)
UNKNOWN_ROLE_SECTIONS = (
    "待确认材料来源块（角色未定，须人工裁决）",
)
# Legacy default `get` exposed these explicitly unsafe source blocks when the
# guide selected them.  Keep that surface text for old callers, but never
# treat either block as an adopted stem or as E1/E3/student.
DEFAULT_PASSTHROUGH_SECTIONS = (
    "教师版题面来源（含答案，须回原卷核实）",
    "原卷 OCR 候选（未逐字对照，不得直接采用）",
)
UNCLASSIFIED_CONTAINER = "未分类原始内容，角色未自动判定"


def role_sections(by, role, qid=None):
    """Yield (title, body) only for exact, controlled role aliases."""
    titles = list(ROLE_SECTION_ALIASES.get(role, ()))
    titles.extend(ROLE_SECTION_QID_ALIASES.get(role, {}).get(qid, ()))
    for title in titles:
        if title in by:
            yield title, by[title]


def append_unclassified(parts, sections, emitted):
    """Keep every un-emitted source section verbatim without assigning a role."""
    remaining = [(title, body) for title, body in sections if title not in emitted]
    if not remaining:
        return
    parts.append("\n## %s\n" % UNCLASSIFIED_CONTAINER)
    parts.append("> ⚠ 以下原标题和正文仅原样保留；未自动归入题面、E1、E3或学生层。\n")
    for title, body in remaining:
        parts.append("\n> 原始二级段 `%s` 以下按源 Markdown 层级原样保留。\n" % title)
        parts.append("\n## %s%s" % (title, body))


def packet_role_title(role, title):
    """Keep legacy packet headings byte-compatible; preserve new titles."""
    if role == "e1" and title == "正式评分材料原文":
        return "正式评分材料原文（不得与题面混用）"
    if role == "e3" and title == "参考答案原文":
        return "参考答案原文（不等于正式细则）"
    return title


def split_md(md):
    """返回 [(title, body)]（不含 '## '）。"""
    ms = list(re.finditer(r"^## (.+)$", md, re.M))
    out = []
    for i, m in enumerate(ms):
        e = ms[i + 1].start() if i + 1 < len(ms) else len(md)
        out.append((m.group(1).strip(), md[m.end():e]))
    return out


def adopted_stem(md):
    """按读取指引取出本题应采用的小节；兼容未分层的旧文件。"""
    secs = split_md(md)
    by = dict(secs)
    guide = by.get("读取指引（机器可读）", "")
    m = re.search(r"^-\s*采用题面小节\s*[:：]\s*`?([^`\n]+?)`?\s*$", guide, re.M)
    if m:
        t = m.group(1)
        if t in GUIDED_STEM_ALIASES and t in by:
            return t, by[t]
    for t in STEM_ALIASES:
        if t in by:
            return t, by[t]
    return None, ""


def cmd_get(a):
    fp, q = q_path(a.qid)
    if not fp:
        print("未找到:", a.qid)
        return 1
    md = open(fp, encoding="utf-8").read()
    if a.all:
        print(md)
        return 0
    secs = split_md(md)
    by = dict(secs)
    out = ["# %s\n" % a.qid]
    if "身份信息" in by:
        out.append("## 身份信息" + by["身份信息"])
    if "读取指引（机器可读）" in by:
        out.append("## 读取指引（机器可读）" + by["读取指引（机器可读）"])
    t, body = adopted_stem(md)
    emitted = {"身份信息", "读取指引（机器可读）"}
    rendered_sections = set()

    def emit_get_section(title, section_body, rendered_body=None):
        key = (title, section_body)
        if key in rendered_sections:
            return False
        rendered_sections.add(key)
        out.append("## %s%s" % (title, section_body if rendered_body is None else rendered_body))
        return True

    # Identity and guide are emitted before the role-aware section pass and
    # are not part of the overlap-prone aliases below.
    if "身份信息" in by:
        rendered_sections.add(("身份信息", by["身份信息"]))
    if "读取指引（机器可读）" in by:
        rendered_sections.add(("读取指引（机器可读）", by["读取指引（机器可读）"]))
    if t:
        emit_get_section(t, body)
        emitted.add(t)
    else:
        if not any(title in by for title in DEFAULT_PASSTHROUGH_SECTIONS):
            out.append("> ⚠ 本题未取得可作题面的小节；"
                       "用 `bank.py get %s --all` 查看全部原文，或回原卷核实。\n" % a.qid)
    if not t:
        for title in DEFAULT_PASSTHROUGH_SECTIONS:
            if title in by:
                emit_get_section(title, by[title])
                emitted.add(title)
    # Explicitly named figure/table/frame sections are stem adjuncts, not
    # answer/rubric roles; retain them without dumping unknown sections.
    for title, section_body in secs:
        if title in STRUCTURE_SECTIONS and title != t:
            emit_get_section(title, section_body)
            emitted.add(title)
    if a.with_rubric:
        for role in ("e1", "e3", "student"):
            for title, section_body in role_sections(by, role, a.qid):
                emit_get_section(title, section_body)
                emitted.add(title)
        for title in PASSTHROUGH_SECTIONS:
            if title in by:
                emit_get_section(title, by[title])
                emitted.add(title)
        for title in UNKNOWN_ROLE_SECTIONS:
            if title in by:
                emit_get_section(
                    title,
                    by[title],
                    "\n> ⚠ 原始角色未定；本段不得当作题面、E1、E3或学生层。\n%s" % by[title],
                )
                emitted.add(title)
        for k in ("候选评分材料（尚未确认，不得当作正式细则）",
                  "配对状态", "来源定位", "质量标记"):
            if k in by:
                emit_get_section(k, by[k])
                emitted.add(k)
        append_unclassified(out, secs, emitted)
    else:
        if "配对状态" in by:
            out.append("## 配对状态" + by["配对状态"])
        # 图像依赖必须默认可见：读取器要能直接知道该打开哪一页/哪张图
        qm = by.get("质量标记", "")
        img = re.search(r"^- 图像依赖（页级，须显式打开）：\n((?:  - .*\n?)+)", qm, re.M)
        if img:
            out.append("\n## 所需图片（页级，须显式打开；路径不等于已看见）\n"
                       + img.group(1))
        elif "图像依赖" in qm:
            line = re.search(r"^- 图像依赖: .*$", qm, re.M)
            out.append("\n## 所需图片（须显式打开）\n" + (line.group(0) if line else ""))
        out.append("\n> 本题另有评分材料/参考答案/讲评等小节，"
                   "加 `--with-rubric` 才输出；`--all` 输出全部原文。\n")
    print("".join(out))
    return 0


def cmd_search(a):
    kw = a.keyword
    hits = []
    for fn in sorted(os.listdir(P.MD_DIR)):
        if not fn.endswith(".full.md"):
            continue
        p = os.path.join(P.MD_DIR, fn)
        with open(p, encoding="utf-8", errors="replace") as fh:
            t = fh.read()
        c = t.count(kw)
        if c:
            hits.append((c, fn))
    hits.sort(reverse=True)
    print("关键词 `%s` 命中 %d 份文档：" % (kw, len(hits)))
    for c, fn in hits[:40]:
        print("  %-4d  %s" % (c, fn))


try:
    # Reuse the pipeline's balanced destination scanner when the shared
    # workspace helper is importable.  The fallback is the same scanner body
    # so the isolated bank remains self-contained when copied elsewhere.
    _pipeline_link_dir = os.path.join(P.WORKSPACE, "后勤管理/MD全库流水线_20260921")
    if _pipeline_link_dir not in sys.path:
        sys.path.insert(0, _pipeline_link_dir)
    from audit_all_markdown_links import destinations as markdown_destinations
except ImportError:
    def markdown_destinations(text):
        pos = 0
        while True:
            start = text.find("](", pos)
            if start < 0:
                return
            i = start + 2
            if i < len(text) and text[i] == "<":
                end = text.find(">", i + 1)
                close = text.find(")", end + 1) if end >= 0 else -1
                if end >= 0 and close >= 0:
                    yield text[i + 1:end], start
                    pos = close + 1
                    continue
            depth = 0
            end = i
            while end < len(text):
                ch = text[end]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    if depth == 0:
                        break
                    depth -= 1
                end += 1
            if end >= len(text):
                return
            raw = text[i:end].strip()
            if " \"" in raw:
                raw = raw.split(" \"", 1)[0]
            yield raw, start
            pos = end + 1


def _markdown_destination_spans(text):
    """Yield (path_start, path_end, raw, angle_bracketed) from pipeline spans."""
    for raw, offset in markdown_destinations(text):
        start = offset + 2
        if start >= len(text):
            continue
        if text[start] == "<":
            end = text.find(">", start + 1)
            if end < 0:
                continue
            yield start, end + 1, raw, True
            continue
        close = start
        depth = 0
        while close < len(text):
            ch = text[close]
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    break
                depth -= 1
            close += 1
        if close >= len(text):
            continue
        field = text[start:close]
        title_at = field.find(" \"")
        end = start + title_at if title_at >= 0 else close
        yield start, end, raw, False


def _link_source_path(src_dir, destination):
    """Resolve a Markdown destination and classify its portability boundary."""
    target = destination.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    if not target or target.startswith("#"):
        return None, None, "fragment"
    path_part, sep, anchor = target.partition("#")
    path_part = path_part.split("?", 1)[0]
    path_part = unquote(path_part)
    anchor = unquote(anchor) if sep else None
    if not path_part:
        return None, anchor, "fragment"
    parsed = urlsplit(path_part)
    if (path_part.startswith(("//",)) or parsed.scheme or parsed.netloc or
            path_part.startswith(("mailto:", "data:"))):
        return None, anchor, "external"
    if os.path.isabs(path_part):
        return os.path.normpath(path_part), anchor, "absolute"
    return os.path.normpath(os.path.join(src_dir, path_part)), anchor, "relative"


def _fallback_link_rel(source, source_real):
    """Stable collision-safe destination for absolute/traversing links."""
    digest = hashlib.sha256(source_real.encode("utf-8")).hexdigest()[:12]
    return os.path.join("linked_assets", digest, os.path.basename(source))


def materialize_local_links(packet_text, src_dir, out):
    """Recursively copy local Markdown destinations and rewrite every link.

    The initial packet text and every copied ``*.md`` are scanned with the
    pipeline's ``audit_all_markdown_links.destinations`` contract.  Relative
    hierarchy is preserved; absolute paths and traversal/collision targets use
    a content-addressed packet-local destination.  External links stay
    visible and are returned as explicit warnings.
    """
    src_dir = os.path.abspath(src_dir)
    out = os.path.abspath(out)
    copied = {}
    destination_sources = {}
    warnings = []

    def add_warning(kind, raw, detail):
        message = "%s：`%s`；%s" % (kind, raw, detail)
        if message not in warnings:
            warnings.append(message)

    def choose_rel(source, source_real, desired_rel):
        rel = os.path.normpath(desired_rel) if desired_rel else ""
        if (not rel or rel == os.pardir or rel.startswith(os.pardir + os.sep)
                or os.path.isabs(rel)):
            rel = _fallback_link_rel(source, source_real)
        prior = destination_sources.get(rel)
        destination = os.path.join(out, rel)
        existing_different = False
        if os.path.isfile(destination) and not prior:
            try:
                with open(destination, "rb") as existing_fh, open(source, "rb") as source_fh:
                    existing_different = existing_fh.read() != source_fh.read()
            except (OSError, UnicodeError):
                existing_different = True
        if (prior and prior != source_real) or os.path.isdir(destination) or existing_different:
            rel = _fallback_link_rel(source, source_real)
        prior = destination_sources.get(rel)
        if prior and prior != source_real:
            # A path-derived hash should already be unique, but keep a
            # deterministic suffix if an unusual collision is encountered.
            rel = os.path.join("linked_assets", hashlib.sha256(
                (source_real + "#2").encode("utf-8")).hexdigest()[:12],
                os.path.basename(source))
        destination_sources[rel] = source_real
        return rel

    def render_destination(rel, anchor, original_angle):
        new_dest = rel.replace(os.sep, "/")
        if anchor:
            new_dest += "#" + anchor
        use_angle = original_angle or any(ch.isspace() or ch in "()" for ch in new_dest)
        return "<%s>" % new_dest if use_angle else new_dest

    def materialize_file(source, desired_rel):
        source_real = os.path.realpath(source)
        if source_real in copied:
            return copied[source_real]
        rel = choose_rel(source, source_real, desired_rel)
        copied[source_real] = rel  # reserve before following cyclic MD links
        destination = os.path.join(out, rel)
        P.ensure_dirs(os.path.dirname(destination))
        if os.path.splitext(source)[1].lower() in (".md", ".markdown"):
            try:
                with open(source, encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, UnicodeError) as exc:
                add_warning("Markdown 源文件读取失败", source, repr(exc))
                return rel
            rewritten = rewrite_links(text, os.path.dirname(source), rel)
            with open(destination, "w", encoding="utf-8") as fh:
                fh.write(rewritten)
        else:
            shutil.copy2(source, destination)
        return rel

    def rewrite_links(text, current_src_dir, current_rel):
        replacements = []
        for start, end, raw, angle in _markdown_destination_spans(text):
            source, anchor, boundary = _link_source_path(current_src_dir, raw)
            if boundary == "fragment":
                continue
            if boundary == "external":
                add_warning("外部链接", raw, "保留原链接，未物化")
                continue
            if not source or not os.path.isfile(source):
                kind = "绝对本地链接" if boundary == "absolute" else "本地链接"
                add_warning(kind, raw, "未找到源文件，未物化")
                continue
            if boundary == "absolute":
                desired = None
                add_warning("绝对本地链接", raw, "已重写为 packet-local 文件")
            else:
                path_part = raw.strip()
                if path_part.startswith("<") and path_part.endswith(">"):
                    path_part = path_part[1:-1]
                path_part = unquote(path_part.split("#", 1)[0].split("?", 1)[0])
                desired = os.path.normpath(os.path.join(
                    os.path.dirname(current_rel), path_part))
            rel = materialize_file(source, desired)
            display_rel = os.path.relpath(rel, os.path.dirname(current_rel) or ".")
            replacements.append((start, end, render_destination(display_rel, anchor, angle)))
        for start, end, replacement in reversed(replacements):
            text = text[:start] + replacement + text[end:]
        return text

    rewritten = rewrite_links(packet_text, src_dir, "")
    return rewritten, warnings, copied


def copy_registered_asset(sp, out, rel_path):
    """Keep old basename copy and add the original relative path copy."""
    copied = False
    if not os.path.isfile(sp):
        return copied
    local_basename = os.path.join(out, "assets", os.path.basename(sp))
    P.ensure_dirs(os.path.dirname(local_basename))
    try:
        shutil.copy2(sp, local_basename)
        copied = True
    except Exception:
        pass
    # The packet's displayed asset path must also resolve locally.  Preserve
    # its hierarchy under packet.parent without replacing the legacy copy.
    local_rel = os.path.join(out, rel_path)
    P.ensure_dirs(os.path.dirname(local_rel))
    try:
        shutil.copy2(sp, local_rel)
        copied = True
    except Exception:
        pass
    return copied


def cmd_packet(a):
    fp, q = q_path(a.qid)
    if not fp:
        print("未找到:", a.qid)
        return 1
    out = a.out or os.path.join(P.OUT_ROOT, "packets", a.qid)
    P.ensure_dirs(out)
    body = open(fp, encoding="utf-8").read()
    secs = split_md(body)
    by = dict(secs)
    stem_title, stem_body = adopted_stem(body)
    links = [c for c in read_csv("rubric_links.csv") if c["question_id"] == a.qid]
    assets = [x for x in read_csv("assets.csv")
              if x["source_id"] in set([q["source_id"]] + [c["material_source_id"] for c in links])]
    smap = [s for s in (json.loads(l) for l in
                        open(os.path.join(P.INDEX_DIR, "source_map.jsonl"), encoding="utf-8"))
            if s["source_id"] == q["source_id"]]

    # 续修 2026-09-21：任务包只装"采用的题面小节"，答案/评分/讲评单列，不混入题目材料
    parts = ["# 任务包 %s\n" % a.qid, "> 生成自 DeepSeek 政治题库资料库\n"]
    emitted = set()
    if "身份信息" in by:
        parts.append("## 身份信息" + by["身份信息"])
        emitted.add("身份信息")
    if "读取指引（机器可读）" in by:
        parts.append("## 读取指引（机器可读）" + by["读取指引（机器可读）"])
        emitted.add("读取指引（机器可读）")
    if stem_title:
        parts.append("## 题面（%s）\n" % stem_title)
        parts.append(stem_body)
        emitted.add(stem_title)
    else:
        parts.append("\n> ⚠ 本题未取得可作题面的小节，题面须回原卷核实。\n")
    for title, section_body in secs:
        if title in STRUCTURE_SECTIONS and title != stem_title:
            parts.append("\n## %s%s" % (title, section_body))
            emitted.add(title)
    for role in ("e1", "e3", "student"):
        for title, section_body in role_sections(by, role, a.qid):
            parts.append("\n## %s" % packet_role_title(role, title) + section_body)
            emitted.add(title)
    for title in PASSTHROUGH_SECTIONS:
        if title in by:
            parts.append("\n## %s%s" % (title, by[title]))
            emitted.add(title)
    for title in UNKNOWN_ROLE_SECTIONS:
        if title in by:
            parts.append("\n## %s\n> ⚠ 原始角色未定；本段不得当作题面、E1、E3或学生层。\n%s" % (title, by[title]))
            emitted.add(title)
    if "候选评分材料（尚未确认，不得当作正式细则）" in by:
        parts.append("\n## 候选评分材料（尚未确认）"
                     + by["候选评分材料（尚未确认，不得当作正式细则）"])
        emitted.add("候选评分材料（尚未确认，不得当作正式细则）")
    append_unclassified(parts, secs, emitted)
    parts.append("\n## 来源表\n")
    parts.append("| source_id | 角色 | 文件 | 位置 |")
    parts.append("| --- | --- | --- | --- |")
    parts.append("| %s | %s | `%s` | %s |" % (q["source_id"], q["role"], q["rel_path"], q["line_range"]))
    for c in links:
        parts.append("| %s | %s（%s） | `%s` | 题号%s |" % (
            c["material_source_id"], c["material_role"], c["pair_status"],
            c["material_rel_path"], c["qnum"]))
    parts.append("\n## 评分材料状态\n")
    st = links[0]["exam_rubric_status"] if links else "暂未找到"
    parts.append("- rubric_status: **%s**" % st)
    if st in ("存在候选", "暂未找到"):
        parts.append("- **注意**：本题尚无已确认的正式评分材料，不得当作评分依据。")
    parts.append("\n## 所需图片资产（须显式打开，路径不等于已看见）\n")
    if assets:
        for x in assets[:60]:
            parts.append("- `%s`（%s，页/张 %s）" % (x["path"], x["kind"], x["page"]))
    else:
        parts.append("（无登记资产）")
    parts.append("\n## 来源映射（该来源逐页/逐张定位）\n")
    for s in smap[:200]:
        parts.append("- %s=%s → `%s`%s [%s]" % (
            s["locator_type"], s["locator"], s["md_path"], s.get("md_anchor", ""),
            s["verify_status"]))
    # 拷贝引用资产
    copied = 0
    for x in assets:
        sp = os.path.join(P.OUT_ROOT, x["path"])
        if copy_registered_asset(sp, out, x["path"]):
            copied += 1
    packet_text, link_warnings, _ = materialize_local_links(
        "\n".join(parts), os.path.dirname(fp), out)
    if link_warnings:
        packet_text += "\n## 本地链接物化警告\n"
        packet_text += "".join("- %s\n" % x for x in link_warnings)
    with open(os.path.join(out, "packet.md"), "w", encoding="utf-8") as fh:
        fh.write(packet_text)
    print("任务包已生成:", os.path.join(out, "packet.md"))
    print("  关联材料 %d 条；资产 %d 项（已复制 %d）" % (len(links), len(assets), copied))
    print("  评分材料状态:", st)
    return 0


def cmd_verify(a):
    need = ["source_manifest.csv", "exam_files.csv", "exams.csv", "questions.csv",
            "rubric_links.csv", "assets.csv", "source_map.jsonl"]
    ok = True
    for n in need:
        p = os.path.join(P.INDEX_DIR, n)
        e = os.path.isfile(p) and os.path.getsize(p) > 0
        ok = ok and e
        print(("OK   " if e else "MISS ") + n)
    for d in ["processed_markdown", "questions", "assets", "evidence", "validation", "scripts"]:
        p = os.path.join(P.OUT_ROOT, d)
        print(("OK   " if os.path.isdir(p) else "MISS ") + d + "/")
    print("结果:", "通过" if ok else "存在缺失")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("list"); p.add_argument("--year"); p.add_argument("--region")
    p.add_argument("--stage"); p.add_argument("--type"); p.add_argument("--status")
    p.add_argument("--count", action="store_true"); p.set_defaults(f=cmd_list)
    sub.add_parser("exams").set_defaults(f=cmd_exams)
    p = sub.add_parser("get"); p.add_argument("qid")
    p.add_argument("--all", action="store_true", help="输出全部原文小节（含答案/评分/讲评）")
    p.add_argument("--with-rubric", action="store_true",
                   help="在题面之外一并输出评分材料/参考答案/来源定位/质量标记")
    p.set_defaults(f=cmd_get)
    p = sub.add_parser("search"); p.add_argument("keyword"); p.set_defaults(f=cmd_search)
    p = sub.add_parser("packet"); p.add_argument("qid"); p.add_argument("-o", "--out")
    p.set_defaults(f=cmd_packet)
    sub.add_parser("verify").set_defaults(f=cmd_verify)
    a = ap.parse_args()
    if not getattr(a, "f", None):
        ap.print_help()
        return 0
    return a.f(a) or 0


if __name__ == "__main__":
    sys.exit(main())
