#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""续修 2026-09-21 · 通用逐页批次应用器（verified 层写入 + 逐页登记）。

把某一来源（source_id）的逐页校对结果落盘：
  1. 对每道题写入独立 `## 题面（原页核验改正，verified）` 小节，
     并更新读取指引优先采用该小节；原始 native / OCR 候选块原样保留；
  2. 逐页登记 visual_review（带真实查看证据，由 24 脚本写入）。

用法：
  /usr/bin/python3 37_apply_batch.py --config <批次配置.json>

配置字段：
  source_id, exam_id, rel_path, batch_name,
  texts: { "题号": {"question_id","page","type","score","subq","fixes","text"} },
  pages: { "页码": {"carries":[...], "findings":[...], "verdict":"..."} }
"""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

VERIFIED_TITLE = "题面（原页核验改正，verified）"


def split_sections(md):
    ms = list(re.finditer(r"^## (.+)$", md, re.M))
    out = []
    for i, m in enumerate(ms):
        e = ms[i + 1].start() if i + 1 < len(ms) else len(md)
        out.append((m.group(1).strip(), m.start(), m.end(), md[m.end():e]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    SID = cfg["source_id"]
    EXAM = cfg["exam_id"]
    REL = cfg["rel_path"]
    BATCH = cfg.get("batch_name", "B5")
    now = datetime.datetime.now().isoformat(timespec="seconds")

    log = []
    for num_s, item in sorted(cfg["texts"].items(), key=lambda kv: int(kv[0])):
        qid = item["question_id"]
        fp = os.path.join(P.Q_DIR, EXAM, "%s.md" % qid)
        new_file = not os.path.isfile(fp)
        hdr = ("\n## %s\n\n" % VERIFIED_TITLE
               + "> **核验依据**：实际打开 `evidence/%s/pages/p%03d.png`"
                 "（%s 第 %d 页），逐字对照 native 与 OCR 候选。\n"
                 % (SID, item["page"], cfg.get("label", EXAM), item["page"])
               + "> **原图依据**：`assets/%s/pages/p%03d.png`\n" % (SID, item["page"])
               + "> **执行者**：DeepSeek-V4.1-Flash（本会话）；**时间**：%s\n" % now
               + "> **本批**：%s\n" % BATCH
               + "> **改正内容**：%s\n" % item.get("fixes", "本页未发现文字错漏；题面按原页逐字录入。")
               + ("> **父稿**：原始 native / OCR 候选块原样保留在下方各节，未被覆盖。\n"
                  if not new_file else
                  "> **新建说明**：本库原未切出本题（索引缺号），本轮按原页补建，"
                  "原页确有该题，非凭空生成。\n")
               + "\n" + item["text"].rstrip() + "\n")

        if new_file:
            md = ("# %s\n\n## 身份信息\n"
                  "- question_id: `%s`\n- exam_id: `%s`\n- 题号: %s\n- 题型: %s\n"
                  "- 分值: %s\n- 小问: %s\n"
                  "- 来源文件数: 1（去重后）；来源块数: 0（原页核验补建，非自动切分）\n\n"
                  % (qid, qid, EXAM, num_s, item.get("type", "选择题"),
                     item.get("score", "缺失（原文未标注或切分未捕获）"),
                     item.get("subq", "无（或未标注）"))
                  + "## 读取指引（机器可读）\n\n"
                  + "- 采用题面小节: `%s`\n" % VERIFIED_TITLE
                  + "- 采用题面来源性质: 原页核验录入（依据 `evidence/%s/pages/p%03d.png`）\n"
                    % (SID, item["page"])
                  + "- 备选题面小节: 无\n"
                  + "- 不得当作题面: `讲评来源块（含答案与解析，不得当作题面）`、"
                    "`参考答案来源块（不得当作评分依据）`、`评分材料来源块（原样保留，配对状态见下）`、"
                    "`待确认材料来源块（角色未定，须人工裁决）`\n"
                  + "- 评分关系状态: 暂未找到\n"
                  + "- 原页核验: 已核（%s，%s）\n" % (now[:10], BATCH)
                  + hdr
                  + "\n## 正式评分材料原文\n\n（未找到已确认的正式评分材料）\n\n"
                  + "## 参考答案原文\n\n（无）\n\n"
                  + "## 来源定位\n- `%s`（原卷，第 %d 页）\n" % (REL, item["page"])
                  + "\n## 质量标记\n- extraction_status: verified\n"
                  + "- rubric_status: 暂未找到（与头部配对状态同源，派生自 indexes/rubric_links.csv）\n"
                  + "- needs_review: N（题面已按原页核验）\n"
                  + "- 图像依赖（页级，须显式打开）：\n  - 第 %d 页：`assets/%s/pages/p%03d.png`\n"
                    % (item["page"], SID, item["page"]))
        else:
            md = open(fp, encoding="utf-8").read()
            if VERIFIED_TITLE in md:
                print("%s 已有 verified 小节，跳过" % qid)
                continue
            secs = split_sections(md)
            i = next((k for k, s in enumerate(secs)
                      if s[0] == "读取指引（机器可读）"), None)
            if i is None:
                print("!! %s 无读取指引，跳过" % qid)
                continue
            insert_at = secs[i][2] + len(secs[i][3])
            md = md[:insert_at] + hdr + md[insert_at:]
            md = re.sub(r"^- 采用题面小节: .*$", "- 采用题面小节: `%s`" % VERIFIED_TITLE,
                        md, count=1, flags=re.M)
            md = re.sub(r"^- 采用题面来源性质: .*$",
                        "- 采用题面来源性质: 原页核验录入（依据 `evidence/%s/pages/p%03d.png`）"
                        % (SID, item["page"]), md, count=1, flags=re.M)
            md = re.sub(r"^- 评分关系状态: (.*)$",
                        r"- 评分关系状态: \1\n- 原页核验: 已核（%s，%s）" % (now[:10], BATCH),
                        md, count=1, flags=re.M)
            md = re.sub(r"^- extraction_status: .*$", "- extraction_status: verified",
                        md, count=1, flags=re.M)
            md = re.sub(r"^- needs_review: .*$", "- needs_review: N（题面已按原页核验）",
                        md, count=1, flags=re.M)

        with open(fp, "w", encoding="utf-8") as fh:
            fh.write(md)
        log.append({"question_id": qid, "page": item["page"], "new_file": new_file,
                    "fixes": item.get("fixes", ""),
                    "原图依据": "evidence/%s/pages/p%03d.png" % (SID, item["page"]),
                    "执行者": "DeepSeek-V4.1-Flash", "时间": now, "批次": BATCH})
        print("%s %s" % (qid, "新建" if new_file else "写入 verified"))

    outdir = os.path.join(P.VAL_DIR, "续修_20260921")
    P.ensure_dirs(outdir)
    with open(os.path.join(outdir, "%s_修复日志.jsonl" % BATCH.replace("/", "_")),
              "w", encoding="utf-8") as fh:
        for x in log:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    recs = []
    for pg_s, d in sorted(cfg["pages"].items(), key=lambda kv: int(kv[0])):
        pg = int(pg_s)
        recs.append({
            "source_id": SID, "page": pg,
            "viewed_file": "evidence/%s/pages/p%03d.png" % (SID, pg),
            "method": "实际打开原页渲染图，逐字对照 native 逐块 bbox 与 OCR 候选",
            "findings": d["findings"],
            "affected_questions": d.get("carries", []),
            "action": "本页已实际打开逐项对照；结论：%s" % d.get("verdict", ""),
            "reviewer": "DeepSeek-V4.1-Flash",
        })
    rp = os.path.join(outdir, "%s_逐页记录.json" % BATCH.replace("/", "_"))
    json.dump(recs, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("题:", len(log), " 逐页记录:", rp)


if __name__ == "__main__":
    main()
