#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 sessions.csv 生成按书线 digest_<line>.md 和 overall.md。只读 CSV，不再碰原始 jsonl。"""
import sys
sys.dont_write_bytecode = True
import csv
import json
import collections
import datetime
import os

IN_CSV = "/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/07ecc7d4-1283-4309-9858-715c562b9892/scratchpad/codex_mining/sessions.csv"
OUT_DIR = "/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/07ecc7d4-1283-4309-9858-715c562b9892/scratchpad/codex_mining"
FINAL_DIR = "/Users/wanglifei/Desktop/gpt和claude共同的小窝/后勤管理/20260923_脚本化与跨书工具/Codex记录分析_20260924"

LINES = ["bixiu2", "bixiu3", "philosophy", "culture", "xuanbi1", "xuanbi2", "thinking", "reasoning", "bank", "other"]


def fnum(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def day(ts):
    ts = fnum(ts, 0)
    if not ts:
        return "?"
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return "?"


def load_rows():
    with open(IN_CSV, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    rows = load_rows()
    by_line = collections.defaultdict(list)
    for r in rows:
        by_line[r.get("book_line") or "other"].append(r)

    overall_lines = []
    overall_lines.append("# Codex 会话记录挖掘 — 全局汇总\n")
    overall_lines.append("生成时间：%s\n" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    overall_lines.append("总文件数：%d（含读取失败 %d）\n" % (len(rows), sum(1 for r in rows if r.get("error"))))
    tot_w = sum(fnum(r.get("tok_weighted")) for r in rows)
    overall_lines.append("加权 token 总量（跨书线合计，口径见各 digest 说明）：%.0f\n" % tot_w)
    overall_lines.append("\n## 各书线文件数 / 加权 token / 占比\n")
    overall_lines.append("| 书线 | 文件数 | 加权token | 占比 | 时间跨度 |")
    overall_lines.append("|---|---:|---:|---:|---|")
    for line in LINES:
        rs = by_line.get(line, [])
        if not rs:
            continue
        w = sum(fnum(r.get("tok_weighted")) for r in rs)
        days = sorted(set(day(r.get("first_ts")) for r in rs if r.get("first_ts")))
        span = "%s ~ %s" % (days[0], days[-1]) if days else "?"
        overall_lines.append("| %s | %d | %.0f | %s | %s |" % (
            line, len(rs), w, ("%.1f%%" % (100 * w / tot_w) if tot_w else "-"), span))

    with open(os.path.join(OUT_DIR, "overall.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(overall_lines) + "\n")

    for line in LINES:
        rs = by_line.get(line, [])
        if not rs:
            continue
        rs_sorted = sorted(rs, key=lambda r: fnum(r.get("first_ts")))
        out = []
        out.append("# 书线 digest — %s\n" % line)
        out.append("文件数：%d\n" % len(rs))
        tot_w = sum(fnum(r.get("tok_weighted")) for r in rs)
        out.append("加权 token 合计：%.0f\n" % tot_w)

        # 按环节统计
        stage_w = collections.Counter()
        stage_n = collections.Counter()
        for r in rs:
            st = r.get("stage_guess") or "其他"
            stage_w[st] += fnum(r.get("tok_weighted"))
            stage_n[st] += 1
        out.append("\n## 按环节 token / 会话数占比\n")
        out.append("| 环节 | 会话数 | 加权token | 占比 |")
        out.append("|---|---:|---:|---:|")
        for st, w in stage_w.most_common():
            out.append("| %s | %d | %.0f | %s |" % (st, stage_n[st], w, ("%.1f%%" % (100 * w / tot_w) if tot_w else "-")))

        # 时间线（抽取有代表性的，按天聚合，避免过长）
        out.append("\n## 时间线（按天聚合，前 40 天）\n")
        out.append("| 日期 | 会话数 | 加权token | 代表用户消息 |")
        out.append("|---|---:|---:|---|")
        by_day = collections.defaultdict(list)
        for r in rs_sorted:
            by_day[day(r.get("first_ts"))].append(r)
        for d in sorted(by_day)[:40]:
            rs_d = by_day[d]
            w = sum(fnum(r.get("tok_weighted")) for r in rs_d)
            sample = ""
            for r in rs_d:
                if r.get("user_text_sample"):
                    sample = r["user_text_sample"][:80]
                    break
            out.append("| %s | %d | %.0f | %s |" % (d, len(rs_d), w, sample.replace("|", "/")))

        # 返工信号：反复出现的一次性脚本名 / Bash 命令分类 Top
        cat_counter = collections.Counter()
        tool_counter = collections.Counter()
        render_total = 0
        check_total = 0
        for r in rs:
            render_total += int(fnum(r.get("render_n")))
            check_total += int(fnum(r.get("check_n")))
            try:
                cats = json.loads(r.get("exec_cat_json") or "{}")
                for k, v in cats.items():
                    cat_counter[k] += v
            except Exception:
                pass
            try:
                tools = json.loads(r.get("tool_counts_json") or "{}")
                for k, v in tools.items():
                    tool_counter[k] += v
            except Exception:
                pass
        out.append("\n## 返工信号\n")
        out.append("- 渲染类命令累计次数：%d\n- 检查/校验类命令累计次数：%d\n" % (render_total, check_total))
        out.append("\n## Bash 命令分类 Top10\n")
        for k, v in cat_counter.most_common(10):
            out.append("- %s: %d" % (k, v))
        out.append("\n## 工具调用 Top10\n")
        for k, v in tool_counter.most_common(10):
            out.append("- %s: %d" % (k, v))

        text = "\n".join(out) + "\n"
        # 30KB 上限裁剪
        if len(text.encode("utf-8")) > 30000:
            text = text.encode("utf-8")[:29500].decode("utf-8", "ignore") + "\n\n（已截断，超过30KB上限）\n"
        with open(os.path.join(OUT_DIR, "digest_%s.md" % line), "w", encoding="utf-8") as fh:
            fh.write(text)

    print("digests written to", OUT_DIR)


if __name__ == "__main__":
    main()
