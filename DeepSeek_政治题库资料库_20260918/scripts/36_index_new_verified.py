#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""续修 2026-09-21 · B5-1 收口：丰台一模补建题的索引登记与孤儿定性更新。

1. 把本轮按原页补建的 5 题（Q5/Q7/Q9/Q14/Q21）登记进 indexes/questions.csv，
   variant 标为 `verified_from_page`，extraction_status=verified，
   并注明来源为原页核验补建（非自动切分）。
2. 更新 BJ-2026-FT-YIMO-Q5 的定性登记：原『错误题键』已由原页补建的真 Q5 题面取代，
   旧内容原样保留在『评分材料来源块』中。
3. 重新生成 五个未入索引文件_定性.json/.md（Q5 已解决，余 4 项）。
"""
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

EXAM = "BJ-2026-FT-YIMO"
SID = "S6e8f2df5ef86"
RELPATH = "2026模拟题/2026各区一模/2026丰台一模/试卷/试卷.pdf"

NEW_ROWS = [
    # qid, num, type, score_text, score_value, subq, page, option_marks
    ("BJ-2026-FT-YIMO-Q5", 5, "选择题", "", "", "", 2, 4),
    ("BJ-2026-FT-YIMO-Q7", 7, "选择题", "", "", "", 2, 4),
    ("BJ-2026-FT-YIMO-Q9", 9, "选择题", "", "", "", 3, 4),
    ("BJ-2026-FT-YIMO-Q14", 14, "选择题", "", "", "", 4, 4),
    ("BJ-2026-FT-YIMO-Q21", 21, "非选择题", "（9分）", "9", "", 10, 0),
]

COLS = ["question_id", "exam_id", "num", "type", "type_source", "score_text", "score_value",
        "subq_hint", "source_id", "role", "variant", "rel_path", "line_range", "chars",
        "option_marks", "needs_review", "extraction_status"]


def main():
    qcsv = os.path.join(P.INDEX_DIR, "questions.csv")
    rows = list(csv.DictReader(open(qcsv, encoding="utf-8")))
    have = set(r["question_id"] for r in rows)
    added = []
    for qid, num, typ, stext, sval, subq, page, om in NEW_ROWS:
        if qid in have:
            continue
        fp = os.path.join(P.Q_DIR, EXAM, "%s.md" % qid)
        chars = len(open(fp, encoding="utf-8").read()) if os.path.isfile(fp) else 0
        rows.append({
            "question_id": qid, "exam_id": EXAM, "num": str(num), "type": typ,
            "type_source": "原页核验补建（B5-1 丰台一模试卷逐页校对）",
            "score_text": stext, "score_value": sval, "subq_hint": subq,
            "source_id": SID, "role": "原卷", "variant": "verified_from_page",
            "rel_path": RELPATH, "line_range": "p%d" % page, "chars": str(chars),
            "option_marks": str(om), "needs_review": "N",
            "extraction_status": "verified",
        })
        added.append(qid)
    with open(qcsv, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("新增索引行:", len(added), added)

    # 更新 Q5 的定性横幅
    fp = os.path.join(P.Q_DIR, EXAM, "BJ-2026-FT-YIMO-Q5.md")
    md = open(fp, encoding="utf-8").read()
    old = re.search(r"^> \*\*定性登记（续修 2026-09-21[^\n]*\n", md, re.M)
    if old:
        new = ("> **定性登记（续修 2026-09-21）**：原为错误题键（细则阅卷问题枚举）"
               "＋真实题面缺口。**已于 B5-1 解决**：按原页（`evidence/%s/pages/p002.png`）"
               "补建真第 5 题题面，旧错误内容原样保留在下方『评分材料来源块』中，未删除。"
               "详见 `validation/续修_20260921/五个未入索引文件_定性.md`。\n" % SID)
        md = md[:old.start()] + new + md[old.end():]
        with open(fp, "w", encoding="utf-8") as fh:
            fh.write(md)
        print("已更新 Q5 定性横幅")

    # 重新生成定性清单（Q5 已解决）
    jp = os.path.join(P.VAL_DIR, "续修_20260921", "五个未入索引文件_定性.json")
    d = json.load(open(jp, encoding="utf-8"))
    for item in d["明细"]:
        if item["question_id"] == "BJ-2026-FT-YIMO-Q5":
            item["状态"] = "已解决（B5-1：按原页补建真题面，索引已登记）"
            item["分类"] = "原错误题键已取代；真第5题题面已按原页补建"
            item["是否真缺索引"] = False
    d["Q5处置"] = ("B5-1 已按原页（evidence/%s/pages/p002.png）补建真第 5 题题面，"
                   "并在 indexes/questions.csv 登记 variant=verified_from_page；"
                   "原错误内容保留在『评分材料来源块』。" % SID)
    json.dump(d, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # 索引/实物一致性
    idx = set(r["question_id"] for r in rows)
    import glob
    files = set(os.path.basename(f)[:-3] for f in glob.glob(os.path.join(P.Q_DIR, "*", "*.md")))
    print("实物:", len(files), "索引唯一题:", len(idx))
    print("实物多出:", sorted(files - idx))
    print("索引缺实物:", sorted(idx - files))


if __name__ == "__main__":
    main()
