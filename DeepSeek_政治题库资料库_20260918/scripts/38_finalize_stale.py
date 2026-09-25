#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""续修 2026-09-21 · 收口（v2）：按小节精确修正头/尾配对状态。

v1 用 count=1 替换整篇第一处 rubric_status，命中了头部而非尾部。本版按小节定位：
  - 旧残留文件（未入索引）：头部「配对状态」与尾部「质量标记」**同时**改为
    显式「不适用（旧残留文件…）」，消除互相矛盾且不误导下游；
  - BJ-2026-FT-YIMO-Q5：头部与尾部同时改为派生值「暂未找到」，并注明旧值为假阳性。
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

REF = "validation/续修_20260921/五个未入索引文件_定性.md"
STALE_IDS = ["BJ-2023-HD-ERMO-Q1", "BJ-2023-HD-ERMO-Q3",
             "BJ-2024-HD-QIZHONG-Q0", "BJ-2026-FT-ERMO-Q20"]

STALE_LINE = ("- rubric_status: **不适用（旧残留文件，未入 indexes/questions.csv，"
              "不参与索引与统计口径）**；旧值来自早期 10_pair 运行，非本轮派生。"
              "定性见 `%s`" % REF)


def split_sections(md):
    ms = list(re.finditer(r"^## (.+)$", md, re.M))
    out = []
    for i, m in enumerate(ms):
        e = ms[i + 1].start() if i + 1 < len(ms) else len(md)
        out.append((m.group(1).strip(), m.start(), m.end(), md[m.end():e]))
    return out


def set_in_section(md, section_titles, new_line):
    """在指定小节内替换 rubric_status 行（整篇只改这些小节）。"""
    secs = split_sections(md)
    out, last = [], 0
    for title, _s, e, body in secs:
        out.append(md[last:e])
        if title in section_titles:
            body = re.sub(r"^- rubric_status: .*$", new_line, body, count=1, flags=re.M)
        out.append(body)
        last = e + len(body)
    out.append(md[last:])
    return "".join(out)


def main():
    changed = []
    for qid in STALE_IDS:
        hits = glob.glob(os.path.join(P.Q_DIR, "*", "%s.md" % qid))
        if not hits:
            print("!! 未找到", qid)
            continue
        fp = hits[0]
        md = open(fp, encoding="utf-8").read()
        md2 = set_in_section(md, {"配对状态", "质量标记"}, STALE_LINE)
        if md2 != md:
            open(fp, "w", encoding="utf-8").write(md2)
            changed.append(qid)
            print("已同步头尾为『不适用』:", qid)

    fp = os.path.join(P.Q_DIR, "BJ-2026-FT-YIMO", "BJ-2026-FT-YIMO-Q5.md")
    md = open(fp, encoding="utf-8").read()
    q5_line = ("- rubric_status: **暂未找到**"
               "（与头部配对状态同源；旧值『已匹配正式材料』系自比自的假阳性——"
               "旧“题干”本身就取自该细则文本）")
    md2 = set_in_section(md, {"配对状态", "质量标记"}, q5_line)
    if md2 != md:
        open(fp, "w", encoding="utf-8").write(md2)
        changed.append("BJ-2026-FT-YIMO-Q5")
        print("已同步 Q5 头尾为派生值:", "暂未找到")

    json.dump({"已处理": changed,
               "说明": "旧残留文件头尾同时标为『不适用』；Q5 头尾同时为派生值『暂未找到』"},
              open(os.path.join(P.VAL_DIR, "续修_20260921", "38_收口记录.json"),
                   "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
