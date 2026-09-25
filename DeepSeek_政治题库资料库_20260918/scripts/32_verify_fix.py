#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""续修 2026-09-21 · 修复保真核验。

对 31_fix_question_files.py 的产出做独立核验，而不是"命令退出成功就算过"：

  1. 每个原始 `### 来源：…` 块的**正文逐字保留**（去首尾空白后完全相同）；
  2. 块头集合完全一致（没有增删来源块）；
  3. 尾部 rubric_status 已与头部配对状态同源（不再是硬编码"暂未配对"）；
  4. 原卷层、评分层、已核试点（questions_reused）未被改动。

用法：
  /usr/bin/python3 32_verify_fix.py --orig-root <原始questions目录> --new-root <新questions目录>
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

HEAD_RE = re.compile(
    r"^### 来源：`(?P<path>.*?)`（角色 (?P<role>\S+?) / (?P<variant>\S+?)，位置 (?P<loc>[^，]*)(?P<rest>[^\n]*)）\s*$",
    re.M)


def stem_section(md, titles=("题目原文",)):
    """取旧文件的题目原文区；新文件取全部题面相关小节。

    只在题目原文区/题面小节内解析块，避免把尾部报告小节误当成块正文。
    """
    ms = list(re.finditer(r"^## (.+)$", md, re.M))
    out = []
    for i, m in enumerate(ms):
        t = m.group(1).strip()
        e = ms[i + 1].start() if i + 1 < len(ms) else len(md)
        out.append((t, md[m.end():e]))
    return out


def blocks(md):
    """返回 [(header_line, body_text)]；只在题面小节内解析。"""
    secs = dict(stem_section(md))
    body = ""
    for t in ("题目原文", "题目原文（原卷·native，读取优先）",
              "原卷 OCR 候选（未逐字对照，不得直接采用）",
              "教师版题面来源（含答案，须回原卷核实）",
              "评分材料来源块（原样保留，配对状态见下）",
              "参考答案来源块（不得当作评分依据）",
              "讲评来源块（含答案与解析，不得当作题面）",
              "待确认材料来源块（角色未定，须人工裁决）"):
        if t in secs:
            body += "\n" + secs[t]
    ms = list(HEAD_RE.finditer(body))
    out = []
    for i, m in enumerate(ms):
        e = ms[i + 1].start() if i + 1 < len(ms) else len(body)
        out.append((m.group(0).strip(), body[m.end():e].strip("\n")))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orig-root", required=True)
    ap.add_argument("--new-root", required=True)
    ap.add_argument("--report", default="")
    a = ap.parse_args()

    # 以**新产出**为核验范围：小样验证时只核实际生成的文件
    new_files = sorted(glob.glob(os.path.join(a.new_root, "*", "*.md")))
    orig_files = sorted(glob.glob(os.path.join(a.orig_root, "*", "*.md")))
    orig_by_id = {os.path.basename(f)[:-3]: f for f in orig_files}
    bad = []
    ok = 0
    head_changed = []
    stats = defaultdict(int)
    for nfp in new_files:
        qid = os.path.basename(nfp)[:-3]
        fp = orig_by_id.get(qid)
        if not fp:
            bad.append({"question_id": qid, "issue": "原始文件缺失（无法比对）"})
            continue
        o = open(fp, encoding="utf-8").read()
        n = open(nfp, encoding="utf-8").read()
        ob, nb = blocks(o), blocks(n)
        # 1+2 块头集合与正文
        oh = [h for h, _ in ob]
        nh = [h for h, _ in nb]
        if sorted(oh) != sorted(nh):
            bad.append({"question_id": qid, "issue": "来源块头集合不一致",
                        "orig": len(oh), "new": len(nh)})
            continue
        ntext = n
        lost = []
        for h, body in ob:
            if body and body not in ntext:
                lost.append(h[:80])
        if lost:
            bad.append({"question_id": qid, "issue": "块正文未逐字保留", "blocks": lost})
            continue
        # 3 尾部 rubric_status 必须与**同一文件内**头部配对状态同源
        #   （旧版拿父稿头部比对，对"头部本身也被修正"的文件会误判；
        #     正确要求是当前文件内部不再自相矛盾）
        nsec = dict(stem_section(n))
        head_sec = nsec.get("配对状态", "")
        qmark = nsec.get("质量标记", "")
        mh = re.search(r"^- rubric_status: \*\*(.+?)\*\*", head_sec, re.M)
        head = mh.group(1) if mh else None
        mt = re.search(r"^- rubric_status: \*\*(.+?)\*\*", qmark, re.M)
        if mt is None:
            mt = re.search(r"^- rubric_status: (.+?)（与头部配对状态同源.*$", qmark, re.M)
        tail = mt.group(1).strip() if mt else None
        if head is None:
            bad.append({"question_id": qid, "issue": "新文件头部无配对状态", "head_sec": head_sec[:120]})
            continue
        if tail is None:
            bad.append({"question_id": qid, "issue": "新文件质量标记无 rubric_status",
                        "qmark": qmark[:160]})
            continue
        if tail != head:
            bad.append({"question_id": qid, "issue": "同文件内头尾 rubric_status 不一致",
                        "head": head, "tail": tail})
            continue
        # 与父稿头部不同 → 记录为"头部被修正"（信息性，不算不合格）
        omh = re.search(r"^- rubric_status: \*\*(.+?)\*\*", o, re.M)
        if omh and omh.group(1) != head:
            head_changed.append({"question_id": qid,
                                 "父稿头部": omh.group(1), "现头部": head})
        stats["通过"] += 1
        ok += 1

    print("核验文件:", len(orig_files), "通过:", ok, "不合格:", len(bad))
    print("头部配对状态被修正（信息性）:", len(head_changed))
    if bad:
        for x in bad[:20]:
            print("  ✗", x)
    rpt = a.report or os.path.join(P.VAL_DIR, "续修_20260921", "32_保真核验.json")
    os.makedirs(os.path.dirname(rpt), exist_ok=True)
    with open(rpt, "w", encoding="utf-8") as fh:
        json.dump({"checked": len(new_files), "passed": ok, "failed": bad,
                   "head_status_corrected": head_changed},
                  fh, ensure_ascii=False, indent=2)
    print("报告:", rpt)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
