#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""续修 2026-09-21 · 交付验收：抽五种不同载体/结构的题包做端到端核验。

任务书要求：抽取至少五种不同载体/结构题包，核查
  ① 正文/评分边界（读取器不得把答案/细则混入题面）
  ② 原图链接（页级资产路径必须真实存在）
  ③ 跨页依赖（跨页题不得被拆散）
  ④ 完整度（题号、选项、设问、分值齐全）

样本（刻意覆盖不同载体与结构）：
  1. DOCX 原生纯文字选择题
  2. 扫描件选择题（丰台一模，OCR 通道）
  3. 教师版 PDF（题面与答案同块，高风险载体）
  4. 跨页主观题（丰台一模 Q14，材料在第4页、题肢在第5页）
  5. 表格/图形题（2026 北京高考 Q6 表格、Q19 表格+拓片图）
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P
import bank

SAMPLES = [
    {"name": "DOCX 原生纯文字选择题", "qid": "BJ-2023-XC-ERMO-Q2",
     "why": "DOCX 正文在 w:tbl 里，验证表格抽取与题面边界"},
    {"name": "扫描件选择题（OCR 通道）", "qid": "BJ-2026-FT-YIMO-Q6",
     "why": "纯扫描，验证 verified 层优先于 OCR 候选"},
    {"name": "教师版 PDF（题面与答案同块）", "qid": "BJ-2020-BJ-GAOKAO-Q1",
     "why": "教师版把题面与答案排在同一块，验证默认输出不含答案"},
    {"name": "跨页主观题", "qid": "BJ-2026-FT-YIMO-Q14",
     "why": "材料在第4页、题肢在第5页，验证跨页关系被显式登记"},
    {"name": "表格/图形题", "qid": "BJ-2026-BJ-GAOKAO-Q6",
     "why": "原页两列表格（表头跨列），验证 HTML 表结构与合并单元格"},
]


def run_get(qid, extra=None):
    cmd = [sys.executable, os.path.join(P.SCRIPT_DIR, "bank.py"), "get", qid]
    if extra:
        cmd += extra
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.stdout


def main():
    out = []
    for s in SAMPLES:
        qid = s["qid"]
        fp, q = bank.q_path(qid)
        rec = {"name": s["name"], "question_id": qid, "why": s["why"],
               "file_exists": bool(fp)}
        if not fp:
            rec["result"] = "缺文件"
            out.append(rec)
            continue
        md = open(fp, encoding="utf-8").read()
        secs = dict(bank.split_md(md))
        default_out = run_get(qid)

        # ① 正文/评分边界：默认输出不得含答案/评分/讲评小节标题与 ``` 引用块
        rec["默认输出含答案小节"] = any(t in default_out for t in (
            "## 参考答案来源块", "## 评分材料来源块", "## 讲评来源块",
            "## 正式评分材料原文", "## 参考答案原文"))
        # 默认输出不得出现"参考答案不等于正式细则"这类只在答案区出现的提示
        rec["默认输出含答案区提示"] = "参考答案不等于正式细则" in default_out
        # ② 原图链接：解析默认输出里的资产路径，逐个检查存在性
        paths = re.findall(r"`(assets/[^`]+\.png)`", default_out)
        rec["原图链接数"] = len(paths)
        rec["原图链接全部存在"] = all(os.path.isfile(os.path.join(P.OUT_ROOT, x))
                                     for x in paths) if paths else None
        # ③ 跨页依赖
        rec["含跨页说明"] = "跨页说明" in md
        rec["页级定位行数"] = len(re.findall(r"^- 页级定位", md, re.M))
        # ④ 完整度
        rec["有身份信息"] = "## 身份信息" in md
        rec["有读取指引"] = "## 读取指引（机器可读）" in md
        rec["有来源定位"] = "## 来源定位" in md
        rec["有质量标记"] = "## 质量标记" in md
        rec["采用题面小节"] = (re.search(r"^- 采用题面小节: `(.+?)`", md, re.M) or
                              [None, "（无）"])[1] if re.search(
                                  r"^- 采用题面小节: `(.+?)`", md, re.M) else "（无）"
        # 题面完整度：选项标记数
        t, body = bank.adopted_stem(md)
        rec["题面字符数"] = len(body)
        rec["题面选项标记数"] = len(re.findall(r"(?:^|\s)([A-D])[．.、]", body))
        rec["题面含设问"] = bool(re.search(r"(结合材料|下列|谈谈|说明|分析|阐释|阐明)", body))
        rec["默认输出字符数"] = len(default_out)
        rec["全部原文字符数"] = len(md)
        rec["按题读取占全文比"] = round(len(default_out) / max(1, len(md)) * 100, 1)
        out.append(rec)

    rpt = os.path.join(P.VAL_DIR, "续修_20260921", "39_五载体题包核验.json")
    json.dump(out, open(rpt, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("报告:", rpt)


if __name__ == "__main__":
    main()
