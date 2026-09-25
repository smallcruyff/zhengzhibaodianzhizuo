#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
codex_mine.py -- 只读扫描 ~/.codex/sessions + archived_sessions 的 rollout-*.jsonl，
把 65GB 原始记录压成 CSV + 按书线的 digest 摘要，供模型只读摘要用。

复用 /Users/wanglifei/.codex/skills/beijing-gaokao-politics/scripts/usage_profile.py
里的 codex_file_meta / parse_codex（token 口径、工具计数、bash 分类、用户消息截取都不重写）。

硬约束：只读 rollout-*.jsonl；绝不读取/输出 auth.json、config.toml、任何 *key*/*token* 凭据文件；
摘要里对 sk-…、Bearer …、长度>=32 的十六进制/Base64 串打码。
"""
import sys
sys.dont_write_bytecode = True
import os
import re
import csv
import json
import glob
import time
import collections
import multiprocessing as mp

SKILL_SCRIPTS = "/Users/wanglifei/.codex/skills/beijing-gaokao-politics/scripts"
sys.path.insert(0, SKILL_SCRIPTS)
import usage_profile as UP  # noqa: E402

ROOTS = [
    os.path.expanduser("~/.codex/sessions"),
    os.path.expanduser("~/.codex/archived_sessions"),
]
OUT_DIR = "/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/07ecc7d4-1283-4309-9858-715c562b9892/scratchpad/codex_mining"
FINAL_DIR = "/Users/wanglifei/Desktop/gpt和claude共同的小窝/后勤管理/20260923_脚本化与跨书工具/Codex记录分析_20260924"

SECRET_RX = re.compile(r"sk-[A-Za-z0-9]{10,}|Bearer\s+[A-Za-z0-9._-]{10,}|\b[A-Fa-f0-9]{32,}\b|\b[A-Za-z0-9+/]{32,}={0,2}\b")
FORBIDDEN_NAME_RX = re.compile(r"auth\.json$|config\.toml$", re.I)
FORBIDDEN_CONTENT_RX = re.compile(r"key|token", re.I)


def redact(s):
    if not s:
        return s
    return SECRET_RX.sub("[REDACTED]", s)


# ----------------------------------------------------------------------------- 书线分类
BOOK_LINE_RULES = [
    ("bixiu2", re.compile(r"必修二|经济与社会|修订2[0-3]\d")),
    ("bixiu3", re.compile(r"必修三|政治与法治|第\s*(?:[1-9]|[1-4]\d)\s*批|R\d{1,2}候选|最终\d{2}")),
    ("philosophy", re.compile(r"必修四|哲学与文化|哲学(?!课)|唯物论|辩证法|认识论|历史观")),
    ("culture", re.compile(r"文化生活|文化传承|文化自信|文化(?:创新|交流)")),
    ("xuanbi1", re.compile(r"选择性必修一|选必一|当代国际政治|国际关系")),
    ("xuanbi2", re.compile(r"选择性必修二|选必二|法律与生活")),
    ("thinking", re.compile(r"逻辑与思维|选择性必修三|选必三")),
    ("reasoning", re.compile(r"科学思维|推理")),
    ("bank", re.compile(r"题库|DeepSeek_政治题库|MD全库|bank\.py|claude_bank|逐题|packets/|BANK_ACTOR")),
]
CWD_BOOK_HINTS = [
    ("bixiu2", re.compile(r"必修二_")),
    ("bixiu3", re.compile(r"必修三_")),
    ("philosophy", re.compile(r"必修四|哲学")),
    ("culture", re.compile(r"文化")),
    ("xuanbi1", re.compile(r"选必一|选择性必修一")),
    ("xuanbi2", re.compile(r"选必二|选择性必修二")),
    ("thinking", re.compile(r"选必三|逻辑与思维")),
    ("bank", re.compile(r"题库|MD全库|claude_bank")),
]

STAGE_RULES = [
    ("题源普查", re.compile(r"题源|普查|原题|真题|核题|试卷扫描|逐题核对")),
    ("抽题与细则", re.compile(r"细则|评分标准|采分点|参考答案|抽题|选题")),
    ("分类框架", re.compile(r"分类|框架|知识点树|考点体系|专题划分")),
    ("写教学内容", re.compile(r"知参|解析|讲解|术语|答题模板|写正文|补充内容")),
    ("合稿构建", re.compile(r"合稿|assemble|构建|合并|汇总成书|build")),
    ("编号目录分页", re.compile(r"编号|目录|分页|页码|排版|页眉|页脚")),
    ("渲染看页", re.compile(r"渲染|render|soffice|libreoffice|看页|截图核对|PDF导出")),
    ("发布交接", re.compile(r"送印|交接|发布|定稿|收口|移交")),
    ("题库", re.compile(r"题库|bank\.py|packets|逐题|MD全库")),
    ("规则Skill", re.compile(r"Skill|宪法|规则|协作入口|collab\.py|流程优化")),
]


def classify_book_line(cwd, user_text_joined):
    txt = user_text_joined or ""
    cwd = cwd or ""
    best, best_line = 0, "other"
    for name, rx in BOOK_LINE_RULES:
        k = len(rx.findall(txt))
        if k > best:
            best, best_line = k, name
    if best == 0:
        for name, rx in CWD_BOOK_HINTS:
            if rx.search(cwd):
                best_line = name
                break
    return best_line


def classify_stage(text):
    scores = collections.Counter()
    for name, rx in STAGE_RULES:
        k = len(rx.findall(text))
        if k:
            scores[name] = k
    if not scores:
        return "其他"
    return scores.most_common(1)[0][0]


# ----------------------------------------------------------------------------- 每文件挖掘
def is_forbidden(path):
    base = os.path.basename(path)
    return bool(FORBIDDEN_NAME_RX.search(base))


def mine_one(path):
    if is_forbidden(path) or not path.endswith(".jsonl") or "rollout-" not in os.path.basename(path):
        return None
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    try:
        r = UP.parse_codex(path, UP.DEFAULT_WEIGHTS, UP.make_tz(None))
    except Exception as e:
        return {"file": path, "size_mb": round(size / 1048576, 3), "error": redact(str(e))[:200]}

    meta = r.get("meta") or {}
    cwd = meta.get("cwd") or ""
    user_text = [redact(t) for t in (r.get("user_text") or [])]
    joined = " ".join(user_text) + " " + cwd
    book_line = classify_book_line(cwd, joined)
    stage = classify_stage(joined)

    tools = r.get("tools") or {}
    exec_cats = r.get("exec_categories") or {}
    total = r.get("total") or {}

    # 反复重写 / 渲染 / 失败信号：从 exec_categories 里已有的分类里取
    render_n = exec_cats.get("渲染", 0)
    check_n = exec_cats.get("检查", 0)
    fail_n = 0  # parse_codex 不直接给失败计数；用工具输出错误关键词的近似留空，交给后续脚本按需扩展

    n_turns = len(user_text) if user_text else None

    row = {
        "file": path,
        "size_mb": r.get("size_mb"),
        "cwd": cwd,
        "model_last": r.get("model_last"),
        "first_ts": r.get("first"),
        "last_ts": r.get("last"),
        "book_line": book_line,
        "stage_guess": stage,
        "n_token_count_events": r.get("token_count_events"),
        "records_token_usage": r.get("records_token_usage"),
        "tok_new": total.get("new_tokens"),
        "tok_cache_read": total.get("cache_read"),
        "tok_out": total.get("output"),
        "tok_weighted": total.get("weighted"),
        "n_calls": total.get("calls"),
        "tool_counts_json": json.dumps(tools, ensure_ascii=False),
        "exec_cat_json": json.dumps(exec_cats, ensure_ascii=False),
        "render_n": render_n,
        "check_n": check_n,
        "user_text_sample": " | ".join(user_text[:3]),
        "thread_source": meta.get("thread_source"),
        "parent": meta.get("parent"),
        "nickname": meta.get("nickname"),
    }
    return row


def list_files():
    files = []
    for root in ROOTS:
        if not os.path.isdir(root):
            continue
        files.extend(glob.glob(os.path.join(root, "**", "rollout-*.jsonl"), recursive=True))
    return sorted(set(files))


def run(files, nproc, out_csv, progress_every=200):
    t0 = time.time()
    rows = []
    n_err = 0
    with mp.Pool(nproc) as pool:
        for i, row in enumerate(pool.imap_unordered(mine_one, files, chunksize=4), 1):
            if row is None:
                continue
            if row.get("error"):
                n_err += 1
            rows.append(row)
            if i % progress_every == 0:
                print("[progress] %d/%d files, %.0fs elapsed" % (i, len(files), time.time() - t0), flush=True)
    fieldnames = ["file", "size_mb", "cwd", "model_last", "first_ts", "last_ts", "book_line", "stage_guess",
                  "n_token_count_events", "records_token_usage", "tok_new", "tok_cache_read", "tok_out",
                  "tok_weighted", "n_calls", "tool_counts_json", "exec_cat_json", "render_n", "check_n",
                  "user_text_sample", "thread_source", "parent", "nickname", "error"]
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            for k in fieldnames:
                row.setdefault(k, "")
            w.writerow(row)
    print("[done] %d files, %d errors, %.0fs total -> %s" % (len(rows), n_err, time.time() - t0, out_csv), flush=True)
    return rows


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个文件（试跑用）")
    ap.add_argument("--nproc", type=int, default=max(2, (os.cpu_count() or 4) - 1))
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "sessions.csv"))
    args = ap.parse_args()
    files = list_files()
    print("[info] total files found: %d" % len(files), flush=True)
    if args.limit:
        files = files[: args.limit]
    run(files, args.nproc, args.out)
