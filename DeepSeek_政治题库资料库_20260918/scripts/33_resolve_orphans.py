#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""续修 2026-09-21 · B2：五个未入索引文件的定性登记。

任务书第一步第 4 条要求：逐项记录是旧残留、错误题键还是真正缺索引；
**不直接删除，不凭空生成 Q0**。

定性依据（全部可复核）：
  1. 文件 mtime 与最终切分运行时间对比；
  2. indexes/split_review.jsonl 中该来源的 action 记录；
  3. 该考试在本库实际拥有的来源文件角色（exam_files.csv）；
  4. 文件内实际文本与题面/答案/细则的性质判别。

产出：
  validation/续修_20260921/五个未入索引文件_定性.json / .md
  并在每个文件顶部加一行定性横幅（不改动任何原有文本）。
"""
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

DET = [
    {
        "question_id": "BJ-2023-HD-ERMO-Q1",
        "exam_id": "BJ-2023-HD-ERMO",
        "分类": "旧残留（早期切分产物）",
        "是否真缺索引": False,
        "证据": [
            "文件 mtime = 2026-09-18 16:59，早于最终切分运行 23:01—23:03",
            "split_review.jsonl：该来源 action=dropped_too_short, num=1, chars=18, line 33-35",
            "块原文『1、知识乱堆砌，缺乏逻辑、答题无层次』是阅卷细则的节内枚举点，不是题面",
            "该考试在本库只有『海淀二模 细则(1).pptx』(评分材料)，无原卷",
        ],
        "处置": "保留文件并加定性横幅；不计入题键；不生成替代题",
    },
    {
        "question_id": "BJ-2023-HD-ERMO-Q3",
        "exam_id": "BJ-2023-HD-ERMO",
        "分类": "旧残留（早期切分产物）",
        "是否真缺索引": False,
        "证据": [
            "文件 mtime = 2026-09-18 16:59，早于最终切分运行",
            "split_review.jsonl：action=dropped_too_short, num=3, chars=11, line 256-257",
            "块原文『3.理论和分析不匹配；』是阅卷细则的节内枚举点",
        ],
        "处置": "保留文件并加定性横幅；不计入题键",
    },
    {
        "question_id": "BJ-2024-HD-QIZHONG-Q0",
        "exam_id": "BJ-2024-HD-QIZHONG",
        "分类": "旧残留 + 错误题键（Q0 不存在）",
        "是否真缺索引": False,
        "证据": [
            "文件 mtime = 2026-09-18 17:00，早于最终切分运行",
            "块原文『0.83 / 选择数 / 98 / 选择率』是选项分布统计表，OCR 把『0.83』误读成题号 0",
            "split_review.jsonl：同来源 OCR 有 dropped_too_short 记录，preview 同类统计数字",
            "题号 0 在原卷中不存在",
        ],
        "处置": "保留文件并加定性横幅；**不凭空生成 Q0**",
    },
    {
        "question_id": "BJ-2026-FT-ERMO-Q20",
        "exam_id": "BJ-2026-FT-ERMO",
        "分类": "错误题键（答案充当题面）+ 真实题面缺口",
        "是否真缺索引": "部分：真正缺的是第20题的**题面**，本文件不是它",
        "证据": [
            "文件 mtime = 2026-09-18 17:01，早于最终切分运行 23:0x",
            "split_review.jsonl：教师版 OCR action=dropped_nested_restart, line 331, num=20（位于分节标题之后）",
            "块原文『20.（8分）中国加快推进自由贸易试验区…有利于推动构建人类命运共同体。』是参考答案文本，不是题面",
            "教师版 OCR 缺号 [8—13,18,20,21]；该考试无原卷，仅有评分细则 pptx 与教师版 PDF",
        ],
        "处置": "保留文件并加定性横幅；标注为『答案冒充题面』；第20题真实题面仍缺，登记为缺口",
    },
    {
        "question_id": "BJ-2026-FT-YIMO-Q5",
        "exam_id": "BJ-2026-FT-YIMO",
        "分类": "错误题键（细则阅卷问题枚举）+ 真实题面缺口",
        "是否真缺索引": "部分：真正缺的是第5题的**题面**",
        "证据": [
            "文件 mtime = 2026-09-18 17:00，早于最终切分运行",
            "split_review.jsonl：细则 action=dropped_nested_restart, line 208, num=5（分节标题之后）",
            "块原文『5.宏观整体意识不足：绝大多数孩子只分别拆解了四个角度…』是阅卷常见问题，不是题面",
            "头部旧配对『已匹配正式材料 / 重叠1.0000(题干366字/材料段4000字)』是自比自的假阳性：题干本身就取自该细则",
            "原卷 试卷.pdf 的 OCR 缺号 [5,7,9,14] → 第5题真实题面确实未被切出",
        ],
        "处置": "保留文件并加定性横幅；第5题真实题面登记为缺口",
    },
]


def main():
    out_dir = os.path.join(P.VAL_DIR, "续修_20260921")
    P.ensure_dirs(out_dir)
    idx = set()
    with open(os.path.join(P.INDEX_DIR, "questions.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            idx.add(r["question_id"])

    banner_tpl = ("> **定性登记（续修 2026-09-21，未删除原件）**：{cls}；"
                  "是否真缺索引：{miss}。依据与处置见 "
                  "`validation/续修_20260921/五个未入索引文件_定性.md`。\n\n")

    for d in DET:
        qid = d["question_id"]
        fp = os.path.join(P.Q_DIR, d["exam_id"], "%s.md" % qid)
        d["in_questions_csv"] = qid in idx
        d["file_exists"] = os.path.isfile(fp)
        if d["file_exists"]:
            md = open(fp, encoding="utf-8").read()
            if "定性登记（续修 2026-09-21" not in md:
                banner = banner_tpl.format(cls=d["分类"], miss=d["是否真缺索引"])
                md = md.replace("\n\n", "\n\n" + banner, 1) if md.startswith("# ") \
                    else banner + md
                with open(fp, "w", encoding="utf-8") as fh:
                    fh.write(md)
                d["banner_added"] = True
            else:
                d["banner_added"] = False

    with open(os.path.join(out_dir, "五个未入索引文件_定性.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"核定时间": "2026-09-21", "项数": len(DET), "明细": DET},
                  fh, ensure_ascii=False, indent=2)

    lines = ["# 五个未入索引文件：逐项定性（2026-09-21 续修）", "",
             "实物单题文件 1687 份，索引唯一题号 1682 个；实物多出 5 份、索引无缺实物。",
             "以下逐项定性，**原件全部保留、未删除**，也不凭空生成 Q0。", ""]
    for d in DET:
        lines.append("## %s" % d["question_id"])
        lines.append("- 分类：**%s**" % d["分类"])
        lines.append("- 是否真缺索引：%s" % d["是否真缺索引"])
        lines.append("- 证据：")
        for e in d["证据"]:
            lines.append("  - %s" % e)
        lines.append("- 处置：%s" % d["处置"])
        lines.append("")
    lines.append("## 共同结论")
    lines.append("- 5 份实物文件均由**早期切分运行（2026-09-18 16:59—17:01）**产生；"
                 "最终切分（23:01—23:03）已按 `dropped_too_short` / "
                 "`dropped_nested_restart` 规则不再生成它们，但 `09_split.py` 不回删旧文件，"
                 "故形成残留。")
    lines.append("- 因此这 5 份**不是**“真正缺索引的新题键”，"
                 "而是旧残留或错误题键；索引口径（1682）无需改动。")
    lines.append("- 其中 BJ-2026-FT-ERMO-Q20、BJ-2026-FT-YIMO-Q5 同时暴露"
                 "**真实题面缺口**（教师版/原卷 OCR 未切出该题题面），已登记为缺口，"
                 "须在后续批次回原页补齐。")
    lines.append("- 修复建议（未执行，待主代理裁决）：在 `09_split.py` 增加"
                 "“刷新前清理本卷旧产物”或在索引中登记 stale 清单；本轮只登记不删除。")
    with open(os.path.join(out_dir, "五个未入索引文件_定性.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("已登记 %d 项；报告：%s" % (len(DET), out_dir))
    for d in DET:
        print("  %-26s %s" % (d["question_id"], d["分类"]))


if __name__ == "__main__":
    main()
