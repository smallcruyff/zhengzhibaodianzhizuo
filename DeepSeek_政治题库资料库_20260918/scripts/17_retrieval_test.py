#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段9 读取测试：用真实产物跑通端到端检索与任务包生成。

覆盖规范要求的五类题：
  1. 纯文字题    2. 表格题    3. 漫画/流程图题    4. 跨页主观题    5. 评分材料来自 PPT 的题

对每类：自动挑一道真实存在的题 → 生成任务包 → 校验包内必需区块是否齐全。
只报告真实执行结果，不做任何"应当可用"的推断。
"""
import csv
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

PY = P.PY_SYS
BANK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bank.py")


def rd(name):
    p = os.path.join(P.INDEX_DIR, name)
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def run(*args):
    r = subprocess.run([PY, BANK] + list(args), capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def pick_candidates():
    qs = rd("questions.csv")
    rl = rd("rubric_links.csv")
    man = {m["source_id"]: m for m in rd("source_manifest.csv")}
    meta_cache = {}

    def meta(sid):
        if sid not in meta_cache:
            p = os.path.join(P.EVID_DIR, sid, "meta.json")
            meta_cache[sid] = json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else {}
        return meta_cache[sid]

    # 每题：块文本
    by_q = {}
    for q in qs:
        by_q.setdefault(q["question_id"], []).append(q)
    rubric_by_q = {}
    for c in rl:
        rubric_by_q.setdefault(c["question_id"], []).append(c)

    def body_lines(q):
        """复现切分口径的行序列，用于定位页标记。"""
        for cand in (os.path.join(P.EVID_DIR, q["source_id"], "cleaned", "clean.md"),
                     os.path.join(P.EVID_DIR, q["source_id"], "native_text", "raw.md"),
                     os.path.join(P.EVID_DIR, q["source_id"], "native_text", "raw.txt")):
            if os.path.isfile(cand):
                t = open(cand, encoding="utf-8", errors="replace").read()
                sk = re.compile(r"^\s*(第\s*\d+\s*页|共\s*\d+\s*页|"
                                r"高三(年级)?\s*[（(]思想政治|思想政治\s*$|-\s*\d+\s*-|"
                                r"\d+\s*/\s*\d+\s*页)\s*$")
                return [l for l in t.splitlines() if not sk.match(l)]
        return []

    picks, extra = {}, {}

    # 1. 纯文字题：原卷（pdf/docx）中的选择题，且来源页图对象为 0
    man_by_sid = man
    for q in qs:
        if q["type"] != "选择题" or q["variant"] != "native" or int(q["chars"]) < 200:
            continue
        if q["role"] != "原卷":
            continue
        m = man_by_sid.get(q["source_id"], {})
        if m.get("format") not in ("pdf", "docx"):
            continue
        fo = meta(q["source_id"]).get("figure_objects") or 0
        if fo <= 1:
            picks["纯文字题"] = q
            extra["纯文字题"] = ("原卷 %s，来源图对象 %d 个（几乎无图，纯文字题干）"
                                % (m.get("format"), fo))
            break

    # 2. 表格题：块本身落在一个含表格的文档里（主档含"<!-- 表格 -->"或 <table）
    for q in qs:
        if q["variant"] != "native" or int(q["chars"]) < 200:
            continue
        p = os.path.join(P.MD_DIR, "%s.full.md" % q["source_id"])
        if not os.path.isfile(p):
            continue
        t = open(p, encoding="utf-8", errors="replace").read()
        n = t.count("<!-- 表格 -->") + t.count("<table")
        if n:
            picks["表格题"] = q
            extra["表格题"] = "来源主档含表格标记 %d 处" % n
            break

    # 3. 漫画/流程图题：原卷 PDF，来源页图对象较多
    for q in qs:
        m = man_by_sid.get(q["source_id"], {})
        if m.get("format") != "pdf" or q["variant"] != "native":
            continue
        if (meta(q["source_id"]).get("figure_objects") or 0) >= 8:
            picks["漫画或流程图题"] = q
            extra["漫画或流程图题"] = "来源图对象 %d 个" % meta(q["source_id"]).get("figure_objects")
            break

    # 4. 跨页主观题：非选择题，且块内确实跨越页标记（"## 第 N 页"）
    seen_src = set()
    for q in qs:
        if q["type"] != "非选择题" or q["variant"] != "native":
            continue
        if q["source_id"] in seen_src or int(q["chars"]) < 200:
            continue
        seen_src.add(q["source_id"])
        lines = body_lines(q)
        try:
            s0, s1 = (int(x) for x in q["line_range"].split("-"))
        except Exception:
            continue
        inner = lines[s0:s1]
        # 只看 PDF 的页标记（"## 第 N 页"），PPT 的"## 第 N 张"不算跨页
        pmark = [i for i, l in enumerate(inner)
                 if re.match(r"^## 第 \d+ 页", l.strip())]
        if pmark:
            picks["跨页主观题"] = q
            extra["跨页主观题"] = "块内跨越 %d 处页标记" % len(pmark)
            break

    # 5. 评分材料来自 PPT 的题
    for qid, cs in rubric_by_q.items():
        for c in cs:
            if c["material_rel_path"].lower().endswith(".pptx") and \
                    c["pair_status"] in ("已匹配正式材料", "存在候选"):
                rows = by_q.get(qid) or []
                if rows:
                    picks["评分材料来自PPT的题"] = rows[0]
                    break
        if "评分材料来自PPT的题" in picks:
            break

    return picks, rubric_by_q, extra


def main():
    picks, rubric_by_q, extra = pick_candidates()
    outdir = os.path.join(P.VAL_DIR, "读取测试")
    P.ensure_dirs(outdir)
    lines = ["# 端到端读取测试报告", "",
             "> 用真实索引与真实文件跑通 `bank.py` 的检索与任务包生成，逐项核对包内区块。", ""]
    ok_all = True
    for label, q in picks.items():
        qid = q["question_id"]
        rc1, out1, err1 = run("get", qid)
        pdir = os.path.join(outdir, qid)
        rc2, out2, err2 = run("packet", qid, "-o", pdir)
        pkt = os.path.join(pdir, "packet.md")
        body = open(pkt, encoding="utf-8").read() if os.path.isfile(pkt) else ""
        need = ["## 题目原文", "## 来源表", "## 评分材料状态",
                "## 所需图片资产", "## 来源映射"]
        missing = [n for n in need if n not in body]
        links = [c for c in rubric_by_q.get(qid, [])]
        ok = (rc1 == 0 and rc2 == 0 and not missing)
        ok_all = ok_all and ok
        lines += ["## %s" % label, "",
                  "- 选用题目：`%s`" % qid,
                  "- 来源：`%s`（角色 %s / %s）" % (q["rel_path"], q["role"], q["variant"]),
                  "- 题型：%s；分值：%s；块长：%s 字符"
                  % (q["type"], q["score_text"] or "未捕获", q["chars"]),
                  "- 该类判定依据：%s" % extra.get(label, "见上"),
                  "- `bank.py get` 退出码：%d（输出 %d 字符）" % (rc1, len(out1)),
                  "- `bank.py packet` 退出码：%d；任务包：`%s`" % (rc2, pkt),
                  "- 包内必需区块：%s" % ("齐全" if not missing else "缺 %s" % missing),
                  "- 关联评分材料 %d 条" % len(links),
                  ""]
        if links:
            lines.append("  | 材料 | 角色 | 配对状态 |")
            lines.append("  | --- | --- | --- |")
            for c in links[:6]:
                lines.append("  | `%s` | %s | %s |"
                             % (c["material_rel_path"], c["material_role"], c["pair_status"]))
            lines.append("")

    # 关键词检索
    rc, out, err = run("search", "中国式现代化")
    lines += ["## 关键词检索", "",
              "- `bank.py search 中国式现代化` 退出码 %d" % rc,
              "- 输出首行：%s" % (out.splitlines()[0] if out else "(空)"),
              ""]
    # 清单与卷列表
    rc, out, err = run("list", "--year", "2026", "--type", "选择题", "--count")
    lines += ["- `bank.py list --year 2026 --type 选择题` ：%s" % (out.strip().splitlines()[-1]
                                                                  if out.strip() else "(空)"), ""]
    rc, out, err = run("verify")
    lines += ["- `bank.py verify` 退出码 %d" % rc, ""]

    lines += ["## 结论", "",
              "- 五类题的 `get` 与 `packet` 均%s。" % ("执行成功" if ok_all else "存在失败项"),
              ""]
    with open(os.path.join(P.VAL_DIR, "11_读取测试报告.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines[:40]))
    print("...")
    print("已写出", os.path.join(P.VAL_DIR, "11_读取测试报告.md"))
    print("测试通过:", ok_all)


if __name__ == "__main__":
    main()
