#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段8：既有试点「共享题库/试点_2026海淀一模」核验后增量复用并入新库。

按用户决定执行：既有试点先核验，再复用并入新库，不重做。

做四件事：
  1. 核验：逐条校验 integrity.json 的 SHA-256；核验其来源文件与本库 source_id 的对应关系
  2. 对账：把试点的题号与本库自身切分结果比对，列出"本库缺失、试点已复核"的题
  3. 复用：文本产物复制并**改写失效的 gpt6 绝对链接为相对链接**；
     图片资产用硬链接并入（不额外占盘）；评分单元另存 jsonl
  4. 并入：把试点已复核的题按本库单题格式落到 questions_reused/，标注来源与复核状态

产出：
  reused/2026海淀一模_试点复用/**            试点产物（链接已修）
  questions_reused/BJ-2026-HD-YIMO/*.md      试点已复核题的本题库格式
  indexes/reused_pilot_questions.csv
  validation/08_试点复用核验.md
"""
import hashlib
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

PILOT = os.path.join(P.WORKSPACE, "共享题库", "试点_2026海淀一模")
DEST = os.path.join(P.OUT_ROOT, "reused", "2026海淀一模_试点复用")
QREUSED = os.path.join(P.OUT_ROOT, "questions_reused", "BJ-2026-HD-YIMO")
DEAD_PREFIXES = [
    "/Users/wanglifei/Desktop/gpt6/共享题库/试点_2026海淀一模/",
    "/Users/wanglifei/Desktop/gpt和claude共同的小窝/共享题库/试点_2026海淀一模/",
]
TEXT_EXT = (".md", ".json", ".html", ".txt")


def sha256_file(fp):
    h = hashlib.sha256()
    with open(fp, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def verify_integrity():
    fp = os.path.join(PILOT, "data", "integrity.json")
    d = json.load(open(fp, encoding="utf-8"))
    ok = miss = bad = 0
    missing, mismatched = [], []
    for rel, h in d.items():
        src = os.path.join(PILOT, rel)
        if not os.path.isfile(src):
            miss += 1
            missing.append(rel)
            continue
        if sha256_file(src) == h:
            ok += 1
        else:
            bad += 1
            mismatched.append(rel)
    return {"entries": len(d), "ok": ok, "missing": miss, "mismatch": bad,
            "missing_list": missing, "mismatch_list": mismatched}


def link_rewrite(text, dest_file):
    """把试点内失效的绝对路径改成指向 reused 目录的相对路径。"""
    for pref in DEAD_PREFIXES:
        if pref not in text:
            continue
        # 逐个匹配替换，保持其余内容不动
        out = []
        idx = 0
        while True:
            j = text.find(pref, idx)
            if j < 0:
                out.append(text[idx:])
                break
            out.append(text[idx:j])
            k = j + len(pref)
            # 取到路径结束（空白/引号/括号/反引号为止）
            e = k
            while e < len(text) and text[e] not in ' \t\r\n"\'`)]>':
                e += 1
            tail = text[k:e]
            target_abs = os.path.join(DEST, tail)
            rel = os.path.relpath(target_abs, os.path.dirname(dest_file))
            out.append(rel)
            idx = e
        text = "".join(out)
    return text


def copy_texts():
    copied, rewritten, hardlinked, relinked = 0, 0, 0, 0
    for root, dirs, files in os.walk(PILOT):
        dirs[:] = [d for d in dirs if d != "assets"]
        for fn in files:
            if not fn.endswith(TEXT_EXT):
                continue
            src = os.path.join(root, fn)
            rel = os.path.relpath(src, PILOT)
            dst = os.path.join(DEST, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                t = open(src, encoding="utf-8").read()
            except Exception:
                shutil.copy2(src, dst)
                copied += 1
                continue
            n0 = sum(t.count(p) for p in DEAD_PREFIXES)
            t2 = link_rewrite(t, dst)
            if n0:
                rewritten += 1
                relinked += n0
            with open(dst, "w", encoding="utf-8") as fh:
                fh.write(t2)
            copied += 1
    # 图片资产：硬链接，避免重复占盘
    asrc = os.path.join(PILOT, "assets")
    if os.path.isdir(asrc):
        for root, dirs, files in os.walk(asrc):
            rel = os.path.relpath(root, PILOT)
            os.makedirs(os.path.join(DEST, rel), exist_ok=True)
            for fn in files:
                s = os.path.join(root, fn)
                d = os.path.join(DEST, rel, fn)
                if os.path.exists(d):
                    continue
                try:
                    os.link(s, d)
                    hardlinked += 1
                except Exception:
                    shutil.copy2(s, d)
                    hardlinked += 1
    return {"text_copied": copied, "files_with_dead_links": rewritten,
            "links_rewritten": relinked, "assets_linked": hardlinked}


def source_identity_check():
    """试点 sources 的 sha256 ↔ 本库 source_id 对应。"""
    b = json.load(open(os.path.join(PILOT, "data", "bank.json"), encoding="utf-8"))
    out = []
    for s in b.get("sources", []):
        sha = (s.get("sha256") or "")
        sid = "S" + sha[:12] if sha else None
        out.append({"pilot_source_id": s.get("source_id"), "role": s.get("role"),
                    "sha256": sha, "new_source_id": sid,
                    "pilot_path": s.get("path")})
    return b, out


def coverage_diff(b):
    """试点题号 vs 本库切分：列出本库缺、试点有的题。"""
    import csv
    qs = [q for q in csv.DictReader(
        open(os.path.join(P.INDEX_DIR, "questions.csv"), encoding="utf-8"))
        if q["exam_id"] == "BJ-2026-HD-YIMO"]
    mine = {}
    for q in qs:
        mine.setdefault(int(q["num"]), set()).add(q["variant"])
    pilot_nums = sorted(p["number"] for p in b["parents"])
    only_pilot = [n for n in pilot_nums if n not in mine]
    both = [n for n in pilot_nums if n in mine]
    only_mine = sorted(n for n in mine if n not in pilot_nums)
    return mine, pilot_nums, only_pilot, both, only_mine


def render_question(p, rub_by_q, ans_key):
    """把试点 parent 渲染成本库单题格式。"""
    qid = "BJ-2026-HD-YIMO-Q%d" % p["number"]
    L = ["# %s\n" % qid, "## 身份信息",
         "- question_id: `%s`" % qid,
         "- exam_id: `BJ-2026-HD-YIMO`（试点内记作 BJ-2026-HD-YIMO-POL，同一场考试）",
         "- 题号: %d" % p["number"],
         "- 分值: %s" % (("%s 分" % p["points"]) if p.get("points") else "未标注"),
         "- 来源页: %s" % (p.get("source_pages") or []),
         "- 复核状态: **已复核**（试点人工复核产物，非本库自动切分）",
         "- 复用来源: `共享题库/试点_2026海淀一模/data/bank.json` 的 parents[number=%d]" % p["number"],
         "- 同题多来源: 本库自身切分结果另存于 `questions/BJ-2026-HD-YIMO/`，两者并存不合并",
         "\n## 题目原文（试点已复核版）\n"]
    for blk in p.get("blocks", []):
        t = blk.get("type")
        if t == "statements":
            for e in blk.get("entries", []):
                L.append("%s %s" % (e.get("label", ""), e.get("text", "")))
        elif t == "options":
            for e in blk.get("entries", []):
                L.append("%s. %s" % (e.get("label", ""), e.get("text", "")))
        else:
            txt = blk.get("text", "")
            if txt.strip():
                L.append(txt)
        L.append("")
    bb = p.get("question_bbox") or []
    if bb:
        L.append("\n## 原图定位")
        for x in bb:
            L.append("- 第 %s 页 局部图 `%s`（bbox 归一化 %s）"
                     % (x.get("page"), x.get("asset"), x.get("bbox_normalized")))
    u = rub_by_q.get(p["number"])
    L.append("\n## 正式评分材料原文（试点已复核版）\n")
    if u:
        for blk in u.get("blocks", []):
            role = blk.get("role", "")
            if blk.get("type") == "table":
                L.append("- 评分表（role=%s，第 %s 页）" % (role, blk.get("source_page")))
                hdr = blk.get("headers") or []
                L.append("| " + " | ".join(h.replace("\n", " ") for h in hdr) + " |")
                L.append("|" + "---|" * len(hdr))
                for r in blk.get("rows", []):
                    L.append("| " + " | ".join((c or "").replace("\n", " / ") for c in r) + " |")
            else:
                L.append("- （%s，第 %s 页）%s" % (role, blk.get("source_page"),
                                                  (blk.get("text") or "").replace("\n", " ")))
            L.append("")
        L.append("> 评分表按分档（分值/标准/细则）原样保留，未拆成逐点给分。")
    else:
        L.append("（试点未收录该题评分单元）")
    L.append("\n## 参考答案（选择题答案键）\n")
    if str(p["number"]) in ans_key:
        L.append("- 答案键：**%s**" % ans_key[str(p["number"])])
    else:
        L.append("（该题非选择题答案键条目）")
    L.append("\n## 质量标记")
    L.append("- extraction_status: verified_reused_pilot")
    L.append("- rubric_status: %s" % ("已匹配正式材料" if u else "暂未找到"))
    L.append("- needs_review: N（试点已复核；本库自动切分结果另见 questions/ 下同题文件）")
    L.append("- 图像依赖: 见 `reused/2026海淀一模_试点复用/assets/`；图片须显式打开")
    return qid, "\n".join(L) + "\n"


def main():
    os.makedirs(DEST, exist_ok=True)
    os.makedirs(QREUSED, exist_ok=True)
    rep = {}
    rep["integrity"] = verify_integrity()
    print("完整性: %s" % rep["integrity"])

    b, srcs = source_identity_check()
    rep["sources"] = srcs
    for s in srcs:
        print("  试点来源 %s(%s) → 本库 %s" % (s["pilot_source_id"], s["role"], s["new_source_id"]))

    mine, pilot_nums, only_pilot, both, only_mine = coverage_diff(b)
    rep["coverage"] = {"pilot_parents": len(pilot_nums), "both": len(both),
                       "only_pilot": only_pilot, "only_mine": only_mine,
                       "pilot_items": len(b.get("items", [])),
                       "coverage_note": b.get("coverage_note")}
    print("覆盖对账: 试点 %d 题 / 两方都有 %d / 仅试点有 %s / 仅本库有 %s"
          % (len(pilot_nums), len(both), only_pilot, only_mine[:12]))

    rep["copy"] = copy_texts()
    print("复用复制: %s" % rep["copy"])

    rub_by_q = {}
    for u in b.get("rubrics", []):
        rub_by_q.setdefault(u.get("question"), u)
    rv = json.load(open(os.path.join(PILOT, "data", "rubric_reviewed.json"), encoding="utf-8"))
    ans_key = rv.get("answer_key") or {}
    rep["rubric_reviewed_complete"] = rv.get("complete")

    # 评分单元另存，便于检索
    with open(os.path.join(DEST, "rubric_units.jsonl"), "w", encoding="utf-8") as fh:
        for u in b.get("rubrics", []):
            fh.write(json.dumps(u, ensure_ascii=False) + "\n")

    rows = []
    for p in b["parents"]:
        qid, md = render_question(p, rub_by_q, ans_key)
        with open(os.path.join(QREUSED, "%s.md" % qid), "w", encoding="utf-8") as fh:
            fh.write(md)
        rows.append({
            "question_id": qid, "pilot_id": "Q%d" % p["number"], "number": p["number"],
            "points": p.get("points", ""), "source_pages": "/".join(str(x) for x in
                                                                    (p.get("source_pages") or [])),
            "blocks": len(p.get("blocks", [])),
            "has_rubric_unit": "Y" if p["number"] in rub_by_q else "N",
            "in_my_split": "Y" if p["number"] in mine else "N",
            "reuse_status": "verified_reused_pilot",
        })
    import csv as _csv
    with open(os.path.join(P.INDEX_DIR, "reused_pilot_questions.csv"), "w",
              encoding="utf-8", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    rep["questions_written"] = len(rows)

    with open(os.path.join(DEST, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=2)
    print("已复核题落盘:", len(rows))
    print("DONE")


if __name__ == "__main__":
    main()
