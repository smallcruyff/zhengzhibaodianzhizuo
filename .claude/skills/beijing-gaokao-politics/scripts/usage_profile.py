#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usage_profile.py -- Claude Code / Codex 会话用量画像（只读、流式）

量出 token 与时间花在哪：按 线（必修三/题库线/必修二/其他）、批次、模型、日期、
主线程/子代理/工作流代理（含子代理类型与描述）、工具、Bash 命令类型汇总；
给出“前 15 个最费的环节”“单次最贵动作 TOP10”“Bash 最耗时 TOP10”。

只读取会话 jsonl（及同名目录下 subagents/、workflows/）；不写任何项目文件。
输出写到 --out 目录：usage_profile.json 与 usage_profile.txt（中文排行）。

口径（务必看）：
  * 同一 message.id 的多条记录只计一次；跨文件也去重（续接/分叉会话会整段复制旧消息）。
  * 输出 token：同一消息的首条记录只带流式开头的 output_tokens，取该消息各条记录的最大值；
    仍无最终 usage 的按正文+工具入参字数估计（思考 token 不可见，为下限）。
  * 新 token = input_tokens + cache_creation_input_tokens + output_tokens；cache_read 单列。
  * 加权当量 = in*1 + cache_creation*1.25 + cache_read*0.1 + out*5（Anthropic 标准价比，
    与模型无关；可用 --weights 改）。只是相对量，不是美元。美元请看会话里的 cost-state（已原样汇报）。
  * Bash 耗时 = tool_result 时间戳 - tool_use 时间戳；run_in_background 的调用不计时长。
  * 工具结果体积：文本按字符数估 token（ASCII 0.5、非 ASCII 1.0，系在本项目会话上用
    usage 增量回归得到），图片按 宽*高/700；“滞留成本”= 结果估计 token × 其后同一上下文里的
    API 调用次数（即它被 cache_read 反复读入的次数），遇到压缩(compact)截断。
  * 批次：在每个“人类回合”（两条用户消息之间）里找“第N批 / 最终N / RN候选”等标记，
    取被充分提到的最高批次，并按线单调不减承接；子代理/工作流按其启动时刻落到父会话的回合。

用法：
  python3 usage_profile.py ~/.claude/projects/<项目目录> --out DIR [--since 2026-09-15] [--until 2026-09-24]
  python3 usage_profile.py a.jsonl b.jsonl --line 必修三 --out DIR
  python3 usage_profile.py <项目目录> --classify-only --out DIR
  python3 usage_profile.py <项目目录> --codex-scan ~/.codex/sessions --codex-dates 2026-09-22,2026-09-23 \
      --codex-cwd 'gpt6|gpt和claude' --codex-sample 6 --out DIR
  python3 usage_profile.py --codex FILE.jsonl ... --out DIR       # 只看 Codex
"""
import argparse
import base64
import bisect
import collections
import glob
import heapq
import json
import os
import re
import statistics
import struct
import sys
from datetime import datetime, timedelta, timezone

# ----------------------------------------------------------------------------- 配置
DEFAULT_WEIGHTS = {"input": 1.0, "cache_creation": 1.25, "cache_read": 0.1, "output": 5.0}
# 每“百万加权当量”的美元估算，由会话 cost-state 记录反推（Claude Code 自己算的 costUSD）：
#   sonnet-5：13295440 会话 cost-state 精确吻合 in 2 / 写缓存 2.5 / 读缓存 0.2 / 出 10（$/M），即 2.0；
#   opus-5-5：13295440、3bd4f1ab 两个快照分别 2.55、2.78，取 2.65（出/入价比可能不是 5，误差约 ±10%）；
#   fable-5-1：7106db47 唯一快照 9.21（误差未知）；haiku-4-5：13295440 快照 1.0。未列模型按 0 计。
# 只作排序与量级参考，不是账单。可用 --prices '{"claude-fable":9.2}' 覆盖（按前缀匹配）。
DEFAULT_PRICES = {"claude-sonnet-5": 2.0, "claude-opus-5-5": 2.65, "claude-opus-5": 2.65,
                  "claude-fable-5": 9.21, "claude-haiku-4-5": 1.0}
TOK_PER_ASCII = 0.5
TOK_PER_NONASCII = 1.0
IMG_PX_PER_TOKEN = 700.0

# 线识别：正则 -> 线名。命中次数计分；人类原话权重 5，cwd 每条记录 1，其余文字 1。
LINE_RULES = [
    ("题库线", re.compile(r"题库|DeepSeek_政治题库|MD全库|bank\.py|claude_bank|README_FOR_AI|逐题|packets/|BANK_ACTOR")),
    ("必修二", re.compile(r"必修二|经济与社会|Astra审核|修订2[0-3]\d")),
    ("必修三", re.compile(r"必修三|政治与法治|第\s*(?:4[0-9]|5\d)\s*批|R4\d候选|最终4\d")),
    ("其他", re.compile(r"配置实测|接续测试|how-we-made-claude|usage_profile|用量画像|继续目标|computer use|限额到了|用脚本来操作")),
]
OTHER_BONUS = 3.0  # “其他”类关键词在人类原话里额外加权（配置测试/流程优化类回合）
CWD_RULES = [
    ("题库线", re.compile(r"MD全库流水线|DeepSeek_政治题库|claude_bank")),
    ("必修二", re.compile(r"必修二_")),
    ("必修三", re.compile(r"必修三_")),
]
BATCH_PATTERNS = [
    (re.compile(r"第\s*(\d{1,3})\s*批"), 1.0),
    (re.compile(r"最终(\d{2})(?!\d)"), 1.0),
    (re.compile(r"R(\d{2})候选"), 0.2),
]
REV_PATTERN = re.compile(r"修订(2\d\d)")  # 必修二阶段号

# Bash 命令分类（先按脚本文件名，再按内容关键词；按顺序取第一个命中）
SCRIPT_NAME_RULES = [
    ("同步", re.compile(r"collab\.py")),
    ("题库脚本", re.compile(r"bank\.py|bank_[\w\-]*\.py")),
    ("渲染", re.compile(r"render[\w\-]*\.(?:sh|py)")),
    ("构建", re.compile(r"build[\w\-]*\.py|assemble[\w\-]*\.py|make_[\w\-]*\.py")),
    ("OCR", re.compile(r"ocr[\w\-]*\.(?:py|swift|sh)")),
    ("检查", re.compile(r"(?:check|verify|health|validate|audit|lint|qa)[\w\-]*\.py")),
    ("提取转换", re.compile(r"(?:extract|convert|to_md|md_|intake|dump)[\w\-]*\.py")),
]
CONTENT_RULES = [
    ("等待", re.compile(r"(?:^|[;&|\s])sleep\s+\d|time\.sleep\(\s*\d{2,}")),
    ("渲染", re.compile(r"soffice|libreoffice|--convert-to|docx2pdf|export_pdf|lowriter", re.I)),
    ("OCR", re.compile(r"\bocr|tesseract|paddleocr|rapidocr|VNRecognizeText|ocrmac", re.I)),
    ("PDF转图", re.compile(r"pdftoppm|pdftocairo|get_pixmap|pdf2image|mutool\s+draw|\bsips\b|magick|qlmanage", re.I)),
    ("提取转换", re.compile(r"pdftotext|pandoc|markitdown|python-docx|from docx|import docx|docx2txt|python-pptx|from pptx|"
                           r"textutil|word/document\.xml|pdfplumber|\bfitz\b|pymupdf|zipfile", re.I)),
    ("图片裁剪", re.compile(r"from PIL|import PIL|Image\.open|\.crop\(")),
    ("检查", re.compile(r"check|verify|health|validate|audit|\bdiff\b|\bcmp\b|sha256|shasum|md5|compare", re.I)),
]
ASSIGN_PREFIX = re.compile(r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*=(?:\"[^\"]*\"|'[^']*'|\S*)\s+)+(?=\S)")
# 去掉开头的 cd / 变量赋值 / mkdir / set / export 等“准备段”，看第一条实际命令
PREP_SEG = re.compile(r"^\s*(?:cd\s|mkdir\s|set\s|export\s|source\s|trap\s|umask\s|[A-Za-z_][A-Za-z0-9_]*=|#|$)")
BROWSE_CMD = re.compile(r"^\s*(?:ls|cat|head|tail|grep|egrep|rg|find|sed|wc|stat|du|tree|file|echo|printf|pwd|mdls|open|awk|sort|uniq|jq|cut|diff|basename|dirname|realpath|readlink|test|\[|for|while|if)\b")


# ----------------------------------------------------------------------------- 工具函数
def parse_ts(s):
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return None


def make_tz(spec):
    if spec in (None, "", "local"):
        return datetime.now().astimezone().tzinfo
    m = re.fullmatch(r"([+-])(\d{1,2}):?(\d{2})?", spec)
    if m:
        sign = 1 if m.group(1) == "+" else -1
        return timezone(sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0)))
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(spec)
    except Exception:
        sys.exit("无法识别时区 %r（用 local、+08:00 或 Asia/Shanghai）" % spec)


def parse_bound(s, tz):
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=tz).timestamp()
        except ValueError:
            pass
    sys.exit("无法识别时间 %r" % s)


def fmt_ts(t, tz):
    if t is None:
        return "?"
    return datetime.fromtimestamp(t, tz).strftime("%m-%d %H:%M")


def day_of(t, tz):
    return datetime.fromtimestamp(t, tz).strftime("%Y-%m-%d")


def char_counts(s):
    if not s:
        return 0, 0
    a = len(s.encode("ascii", "ignore"))
    return a, len(s) - a


def image_tokens(block):
    """从 base64 头部解析 PNG/JPEG 宽高，估算 token。解析失败按 1600。"""
    src = block.get("source") or {}
    data = src.get("data") or ""
    if not isinstance(data, str) or not data:
        return 1600
    try:
        head = data[:88000]
        head = head[: len(head) - len(head) % 4]
        raw = base64.b64decode(head)
        w = h = None
        if raw[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", raw[16:24])
        elif raw[:2] == b"\xff\xd8":
            i = 2
            while i + 9 < len(raw):
                if raw[i] != 0xFF:
                    i += 1
                    continue
                marker = raw[i + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h, w = struct.unpack(">HH", raw[i + 5:i + 9])
                    break
                seg = struct.unpack(">H", raw[i + 2:i + 4])[0]
                i += 2 + seg
        if w and h:
            return int(w * h / IMG_PX_PER_TOKEN)
    except Exception:
        pass
    return 1600


def est_tokens(a, n, imgtok=0):
    return a * TOK_PER_ASCII + n * TOK_PER_NONASCII + imgtok


def short(s, n=110):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


WAIT_RX = re.compile(r"(?:^|[;&|\s(])sleep\s+(\d+)")


def classify_bash(cmd):
    c = cmd or ""
    if any(int(x) >= 30 for x in WAIT_RX.findall(c)):
        return "等待"  # 含 sleep≥30s 的命令，耗时主要是等
    for name, rx in SCRIPT_NAME_RULES:
        if rx.search(c):
            return name
    for name, rx in CONTENT_RULES:
        if rx.search(c):
            return name
    first = ""
    for seg in re.split(r"\n|&&|;|\|\|", c):
        seg = ASSIGN_PREFIX.sub("", seg)
        if not PREP_SEG.match(seg):
            first = seg.strip()
            break
    if re.match(r"^(?:/usr/bin/)?python3?\b|^node\b|^swift\b", first):
        if re.search(r"json\.load|json\.loads|\bjq\b", c):
            return "数据查看"
        if re.search(r"re\.(?:findall|search|sub|match)|len\(", c):
            return "临时文本校验"
        return "临时脚本"
    if BROWSE_CMD.match(first):
        return "浏览"
    if re.match(r"^\s*(?:cp|mv|rm|ln|touch|chmod|rsync|ditto|zip|unzip|tar)\b", first):
        return "文件操作"
    return "其他"


def norm_desc(d):
    d = re.sub(r"\d+", "#", d or "")
    return short(d, 40)


def wf_name_from_script(script):
    m = re.search(r"name\s*:\s*['\"]([^'\"]+)['\"]", script or "")
    return m.group(1) if m else None


class Agg(object):
    __slots__ = ("calls", "inp", "cc", "cr", "out", "w", "usd", "models", "batches", "n_threads")

    def __init__(self):
        self.calls = 0
        self.inp = self.cc = self.cr = self.out = 0
        self.w = 0.0
        self.usd = 0.0
        self.models = collections.Counter()
        self.batches = collections.Counter()
        self.n_threads = set()

    def add(self, i, cc, cr, o, w, usd=0.0, model=None, batch=None, thread=None):
        self.calls += 1
        self.inp += i
        self.cc += cc
        self.cr += cr
        self.out += o
        self.w += w
        self.usd += usd
        if model:
            self.models[model] += 1
        if batch:
            self.batches[batch] += 1
        if thread is not None:
            self.n_threads.add(thread)

    @property
    def new(self):
        return self.inp + self.cc + self.out

    @property
    def total(self):
        return self.inp + self.cc + self.cr + self.out

    def to_dict(self):
        d = {"calls": self.calls, "input": self.inp, "cache_creation": self.cc, "cache_read": self.cr,
             "output": self.out, "new_tokens": self.new, "total_tokens": self.total, "weighted": round(self.w),
             "usd_est": round(self.usd, 2)}
        if self.models:
            d["models"] = dict(self.models.most_common())
        if self.batches:
            d["batches"] = dict(self.batches.most_common())
        if self.n_threads:
            d["threads"] = len(self.n_threads)
        return d


# ----------------------------------------------------------------------------- 主体：Claude Code 会话
class Profiler(object):
    def __init__(self, weights, tz, prices=None):
        self.W = weights
        self.prices = prices or dict(DEFAULT_PRICES)
        self._price_cache = {}
        self.tz = tz
        self.seen_msg = set()
        self.seen_tool_use = set()
        self.seen_result = set()
        self.seen_human = {}  # uuid -> seg idx
        self.calls = []  # (ts, model, in, cc, cr, out, thread, seg)
        self.threads = []  # dict
        self.segs = []  # dict
        self.results = []  # dict per tool result
        self.pending = {}  # tool_use_id -> info
        self.file_segs = {}  # session id -> (starts list, seg idx list)
        self.sessions = collections.OrderedDict()
        self.wf_info = {}
        self.wf_names = {}
        self.msg_owner = {}  # message.id -> (文件, calls 下标)
        self.cost_states = {}
        self.dup_records = 0
        self.dup_msgs = 0

    # --- 线与批次打分
    def score_text(self, seg, text, weight=1.0, human=False):
        if not text:
            return
        sc = seg["line_score"]
        for name, rx in LINE_RULES:
            k = len(rx.findall(text))
            if k:
                bonus = OTHER_BONUS if (human and name == "其他") else 1.0
                sc[name] += k * weight * bonus
                if human:
                    seg["human_score"][name] += k * weight * bonus
        bs = seg["batch_score"]
        for rx, bw in BATCH_PATTERNS:
            for m in rx.finditer(text):
                try:
                    n = int(m.group(1))
                except ValueError:
                    continue
                if 30 <= n <= 99:
                    bs[n] += bw * weight
        for m in REV_PATTERN.finditer(text):
            seg["rev_score"][int(m.group(1))] += weight

    def score_cwd(self, seg, cwd):
        if not cwd:
            return
        seg["cwd"][cwd] += 1
        for name, rx in CWD_RULES:
            if rx.search(cwd):
                seg["line_score"][name] += 1.0
                break

    def new_seg(self, sid, ts, text, uuid):
        seg = {"idx": len(self.segs), "session": sid, "start": ts, "end": ts, "uuid": uuid,
               "human": short(text, 160), "line_score": collections.Counter(),
               "batch_score": collections.Counter(), "rev_score": collections.Counter(), "human_score": collections.Counter(),
               "cwd": collections.Counter(), "line": None, "batch": None, "model_time": 0.0}
        self.segs.append(seg)
        return seg

    def new_thread(self, sid, kind, file, **kw):
        th = {"idx": len(self.threads), "session": sid, "kind": kind, "file": file, "calls_n": 0,
              "compactions": [], "first": None, "last": None, "seg": None, "models": collections.Counter(),
              "agent_type": kw.get("agent_type"), "desc": kw.get("desc"), "phase": kw.get("phase"),
              "wf_run": kw.get("wf_run"), "wf_name": kw.get("wf_name"), "agent_id": kw.get("agent_id"),
              "prompt": None, "model_time": 0.0}
        self.threads.append(th)
        return th

    # --- 读工作流元数据
    def load_workflows(self, sdir):
        for f in glob.glob(os.path.join(sdir, "workflows", "wf_*.json")):
            try:
                with open(f, "rb") as fh:
                    d = json.load(fh)
            except Exception:
                continue
            rid = d.get("runId") or os.path.basename(f)[:-5]
            args = d.get("args")
            self.wf_info[rid] = {
                "name": d.get("workflowName") or wf_name_from_script(d.get("script")),
                "start": parse_ts(d.get("timestamp")) if isinstance(d.get("timestamp"), str) else None,
                "duration_s": (d.get("durationMs") or 0) / 1000.0,
                "total_tokens_reported": d.get("totalTokens"), "agent_count": d.get("agentCount"),
                "status": d.get("status"), "args": short(json.dumps(args, ensure_ascii=False), 160) if args else "",
                "script_path": d.get("scriptPath"),
            }

    # --- 解析一个线程文件（主线程或子代理）
    def parse_thread_file(self, path, sid, th, is_main):
        cur_seg = None
        starts, segidx = self.file_segs.setdefault(sid, ([], []))
        last_nonassist_ts = None
        with open(path, "rb") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                typ = d.get("type")
                if typ == "cost-state" and is_main:
                    if d.get("modelUsage"):
                        self.cost_states[sid] = {"totalCostUSD": d.get("totalCostUSD"), "modelUsage": d.get("modelUsage")}
                    continue
                if typ not in ("assistant", "user"):
                    continue
                if is_main and (d.get("isSidechain") or d.get("agentId")):
                    continue  # 老版本把子代理写在主文件；本脚本只从 subagents/ 读，避免重复
                ts = parse_ts(d.get("timestamp"))
                msg = d.get("message") or {}
                content = msg.get("content")
                if typ == "user":
                    # 人类回合
                    if is_main and not d.get("isMeta") and not d.get("isCompactSummary"):
                        origin = (d.get("origin") or {}).get("kind")
                        text = None
                        if isinstance(content, str):
                            text = content
                        elif isinstance(content, list) and not any(
                                isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                            text = "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
                        if text and (origin == "human" or (origin is None and not text.lstrip().startswith(("<", "[Request", "This session")))):
                            if not self.sessions[sid].get("file_first_human"):
                                self.sessions[sid]["file_first_human"] = short(text, 120)
                            uuid = d.get("uuid")
                            if uuid in self.seen_human:
                                cur_seg = self.segs[self.seen_human[uuid]]
                            else:
                                cur_seg = self.new_seg(sid, ts, text, uuid)
                                self.seen_human[uuid] = cur_seg["idx"]
                                self.score_text(cur_seg, text, 5.0, human=True)
                            pos = bisect.bisect_right(starts, cur_seg["start"] or 0)
                            if not (pos > 0 and segidx[pos - 1] == cur_seg["idx"]):
                                starts.insert(pos, cur_seg["start"] or 0)
                                segidx.insert(pos, cur_seg["idx"])
                    if d.get("isCompactSummary"):
                        th["compactions"].append(th["calls_n"])
                    if not is_main and th["prompt"] is None and isinstance(content, (str, list)):
                        th["prompt"] = short(content if isinstance(content, str) else
                                             " ".join(b.get("text", "") for b in content if isinstance(b, dict)), 200)
                    if isinstance(content, list):
                        for b in content:
                            if not isinstance(b, dict) or b.get("type") != "tool_result":
                                continue
                            tid = b.get("tool_use_id")
                            if tid in self.seen_result:
                                continue
                            self.seen_result.add(tid)
                            info = self.pending.pop(tid, None)
                            c = b.get("content")
                            a = n = imgs = imgtok = 0
                            if isinstance(c, str):
                                a, n = char_counts(c)
                            elif isinstance(c, list):
                                for x in c:
                                    if not isinstance(x, dict):
                                        continue
                                    if x.get("type") == "text":
                                        aa, nn = char_counts(x.get("text"))
                                        a += aa
                                        n += nn
                                    elif x.get("type") == "image":
                                        imgs += 1
                                        imgtok += image_tokens(x)
                            if info is None:
                                info = {"name": "?", "ts": None, "summary": "", "cat": None, "bg": False}
                            dur = (ts - info["ts"]) if (ts and info["ts"]) else None
                            tur = d.get("toolUseResult")
                            bg = info["bg"] or (isinstance(tur, dict) and bool(tur.get("backgroundTaskId")))
                            if isinstance(tur, dict) and tur.get("runId") and tur.get("workflowName"):
                                self.wf_names[tur["runId"]] = tur["workflowName"]
                                bg = bg or tur.get("status") == "async_launched"
                            if info["name"] in ("Agent", "Task") and isinstance(tur, dict) and tur.get("isAsync"):
                                bg = True
                            if info["name"] == "Read":
                                ext = os.path.splitext(info["summary"])[1].lower() or "(无扩展名)"
                                info["cat"] = ("图片" if imgs else "文本") + ext
                            self.results.append({
                                "thread": th["idx"], "name": info["name"], "cat": info["cat"], "ts": info["ts"] or ts,
                                "dur": None if bg else dur, "bg": bg, "a": a, "n": n, "imgs": imgs, "imgtok": imgtok,
                                "est": est_tokens(a, n, imgtok), "pos": th["calls_n"], "summary": info["summary"],
                                "seg": cur_seg["idx"] if (is_main and cur_seg) else None,
                                "error": bool(b.get("is_error")),
                            })
                    if ts:
                        last_nonassist_ts = ts
                    continue

                # assistant
                mid = msg.get("id")
                model = msg.get("model")
                u = msg.get("usage") or {}
                call = None
                if mid and mid in self.seen_msg:
                    self.dup_records += 1
                    new_msg = False
                    own = self.msg_owner.get(mid)
                    if own and own[0] == path and own[1] is not None:
                        call = self.calls[own[1]]  # 同一文件里同一消息的后续块：补字数与最终 usage
                        call[5] = max(call[5], u.get("output_tokens") or 0)
                        if msg.get("stop_reason"):
                            call[9] = True
                else:
                    new_msg = True
                    if mid:
                        self.seen_msg.add(mid)
                        self.msg_owner[mid] = (path, None)
                if new_msg and model and model != "<synthetic>":
                    i = u.get("input_tokens") or 0
                    cc = u.get("cache_creation_input_tokens") or 0
                    cr = u.get("cache_read_input_tokens") or 0
                    o = u.get("output_tokens") or 0
                    segi = cur_seg["idx"] if (is_main and cur_seg) else None
                    call = [ts or 0, model, i, cc, cr, o, th["idx"], segi, 0.0, bool(msg.get("stop_reason")), o]
                    if mid:
                        self.msg_owner[mid] = (path, len(self.calls))
                    self.calls.append(call)
                    th["calls_n"] += 1
                    th["models"][model] += 1
                    if ts and last_nonassist_ts and 0 < ts - last_nonassist_ts < 1800:
                        th["model_time"] += ts - last_nonassist_ts
                        if is_main and cur_seg:
                            cur_seg["model_time"] += ts - last_nonassist_ts
                if ts:
                    th["first"] = th["first"] or ts
                    th["last"] = ts
                    if is_main and cur_seg:
                        cur_seg["end"] = max(cur_seg["end"] or ts, ts)
                if is_main and cur_seg is not None and new_msg:
                    self.score_cwd(cur_seg, d.get("cwd"))
                if not isinstance(content, list):
                    continue
                if call is not None:
                    for b in content:
                        if not isinstance(b, dict):
                            continue
                        bt = b.get("type")
                        if bt == "text":
                            aa, nn = char_counts(b.get("text"))
                        elif bt == "tool_use":
                            aa, nn = char_counts(json.dumps(b.get("input"), ensure_ascii=False))
                        elif bt == "thinking":
                            aa, nn = char_counts(b.get("thinking"))
                        else:
                            continue
                        call[8] += est_tokens(aa, nn)
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    bt = b.get("type")
                    if bt == "text" and is_main and cur_seg is not None and call is not None:
                        self.score_text(cur_seg, b.get("text", "")[:6000])
                    elif bt == "tool_use":
                        tid = b.get("id")
                        if tid in self.seen_tool_use:
                            continue
                        self.seen_tool_use.add(tid)
                        name = b.get("name") or "?"
                        inp = b.get("input") or {}
                        summary, cat, bg = "", None, False
                        if name == "Bash":
                            cmd = inp.get("command", "")
                            summary = (inp.get("description") or "") + " | " + short(cmd, 160)
                            cat = classify_bash(cmd)
                            bg = bool(inp.get("run_in_background"))
                        elif name in ("Read", "Write", "Edit", "NotebookEdit"):
                            summary = inp.get("file_path", "")
                        elif name in ("Agent", "Task"):
                            summary = "%s: %s" % (inp.get("subagent_type", ""), inp.get("description", ""))
                            bg = bool(inp.get("run_in_background"))
                        elif name == "Workflow":
                            summary = wf_name_from_script(inp.get("script")) or inp.get("name") or ""
                        elif name in ("Grep", "Glob"):
                            summary = inp.get("pattern", "")
                        else:
                            summary = short(json.dumps(inp, ensure_ascii=False), 120)
                        self.pending[tid] = {"name": name, "ts": ts, "summary": short(summary, 200), "cat": cat, "bg": bg}
                        if is_main and cur_seg is not None:
                            self.score_text(cur_seg, json.dumps(inp, ensure_ascii=False)[:4000])

    # --- 一个会话（主文件 + 目录）
    def add_session(self, main_path):
        sid = os.path.basename(main_path)[:-6]
        sdir = main_path[:-6]
        title = None
        tf = os.path.join(sdir, "custom-title.json")
        if os.path.exists(tf):
            try:
                with open(tf) as fh:
                    title = json.load(fh).get("customTitle")
            except Exception:
                pass
        self.sessions[sid] = {"id": sid, "file": main_path, "title": title, "size_mb": round(os.path.getsize(main_path) / 1048576, 1)}
        mth = self.new_thread(sid, "主线程", main_path)
        before = len(self.seen_msg)
        self.parse_thread_file(main_path, sid, mth, True)
        self.sessions[sid]["new_msgs"] = len(self.seen_msg) - before
        self.sessions[sid]["main_thread"] = mth["idx"]
        self.load_workflows(sdir)
        sub_files = sorted(glob.glob(os.path.join(sdir, "subagents", "**", "agent-*.jsonl"), recursive=True))
        self.sessions[sid]["subagent_files"] = len(sub_files)
        for f in sub_files:
            meta = {}
            mf = f[:-6] + ".meta.json"
            if os.path.exists(mf):
                try:
                    with open(mf) as fh:
                        meta = json.load(fh)
                except Exception:
                    meta = {}
            m = re.search(r"/workflows/(wf_[^/]+)/", f)
            wf_run = m.group(1) if m else None
            kind = "工作流代理" if wf_run else "子代理"
            wf_name = ((self.wf_info.get(wf_run) or {}).get("name") or self.wf_names.get(wf_run)) if wf_run else None
            th = self.new_thread(sid, kind, f, agent_type=meta.get("agentType") or "general-purpose",
                                 desc=meta.get("description"), phase=meta.get("workflowPhase"),
                                 wf_run=wf_run, wf_name=wf_name or (wf_run and "未知工作流"),
                                 agent_id=os.path.basename(f)[6:-6])
            self.parse_thread_file(f, sid, th, False)

    # --- 结束后：回合分类、线程归属
    def finalize(self):
        # 输出 token：流式中途落盘的记录（无 stop_reason）只有 message_start 的 output_tokens，
        # 用正文+工具入参字数估计取大；思考 token 在记录中不可见，因此输出仍是下限。
        self.out_stats = {"calls": len(self.calls), "final": 0, "estimated": 0, "recorded_out": 0, "est_out": 0}
        for c in self.calls:
            self.out_stats["recorded_out"] += c[10]
            if c[9]:
                self.out_stats["final"] += 1
            else:
                est = int(c[8])
                if est > c[5]:
                    c[5] = est
                    self.out_stats["estimated"] += 1
            self.out_stats["est_out"] += c[5]
        # 回合 -> 线
        sess_line_score = collections.defaultdict(collections.Counter)
        for s in self.segs:
            sess_line_score[s["session"]].update(s["line_score"])
        self.session_default = {}
        for sid, sc in sess_line_score.items():
            self.session_default[sid] = sc.most_common(1)[0][0] if sc else "其他"
        # 回合的线：①人类原话明确是“其他”类（配置测试/流程优化/定时点按等）就归其他；②否则看本回合全部文字
        # （人类原话×5 + 助手文字 + 工具入参 + cwd，反映实际干了哪条线的活；人类原话里“像必修二那样”之类的
        # 比较不会压过实际工作）；③分数太低就承接同文件上一回合；④再不行用会话默认。
        for s in sorted(self.segs, key=lambda x: x["start"] or 0):
            hs = s["human_score"].most_common(1)
            if hs and hs[0][0] == "其他" and hs[0][1] >= 5:
                s["line"], s["line_basis"] = "其他", "人类原话"
                continue
            sc = s["line_score"]
            if sc and sc.most_common(1)[0][1] >= 3:
                s["line"], s["line_basis"] = sc.most_common(1)[0][0], "本回合文字"
                continue
            starts, segidx = self.file_segs.get(s["session"], ([], []))
            prev = None
            if s["idx"] in segidx:
                k = segidx.index(s["idx"])
                if k > 0:
                    prev = self.segs[segidx[k - 1]]
            if prev is not None and prev.get("line"):
                s["line"], s["line_basis"] = prev["line"], "承接上一回合"
            else:
                s["line"] = self.session_default.get(s["session"], "其他")
                s["line_basis"] = "会话默认"
        # 批次：按线按时间单调承接
        cur = {}
        for s in sorted(self.segs, key=lambda x: x["start"] or 0):
            line = s["line"]
            if line == "必修三":
                bs = s["batch_score"]
                cand = None
                if bs:
                    top = max(bs.values())
                    ok = [n for n, v in bs.items() if v >= max(3.0, 0.25 * top)]
                    if ok:
                        cand = max(ok)
                prev = cur.get(line)
                b = max([x for x in (prev, cand) if x is not None]) if (prev or cand) else None
                cur[line] = b
                s["batch"] = ("第%d批" % b) if b else "批次未识别"
            elif line == "必修二":
                rs = s["rev_score"]
                cand = max(rs) if rs else None
                prev = cur.get(line)
                b = max([x for x in (prev, cand) if x is not None]) if (prev or cand) else None
                cur[line] = b
                s["batch"] = ("修订%d" % b) if b else "阶段未识别"
            else:
                s["batch"] = day_of(s["start"], self.tz) if s["start"] else "?"
        # 线程 -> 回合
        for th in self.threads:
            if th["kind"] == "主线程":
                continue
            starts, segidx = self.file_segs.get(th["session"], ([], []))
            t = th["first"] or 0
            if starts:
                p = bisect.bisect_right(starts, t) - 1
                th["seg"] = segidx[max(p, 0)]
        # 结果 -> 回合（子代理结果跟线程）
        for r in self.results:
            if r["seg"] is None:
                r["seg"] = self.threads[r["thread"]]["seg"]
        # 滞留成本：其后同上下文 API 调用次数
        for r in self.results:
            th = self.threads[r["thread"]]
            end = th["calls_n"]
            for c in th["compactions"]:
                if c > r["pos"]:
                    end = min(end, c)
                    break
            r["later"] = max(0, end - r["pos"])
            r["carried"] = r["est"] * r["later"]

    def price(self, model):
        if model not in self._price_cache:
            best = 0.0
            blen = -1
            for k, v in self.prices.items():
                if (model or "").startswith(k) and len(k) > blen:
                    best, blen = v, len(k)
            self._price_cache[model] = best
        return self._price_cache[model]

    def seg_of_call(self, c):
        segi = c[7]
        if segi is None:
            segi = self.threads[c[6]]["seg"]
        return self.segs[segi] if segi is not None else None

    def thread_label(self, th):
        if th["kind"] == "主线程":
            return "主线程"
        if th["kind"] == "工作流代理":
            return "工作流 %s·%s·%s" % (th["wf_name"], th["phase"] or "-", th["agent_type"])
        return "子代理 %s" % th["agent_type"]

    # --- 汇总
    def aggregate(self, since=None, until=None, line_filter=None, session_filter=None):
        W = self.W
        G = collections.defaultdict(lambda: collections.defaultdict(Agg))
        thread_agg = collections.defaultdict(Agg)
        seg_main_agg = collections.defaultdict(Agg)
        wfrun_agg = collections.defaultdict(Agg)
        top_calls = []
        rebuilds = Agg()
        # 轮询：主线程在 sleep 等待 / TaskOutput 之后的那次 API 调用（每次都要整段读一遍主线程上下文）
        main_pos = collections.defaultdict(list)
        for ci, c in enumerate(self.calls):
            if self.threads[c[6]]["kind"] == "主线程":
                main_pos[c[6]].append(ci)
        poll_calls = set()
        for r in self.results:
            if (r["cat"] == "等待" or r["name"] == "TaskOutput") and self.threads[r["thread"]]["kind"] == "主线程":
                lst = main_pos.get(r["thread"]) or []
                if r["pos"] < len(lst):
                    poll_calls.add(lst[r["pos"]])
        polling = collections.defaultdict(Agg)
        for ci, c in enumerate(self.calls):
            ts, model, i, cc, cr, o, thi = c[:7]
            if since and ts < since:
                continue
            if until and ts >= until:
                continue
            th = self.threads[thi]
            seg = self.seg_of_call(c)
            line = seg["line"] if seg else self.session_default.get(th["session"], "其他")
            batch = seg["batch"] if seg else "?"
            if line_filter and line != line_filter:
                continue
            if session_filter and not any(th["session"].startswith(x) for x in session_filter):
                continue
            w = i * W["input"] + cc * W["cache_creation"] + cr * W["cache_read"] + o * W["output"]
            kind = th["kind"]
            label = self.thread_label(th)
            args = (i, cc, cr, o, w, w * self.price(model) / 1e6)
            G["总计"]["全部"].add(*args, model=model, batch=batch, thread=thi)
            G["按线"][line].add(*args, model=model, thread=thi)
            G["按线×批次"][(line, batch)].add(*args, model=model, thread=thi)
            G["按线×批次×线程类型"][(line, batch, kind)].add(*args, model=model, thread=thi)
            G["按模型"][model].add(*args, thread=thi)
            G["按线×模型"][(line, model)].add(*args, thread=thi)
            G["按日期"][day_of(ts, self.tz) if ts else "?"].add(*args, model=model, thread=thi)
            G["按线程类型"][kind].add(*args, model=model, thread=thi)
            G["按线×线程类型"][(line, kind)].add(*args, model=model, thread=thi)
            G["按会话"][th["session"]].add(*args, model=model, thread=thi)
            if kind != "主线程":
                G["按子代理类型"][(line, th["agent_type"])].add(*args, model=model, batch=batch, thread=thi)
            if kind == "子代理":
                G["按子代理描述"][(line, th["agent_type"], norm_desc(th["desc"]))].add(*args, model=model, batch=batch, thread=thi)
            if kind == "工作流代理":
                G["按工作流阶段"][(line, th["wf_name"], th["phase"] or "-")].add(*args, model=model, batch=batch, thread=thi)
                G["工作流代理×模型"][(line, model, th["agent_type"])].add(*args, batch=batch, thread=thi)
                wfrun_agg[(th["session"], th["wf_run"])].add(*args, model=model, batch=batch, thread=thi)
            key_env = (line, label if kind != "主线程" else "主线程(%s)" % model)
            G["环节"][key_env].add(*args, model=model, batch=batch, thread=thi)
            thread_agg[thi].add(*args, model=model, batch=batch)
            if kind == "主线程" and seg:
                seg_main_agg[seg["idx"]].add(*args, model=model, batch=batch)
            if ci in poll_calls:
                polling[line].add(*args, model=model, batch=batch, thread=thi)
            # 缓存重建：大量 cache_creation 且 cache_read 很少
            if cc >= 50000 and cr < cc:
                rebuilds.add(*args, model=model, batch=batch, thread=thi)
            item = (w, ts, thi, i, cc, cr, o, model)
            if len(top_calls) < 30:
                heapq.heappush(top_calls, item)
            elif w > top_calls[0][0]:
                heapq.heapreplace(top_calls, item)

        # 工具
        tools = collections.defaultdict(lambda: {"calls": 0, "errors": 0, "chars": 0, "images": 0, "est_tokens": 0.0,
                                                 "carried_tokens": 0.0, "dur_s": 0.0, "timed": 0})
        bash = collections.defaultdict(lambda: {"count": 0, "bg": 0, "durs": [], "est_tokens": 0.0, "carried_tokens": 0.0})
        bash_by_line = collections.defaultdict(lambda: collections.defaultdict(lambda: {"count": 0, "dur_s": 0.0}))
        readcat = collections.defaultdict(lambda: {"count": 0, "images": 0, "est_tokens": 0.0, "carried_tokens": 0.0})
        envmix = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0.0, 0.0]))
        timing = collections.defaultdict(lambda: collections.defaultdict(float))
        top_bash, top_carried = [], []
        for r in self.results:
            ts = r["ts"] or 0
            if since and ts < since:
                continue
            if until and ts >= until:
                continue
            th = self.threads[r["thread"]]
            seg = self.segs[r["seg"]] if r["seg"] is not None else None
            line = seg["line"] if seg else self.session_default.get(th["session"], "其他")
            if line_filter and line != line_filter:
                continue
            if session_filter and not any(th["session"].startswith(x) for x in session_filter):
                continue
            envk = (line, self.thread_label(th) if th["kind"] != "主线程" else
                    "主线程(%s)" % (th["models"].most_common(1)[0][0] if th["models"] else "?"))
            em = envmix[envk]
            tk = r["name"] + ("·" + r["cat"] if r["cat"] else "")
            em[tk][0] += 1
            em[tk][1] += r["est"]
            em[tk][2] += r["carried"]
            t = tools[r["name"]]
            t["calls"] += 1
            t["errors"] += int(r["error"])
            t["chars"] += r["a"] + r["n"]
            t["images"] += r["imgs"]
            t["est_tokens"] += r["est"]
            t["carried_tokens"] += r["carried"]
            if r["dur"] is not None:
                t["dur_s"] += r["dur"]
                t["timed"] += 1
            if r["name"] == "Read":
                rc = readcat[r["cat"] or "?"]
                rc["count"] += 1
                rc["images"] += r["imgs"]
                rc["est_tokens"] += r["est"]
                rc["carried_tokens"] += r["carried"]
            if r["name"] == "Bash" and r["dur"] is not None and not r["bg"]:
                who = "主线程" if th["kind"] == "主线程" else "子代理/工作流"
                timing[line]["Bash前台·" + who] += r["dur"]
                if r["cat"] == "等待":
                    timing[line]["其中 sleep 等待·" + who] += r["dur"]
                    timing[line]["sleep 次数·" + who] += 1
            if r["name"] == "Bash":
                b = bash[r["cat"] or "其他"]
                b["count"] += 1
                b["est_tokens"] += r["est"]
                b["carried_tokens"] += r["carried"]
                if r["bg"]:
                    b["bg"] += 1
                elif r["dur"] is not None:
                    b["durs"].append(r["dur"])
                    bl = bash_by_line[line][r["cat"] or "其他"]
                    bl["count"] += 1
                    bl["dur_s"] += r["dur"]
                    item = (r["dur"], ts, r["thread"], r["cat"], r["summary"], seg["batch"] if seg else "?")
                    if len(top_bash) < 20:
                        heapq.heappush(top_bash, item)
                    elif item[0] > top_bash[0][0]:
                        heapq.heapreplace(top_bash, item)
            item = (r["carried"], ts, r["thread"], r["name"], r["summary"], r["est"], r["later"], r["imgs"])
            if len(top_carried) < 20:
                heapq.heappush(top_carried, item)
            elif item[0] > top_carried[0][0]:
                heapq.heapreplace(top_carried, item)
        # 墙钟与模型时间
        for segi, a in seg_main_agg.items():
            sg = self.segs[segi]
            timing[sg["line"]]["主线程回合墙钟"] += max(0.0, (sg["end"] or 0) - (sg["start"] or 0))
            timing[sg["line"]]["主线程模型生成"] += sg["model_time"]
            timing[sg["line"]]["人类回合数"] += 1
        for (sid, run), a in wfrun_agg.items():
            info = self.wf_info.get(run) or {}
            ths = [self.threads[t] for t in a.n_threads]
            d = info.get("duration_s") or (max((t["last"] or 0) for t in ths) - min((t["first"] or 0) for t in ths))
            sg = self.segs[ths[0]["seg"]] if ths and ths[0]["seg"] is not None else None
            ln = sg["line"] if sg else self.session_default.get(sid, "其他")
            timing[ln]["工作流运行墙钟"] += d
            timing[ln]["工作流运行数"] += 1
            timing[ln]["工作流代理数"] += len(ths)
        for thi, a in thread_agg.items():
            th = self.threads[thi]
            if th["kind"] == "子代理":
                sg = self.segs[th["seg"]] if th["seg"] is not None else None
                ln = sg["line"] if sg else self.session_default.get(th["session"], "其他")
                timing[ln]["子代理运行墙钟"] += max(0.0, (th["last"] or 0) - (th["first"] or 0))
                timing[ln]["子代理数"] += 1
        return {"G": G, "thread_agg": thread_agg, "seg_main_agg": seg_main_agg, "wfrun_agg": wfrun_agg,
                "readcat": readcat, "timing": timing, "polling": polling, "envmix": envmix,
                "top_calls": sorted(top_calls, reverse=True), "rebuilds": rebuilds, "tools": tools, "bash": bash,
                "bash_by_line": bash_by_line, "top_bash": sorted(top_bash, reverse=True),
                "top_carried": sorted(top_carried, reverse=True)}

    # --- 会话判定表
    def session_table(self):
        rows = []
        calls_by_sess_line = collections.defaultdict(collections.Counter)
        w_by_sess_line = collections.defaultdict(collections.Counter)
        for c in self.calls:
            th = self.threads[c[6]]
            seg = self.seg_of_call(c)
            line = seg["line"] if seg else self.session_default.get(th["session"], "其他")
            calls_by_sess_line[th["session"]][line] += 1
            w_by_sess_line[th["session"]][line] += c[2] * self.W["input"] + c[3] * self.W["cache_creation"] + \
                c[4] * self.W["cache_read"] + c[5] * self.W["output"]
        for sid, s in self.sessions.items():
            segs = [x for x in self.segs if x["session"] == sid]
            kw = collections.Counter()
            cwd = collections.Counter()
            for x in segs:
                kw.update(x["line_score"])
                cwd.update(x["cwd"])
            mth = self.threads[s["main_thread"]]
            wl = w_by_sess_line.get(sid, collections.Counter())
            tot = sum(wl.values()) or 1
            main_line = wl.most_common(1)[0][0] if wl else ("（副本，无新调用）" if s["new_msgs"] == 0 else
                                                              self.session_default.get(sid, "其他"))
            first_h = segs[0]["human"] if segs else ""
            bases = collections.Counter(x.get("line_basis") for x in segs)
            rows.append({
                "session": sid, "title": s.get("title"), "size_mb": s["size_mb"], "subagent_files": s["subagent_files"],
                "first": mth["first"], "last": mth["last"], "new_msgs_main": s["new_msgs"],
                "copied_from_other_file": (mth["calls_n"] == 0 and s["new_msgs"] == 0),
                "line": main_line, "line_share": {k: round(v / tot, 3) for k, v in wl.most_common()},
                "keyword_score": {k: round(v, 1) for k, v in kw.most_common()},
                "cwd_top": [[k, v] for k, v in cwd.most_common(3)],
                "first_human": first_h, "file_first_human": s.get("file_first_human"), "human_turns": len(segs),
                "turn_line_basis": dict(bases),
                "turn_lines": dict(collections.Counter(x["line"] for x in segs)),
                "cost_state_usd": (self.cost_states.get(sid) or {}).get("totalCostUSD"),
            })
        return rows


# ----------------------------------------------------------------------------- Codex rollout
def codex_file_meta(path):
    try:
        with open(path, "rb") as fh:
            d = json.loads(fh.readline())
        p = d.get("payload") or {}
        src = p.get("source")
        return {"cwd": p.get("cwd"), "thread_source": p.get("thread_source"), "id": p.get("id"),
                "parent": p.get("parent_thread_id") or (isinstance(src, dict) and ((src.get("subagent") or {}).get("thread_spawn") or {}).get("parent_thread_id")),
                "nickname": p.get("agent_nickname"), "ts": d.get("timestamp")}
    except Exception:
        return None


def parse_codex(path, W, tz):
    meta = codex_file_meta(path) or {}
    seen = set()
    by_model = collections.defaultdict(Agg)
    by_date = collections.defaultdict(Agg)
    model = None
    n_tc = 0
    last_tc = None
    tools = collections.Counter()
    exec_cats = collections.Counter()
    pending = {}
    durs = collections.defaultdict(list)
    user_text = []
    first = last = None
    with open(path, "rb") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            typ = d.get("type")
            p = d.get("payload") if isinstance(d.get("payload"), dict) else {}
            ts = parse_ts(d.get("timestamp"))
            if ts:
                first = first or ts
                last = ts
            if typ == "turn_context":
                model = p.get("model") or model
            elif typ == "token_usage_record":
                rid = p.get("response_id")
                if rid in seen:
                    continue
                seen.add(rid)
                u = p.get("usage") or {}
                inp = u.get("input_tokens") or 0
                cached = u.get("cached_input_tokens") or 0
                cw = u.get("cache_write_input_tokens") or 0
                out = u.get("output_tokens") or 0
                i = max(0, inp - cached - cw)
                w = i * W["input"] + cw * W["cache_creation"] + cached * W["cache_read"] + out * W["output"]
                by_model[model or "?"].add(i, cw, cached, out, w)
                by_date[day_of(ts, tz) if ts else "?"].add(i, cw, cached, out, w, model=model)
            elif typ == "event_msg" and p.get("type") == "token_count":
                n_tc += 1
                last_tc = (p.get("info") or {}).get("total_token_usage")
            elif typ == "response_item":
                pt = p.get("type")
                if pt in ("function_call", "custom_tool_call"):
                    name = p.get("name") or "?"
                    tools[name] += 1
                    body = p.get("arguments") if pt == "function_call" else p.get("input")
                    cats = []
                    if isinstance(body, str):
                        for m in re.finditer(r"\bcmd\s*[:=]\s*(?:\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)'|`([^`]*)`)", body):
                            cats.append(classify_bash(m.group(1) or m.group(2) or m.group(3) or ""))
                        if name == "exec_command" and not cats:
                            try:
                                cats.append(classify_bash(json.loads(body).get("cmd", "")))
                            except Exception:
                                pass
                    for c in cats:
                        exec_cats[c] += 1
                    pending[p.get("call_id")] = (ts, cats[0] if len(cats) == 1 else ("多命令" if cats else name))
                elif pt in ("function_call_output", "custom_tool_call_output"):
                    x = pending.pop(p.get("call_id"), None)
                    if x and x[0] and ts:
                        durs[x[1]].append(ts - x[0])
                elif pt == "message" and p.get("role") == "user" and len(user_text) < 3:
                    for c in p.get("content") or []:
                        if isinstance(c, dict) and c.get("type") in ("input_text", "text"):
                            t = c.get("text", "")
                            if not t.startswith("<") and "AGENTS.md" not in t[:200]:
                                user_text.append(short(t, 160))
    total = Agg()
    for a in by_model.values():
        total.calls += a.calls
        total.inp += a.inp
        total.cc += a.cc
        total.cr += a.cr
        total.out += a.out
        total.w += a.w
    line = "其他"
    txt = " ".join(user_text) + " " + (meta.get("cwd") or "")
    best = 0
    for name, rx in LINE_RULES:
        k = len(rx.findall(txt))
        if k > best:
            best, line = k, name
    return {
        "file": path, "size_mb": round(os.path.getsize(path) / 1048576, 1), "meta": meta, "model_last": model,
        "first": first, "last": last, "records_token_usage": len(seen), "token_count_events": n_tc,
        "total": total.to_dict(), "by_model": {k: v.to_dict() for k, v in by_model.items()},
        "by_date": {k: v.to_dict() for k, v in by_date.items()},
        "last_cumulative_token_count": last_tc, "tools": dict(tools.most_common()),
        "exec_categories": dict(exec_cats.most_common()),
        "tool_durations_s": {k: {"n": len(v), "sum": round(sum(v), 1), "max": round(max(v), 1)} for k, v in durs.items()},
        "user_text": user_text, "line_guess": line,
    }


def codex_scan(root, dates, cwd_rx, sample):
    files = []
    for dt in dates:
        y, m, d = dt.split("-")
        for f in glob.glob(os.path.join(root, y, m, d, "rollout-*.jsonl")):
            meta = codex_file_meta(f)
            if not meta or not re.search(cwd_rx, meta.get("cwd") or ""):
                continue
            files.append((f, meta, os.path.getsize(f)))
    # 抽样：优先根会话（user 发起），再按大小取中等规模的若干个
    roots = [x for x in files if x[1].get("thread_source") == "user"]
    subs = sorted([x for x in files if x[1].get("thread_source") != "user"], key=lambda x: -x[2])
    picked = roots[: max(1, sample // 2)] + subs[: max(0, sample - min(len(roots), max(1, sample // 2)))]
    return [x[0] for x in picked][:sample], len(files)


# ----------------------------------------------------------------------------- 报告
def fm(n):
    n = float(n or 0)
    if abs(n) >= 1e9:
        return "%.2fB" % (n / 1e9)
    if abs(n) >= 1e6:
        return "%.1fM" % (n / 1e6)
    if abs(n) >= 1e3:
        return "%.1fK" % (n / 1e3)
    return "%d" % n


def pct(a, b):
    return "%.1f%%" % (100.0 * a / b) if b else "-"


def dur_h(s):
    s = float(s or 0)
    if s >= 3600:
        return "%.1fh" % (s / 3600)
    if s >= 60:
        return "%.1fmin" % (s / 60)
    return "%.0fs" % s


AGG_TOTAL_USD = [0.0]


def agg_row(k, a, tot_w):
    ctx = (a.inp + a.cc + a.cr) / a.calls if a.calls else 0
    return "%-46s 调用%6d  新%7s  读缓存%8s  输出%7s  加权%7s  ≈$%7.0f %6s  均上下文%6s" % (
        short(k, 46), a.calls, fm(a.new), fm(a.cr), fm(a.out), fm(a.w), a.usd, pct(a.usd, AGG_TOTAL_USD[0]), fm(ctx))


def build_report(P, R, args, sess_rows, codex_results):
    tz = P.tz
    out = []
    G = R["G"]
    tot = G["总计"].get("全部") or Agg()
    tw = tot.w
    AGG_TOTAL_USD[0] = tot.usd
    out.append("用量画像（usage_profile.py）  生成于 %s" % datetime.now(tz).strftime("%Y-%m-%d %H:%M %Z"))
    out.append("范围：%s  since=%s until=%s  line=%s" % (
        ", ".join(os.path.basename(x) for x in args.inputs) or "-", args.since or "-", args.until or "-", args.line or "全部"))
    out.append("去重：唯一 API 调用 %d 次；跨文件/同消息重复记录 %d 条已跳过。加权当量=in×%g+写缓存×%g+读缓存×%g+出×%g（相对量）。" % (
        len(P.calls), P.dup_records, P.W["input"], P.W["cache_creation"], P.W["cache_read"], P.W["output"]))
    os_ = getattr(P, "out_stats", None)
    if os_ and os_["calls"]:
        out.append("输出口径：同一消息的多条记录里，首条的 output_tokens 只是流式开头值（首条合计 %s），取各条最大值；"
                   "%d/%d 次调用有最终 usage，其余 %d 次按正文+工具入参字数估计（思考不可见，为下限）。采用值合计 %s。"
                   "输入侧（input/写缓存/读缓存）各条一致。" % (
                       fm(os_["recorded_out"]), os_["final"], os_["calls"], os_["estimated"], fm(os_["est_out"])))
    out.append("")
    out.append("== 总计")
    out.append("调用 %d  输入 %s  写缓存 %s  读缓存 %s  输出 %s  | 新token %s  总 %s  加权 %s  ≈$%.0f（读缓存占总 token %s，占加权 %s）" % (
        tot.calls, fm(tot.inp), fm(tot.cc), fm(tot.cr), fm(tot.out), fm(tot.new), fm(tot.total), fm(tot.w), tot.usd,
        pct(tot.cr, tot.total), pct(tot.cr * P.W["cache_read"], tot.w)))
    out.append("美元为按 cost-state 反推单价的估算（sonnet-5 精确；opus-5-5 约±10%；fable-5-1 仅一个快照），只作量级与排序参考。")

    def section(title, key, sort_key=None, limit=40, fmtkey=None):
        g = G.get(key) or {}
        if not g:
            return
        out.append("")
        out.append("== " + title)
        items = sorted(g.items(), key=sort_key or (lambda kv: (-kv[1].usd, -kv[1].w)))
        for k, a in items[:limit]:
            out.append(agg_row(fmtkey(k) if fmtkey else (" / ".join(map(str, k)) if isinstance(k, tuple) else str(k)), a, tw))

    section("按线", "按线")
    section("按线 × 线程类型", "按线×线程类型")
    section("按线 × 批次（时间顺序）", "按线×批次", sort_key=lambda kv: (kv[0][0], kv[0][1]))
    # 批次内主线程/子代理占比
    g = G.get("按线×批次×线程类型") or {}
    if g:
        out.append("")
        out.append("== 批次内 主线程 / 子代理 / 工作流代理 占比（按估算美元）")
        byb = collections.defaultdict(dict)
        for (line, batch, kind), a in g.items():
            byb[(line, batch)][kind] = a
        for k in sorted(byb):
            parts = byb[k]
            s = sum(a.usd for a in parts.values()) or 1e-9
            out.append("%-22s ≈$%6.0f  主线程%6s  子代理%6s  工作流代理%6s   读缓存%8s 新%7s 输出%7s" % (
                " / ".join(k), s, pct(parts.get("主线程", Agg()).usd, s), pct(parts.get("子代理", Agg()).usd, s),
                pct(parts.get("工作流代理", Agg()).usd, s), fm(sum(a.cr for a in parts.values())),
                fm(sum(a.new for a in parts.values())), fm(sum(a.out for a in parts.values()))))
    section("按模型", "按模型")
    section("按线 × 模型", "按线×模型")
    section("按日期（%s）" % (args.tz or "local"), "按日期", sort_key=lambda kv: kv[0])
    section("按线程类型", "按线程类型")
    section("按子代理类型（含工作流代理）", "按子代理类型", limit=20)
    section("工作流代理 × 模型 × 代理类型（未指定 agentType 的 workflow-subagent 继承主线程模型）", "工作流代理×模型", limit=20)
    section("按工作流·阶段", "按工作流阶段", limit=25)
    section("按子代理描述（前 20，数字已归一为 #）", "按子代理描述", limit=20)

    # 前 15 环节
    env = sorted((G.get("环节") or {}).items(), key=lambda kv: (-kv[1].usd, -kv[1].w))
    out.append("")
    out.append("== 前 15 个最费的环节（按估算美元排序；环节=线×线程角色/工作流阶段）")
    for rank, (k, a) in enumerate(env[:15], 1):
        bt = ",".join("%s" % b for b, _ in a.batches.most_common(4))
        md = ",".join("%s" % m for m, _ in a.models.most_common(2))
        out.append("%2d. %s  ≈$%.0f（%s） 加权%s 新%s 读缓存%s  调用%d  线程%d  模型[%s]  批次[%s]" % (
            rank, " · ".join(k), a.usd, pct(a.usd, tot.usd), fm(a.w), fm(a.new), fm(a.cr), a.calls, len(a.n_threads), md, bt))

    em = R.get("envmix") or {}
    if em:
        out.append("")
        out.append("== 前 8 个环节的工具构成（次数 / 结果≈token / 滞留≈token；Read·图片.png 即看页图）")
        for k, a in env[:8]:
            mix = em.get(k) or {}
            items = sorted(mix.items(), key=lambda kv: -kv[1][2])[:7]
            out.append("  %s：%s" % (" · ".join(k), "；".join("%s %d次/%s/%s" % (n, v[0], fm(v[1]), fm(v[2])) for n, v in items)))
    # 单次最贵动作
    acts = []
    for thi, a in R["thread_agg"].items():
        th = P.threads[thi]
        if th["kind"] == "子代理":
            acts.append((a.w, "子代理运行", th["first"], "%s「%s」" % (th["agent_type"], short(th["desc"], 40)), a, th["session"]))
    for (sid, run), a in R["wfrun_agg"].items():
        info = P.wf_info.get(run) or {}
        acts.append((a.w, "工作流运行", info.get("start") or min((P.threads[t]["first"] or 0) for t in a.n_threads),
                     "%s %s（%d 代理，%s）%s" % (info.get("name") or next((P.threads[t]["wf_name"] for t in a.n_threads), "?"), run, len(a.n_threads), dur_h(info.get("duration_s")),
                                          short(info.get("args"), 60)), a, sid))
    for segi, a in R["seg_main_agg"].items():
        s = P.segs[segi]
        acts.append((a.w, "主线程回合", s["start"], "「%s」" % short(s["human"], 50), a, s["session"]))
    acts.sort(key=lambda x: -x[4].usd)
    out.append("")
    out.append("== 单次最贵动作 TOP10（子代理运行 / 工作流运行 / 主线程一个人类回合）")
    for rank, (w, typ, ts, desc, a, sid) in enumerate(acts[:10], 1):
        out.append("%2d. [%s] %s %s  ≈$%.0f 加权%s 新%s 读缓存%s 调用%d  模型%s  批次%s  会话%s" % (
            rank, typ, fmt_ts(ts, tz), desc, a.usd, fm(w), fm(a.new), fm(a.cr), a.calls,
            ",".join(a.models) if a.models else "-", ",".join(list(a.batches)[:2]), sid[:8]))
    # 单次 API 调用
    out.append("")
    out.append("== 单次 API 调用最贵 TOP10（多为长上下文缓存失效后的整段重写）")
    for rank, (w, ts, thi, i, cc, cr, o, model) in enumerate(R["top_calls"][:10], 1):
        th = P.threads[thi]
        out.append("%2d. %s %s %s  写缓存%s 读缓存%s 输出%s 加权%s  会话%s" % (
            rank, fmt_ts(ts, tz), P.thread_label(th), model, fm(cc), fm(cr), fm(o), fm(w), th["session"][:8]))
    for ln, a in sorted((R.get("polling") or {}).items(), key=lambda kv: -kv[1].usd):
        out.append("轮询（主线程 sleep/TaskOutput 之后的调用）[%s]：%d 次，读缓存 %s，≈$%.0f（%s），均上下文 %s" % (
            ln, a.calls, fm(a.cr), a.usd, pct(a.usd, tot.usd), fm((a.inp + a.cc + a.cr) / a.calls if a.calls else 0)))
    rb = R["rebuilds"]
    out.append("缓存重建（单次写缓存≥50K 且读缓存<写缓存）：%d 次，写缓存合计 %s，加权 %s（%s），≈$%.0f" % (
        rb.calls, fm(rb.cc), fm(rb.w), pct(rb.w, tw), rb.usd))

    # 工具
    out.append("")
    out.append("== 工具：次数 / 结果体积（估 token）/ 滞留成本（估被反复读入的 token）/ 计时")
    tl = sorted(R["tools"].items(), key=lambda kv: -kv[1]["carried_tokens"])
    for name, t in tl[:20]:
        out.append("%-34s 次%6d  错%4d  图%6d  结果≈%8s  滞留≈%9s  计时合计%8s" % (
            short(name, 34), t["calls"], t["errors"], t["images"], fm(t["est_tokens"]), fm(t["carried_tokens"]), dur_h(t["dur_s"])))
    out.append("")
    out.append("== Read 按类型（图片/文本×扩展名）")
    for cat, rc in sorted(R.get("readcat", {}).items(), key=lambda kv: -kv[1]["carried_tokens"])[:12]:
        out.append("%-16s 次%6d  图%6d  结果≈%8s  滞留≈%9s" % (short(cat, 16), rc["count"], rc["images"], fm(rc["est_tokens"]),
                                                          fm(rc["carried_tokens"])))
    tm = R.get("timing") or {}
    if tm:
        out.append("")
        out.append("== 时间（按线）")
        for ln in sorted(tm, key=lambda k: -tm[k].get("主线程回合墙钟", 0)):
            d = tm[ln]
            out.append("%-6s 人类回合%3d  主线程回合墙钟%7s（其中模型生成≈%7s，主线程Bash前台%7s，sleep等待%7s/%d次）"
                       "  工作流%3d次/%4d代理 墙钟合计%7s  子代理%4d个 墙钟合计%7s  子代理侧Bash前台%7s" % (
                           ln, d.get("人类回合数", 0), dur_h(d.get("主线程回合墙钟")), dur_h(d.get("主线程模型生成")),
                           dur_h(d.get("Bash前台·主线程")), dur_h(d.get("其中 sleep 等待·主线程")), d.get("sleep 次数·主线程", 0),
                           d.get("工作流运行数", 0), d.get("工作流代理数", 0), dur_h(d.get("工作流运行墙钟")),
                           d.get("子代理数", 0), dur_h(d.get("子代理运行墙钟")), dur_h(d.get("Bash前台·子代理/工作流"))))
    out.append("")
    out.append("== Bash 按类型：耗时（前台）")
    bl = sorted(R["bash"].items(), key=lambda kv: -sum(kv[1]["durs"]))
    for cat, b in bl:
        ds = b["durs"]
        out.append("%-8s 次%6d  后台%4d  总耗时%8s  中位%6s  最长%7s  结果≈%7s  滞留≈%8s" % (
            cat, b["count"], b["bg"], dur_h(sum(ds)), dur_h(statistics.median(ds)) if ds else "-",
            dur_h(max(ds)) if ds else "-", fm(b["est_tokens"]), fm(b["carried_tokens"])))
    out.append("")
    out.append("== Bash 最耗时 TOP10")
    for rank, (dsec, ts, thi, cat, summ, batch) in enumerate(R["top_bash"][:10], 1):
        out.append("%2d. %s %-6s %7s  %s  [%s·%s]" % (rank, fmt_ts(ts, tz), cat, dur_h(dsec), short(summ, 90),
                                                    P.thread_label(P.threads[thi]), batch))
    out.append("")
    out.append("== 工具结果滞留成本 TOP10（结果越大、之后调用越多，越贵）")
    for rank, (car, ts, thi, name, summ, est, later, imgs) in enumerate(R["top_carried"][:10], 1):
        out.append("%2d. %s %-5s 结果≈%s×其后%d次=%s  图%d  %s  [%s]" % (
            rank, fmt_ts(ts, tz), name, fm(est), later, fm(car), imgs, short(summ, 70), P.thread_label(P.threads[thi])))

    if sess_rows:
        out.append("")
        out.append("== 会话判定")
        for r in sess_rows:
            out.append("%s  %-22s %s→%s  主文件%5.1fMB 子代理文件%4d  线=%s %s" % (
                r["session"][:8], short(r["title"] or "-", 22), fmt_ts(r["first"], tz), fmt_ts(r["last"], tz),
                r["size_mb"], r["subagent_files"], r["line"],
                "（主文件全部为其他会话的复制）" if r["copied_from_other_file"] else ""))
            out.append("    依据: 文件首条=%s | 本会话新回合首条=%s | 关键词分=%s | cwd=%s | 回合线=%s（判据%s）| 加权占比=%s | cost-state=%s" % (
                short(r.get("file_first_human"), 50), short(r["first_human"], 50), r["keyword_score"],
                [short(c[0][-40:], 40) for c in r["cwd_top"][:2]], r["turn_lines"], r.get("turn_line_basis"),
                r["line_share"], r["cost_state_usd"]))
    if codex_results:
        out.append("")
        out.append("== Codex 抽样")
        for c in codex_results:
            t = c["total"]
            out.append("%s %5.1fMB %s 线≈%s 模型=%s  调用%d 新%s 读缓存%s 输出%s  工具%s  exec类%s" % (
                os.path.basename(c["file"])[8:27], c["size_mb"], (c["meta"] or {}).get("thread_source"), c["line_guess"],
                c["model_last"], t["calls"], fm(t["new_tokens"]), fm(t["cache_read"]), fm(t["output"]),
                dict(list(c["tools"].items())[:4]), dict(list(c["exec_categories"].items())[:5])))
    return "\n".join(out)


def to_json(P, R, sess_rows, codex_results, args):
    tz = P.tz
    G = R["G"]

    def gdict(key):
        return {(" / ".join(map(str, k)) if isinstance(k, tuple) else str(k)): a.to_dict()
                for k, a in sorted((G.get(key) or {}).items(), key=lambda kv: (-kv[1].usd, -kv[1].w))}

    acts = []
    for thi, a in R["thread_agg"].items():
        th = P.threads[thi]
        if th["kind"] == "主线程":
            continue
        acts.append({"type": th["kind"], "ts": fmt_ts(th["first"], tz), "session": th["session"],
                     "agent_type": th["agent_type"], "desc": th["desc"], "phase": th["phase"], "workflow": th["wf_name"],
                     "wf_run": th["wf_run"], "duration_s": round((th["last"] or 0) - (th["first"] or 0)),
                     "prompt": th["prompt"], **a.to_dict()})
    acts.sort(key=lambda x: -x["usd_est"])
    wf = []
    for (sid, run), a in R["wfrun_agg"].items():
        info = P.wf_info.get(run) or {}
        name = info.get("name") or next((P.threads[t]["wf_name"] for t in a.n_threads), None)
        wf.append({"session": sid, "run": run, "name": name, "start": fmt_ts(info.get("start"), tz),
                   "duration_s": info.get("duration_s"), "reported_total_tokens": info.get("total_tokens_reported"),
                   "agent_count": info.get("agent_count"), "args": info.get("args"), **a.to_dict()})
    wf.sort(key=lambda x: -x["usd_est"])
    segs = []
    for segi, a in R["seg_main_agg"].items():
        s = P.segs[segi]
        segs.append({"session": s["session"], "start": fmt_ts(s["start"], tz), "end": fmt_ts(s["end"], tz),
                     "line": s["line"], "line_basis": s.get("line_basis"), "batch": s["batch"], "human": s["human"],
                     "model_time_s": round(s["model_time"]),
                     "wall_s": round((s["end"] or 0) - (s["start"] or 0)), **a.to_dict()})
    segs.sort(key=lambda x: x["start"])
    bash = {}
    for cat, b in R["bash"].items():
        ds = b["durs"]
        bash[cat] = {"count": b["count"], "background": b["bg"], "total_s": round(sum(ds), 1),
                     "median_s": round(statistics.median(ds), 1) if ds else None, "max_s": round(max(ds), 1) if ds else None,
                     "est_result_tokens": round(b["est_tokens"]), "carried_tokens": round(b["carried_tokens"])}
    return {
        "meta": {"generated": datetime.now(tz).isoformat(), "inputs": args.inputs, "since": args.since, "until": args.until,
                 "tz": args.tz, "line_filter": args.line, "weights": P.W, "prices_per_weighted_M": P.prices, "unique_api_calls": len(P.calls),
                 "duplicate_records_skipped": P.dup_records, "threads": len(P.threads), "human_turns": len(P.segs),
                 "tool_results": len(P.results), "output_stats": getattr(P, "out_stats", None),
                 "estimates": {"tok_per_ascii": TOK_PER_ASCII, "tok_per_nonascii": TOK_PER_NONASCII,
                               "img_px_per_token": IMG_PX_PER_TOKEN}},
        "totals": (G.get("总计") or {}).get("全部", Agg()).to_dict(),
        "by_line": gdict("按线"), "by_line_kind": gdict("按线×线程类型"), "by_line_batch": gdict("按线×批次"),
        "by_line_batch_kind": gdict("按线×批次×线程类型"), "by_model": gdict("按模型"), "by_line_model": gdict("按线×模型"),
        "by_date": gdict("按日期"), "by_thread_kind": gdict("按线程类型"), "by_agent_type": gdict("按子代理类型"),
        "by_workflow_phase": gdict("按工作流阶段"), "by_agent_desc": gdict("按子代理描述"), "by_session": gdict("按会话"),
        "ranking_env": [{"key": " · ".join(k), **a.to_dict()} for k, a in
                        sorted((G.get("环节") or {}).items(), key=lambda kv: (-kv[1].usd, -kv[1].w))[:40]],
        "top_agent_runs": acts[:60], "workflow_runs": wf, "main_turns": segs,
        "top_api_calls": [{"ts": fmt_ts(ts, tz), "thread": P.thread_label(P.threads[thi]), "session": P.threads[thi]["session"],
                           "model": m, "input": i, "cache_creation": cc, "cache_read": cr, "output": o, "weighted": round(w)}
                          for (w, ts, thi, i, cc, cr, o, m) in R["top_calls"]],
        "cache_rebuilds": R["rebuilds"].to_dict(),
        "main_thread_polling": {k: v.to_dict() for k, v in R["polling"].items()},
        "tools": {k: {kk: (round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in R["tools"].items()},
        "bash": bash,
        "read_by_kind": {k: {kk: (round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in R["readcat"].items()},
        "timing_by_line_s": {ln: {k: round(v, 1) for k, v in d.items()} for ln, d in R["timing"].items()},
        "by_workflow_agent_model": gdict("工作流代理×模型"),
        "env_tool_mix": {" · ".join(k): {n: {"count": v[0], "est_tokens": round(v[1]), "carried_tokens": round(v[2])}
                                         for n, v in sorted(mix.items(), key=lambda kv: -kv[1][2])[:25]}
                         for k, mix in R["envmix"].items()},
        "bash_by_line": {ln: {c: {"count": v["count"], "dur_s": round(v["dur_s"], 1)} for c, v in d.items()} for ln, d in R["bash_by_line"].items()},
        "top_bash": [{"ts": fmt_ts(ts, tz), "cat": cat, "dur_s": round(dsec, 1), "summary": summ, "batch": batch,
                      "thread": P.thread_label(P.threads[thi])} for (dsec, ts, thi, cat, summ, batch) in R["top_bash"]],
        "top_carried_results": [{"ts": fmt_ts(ts, tz), "tool": name, "summary": summ, "est_tokens": round(est), "later_calls": later,
                                 "carried_tokens": round(car), "images": imgs, "thread": P.thread_label(P.threads[thi])}
                                for (car, ts, thi, name, summ, est, later, imgs) in R["top_carried"]],
        "sessions": [dict(r, first=fmt_ts(r["first"], tz), last=fmt_ts(r["last"], tz)) for r in sess_rows],
        "cost_state": P.cost_states,
        "workflow_meta": P.wf_info,
        "codex": codex_results,
    }


# ----------------------------------------------------------------------------- 入口
def collect_inputs(paths):
    mains = []
    for p in paths:
        p = os.path.expanduser(p)
        if os.path.isdir(p):
            mains += [f for f in glob.glob(os.path.join(p, "*.jsonl"))]
        elif p.endswith(".jsonl") and os.path.exists(p):
            mains.append(p)
        else:
            print("跳过：%s" % p, file=sys.stderr)

    def first_ts(f):
        with open(f, "rb") as fh:
            for i, line in enumerate(fh):
                if i > 200:
                    break
                try:
                    t = parse_ts(json.loads(line).get("timestamp"))
                except Exception:
                    t = None
                if t:
                    return t
        return float("inf")
    # 按首条时间排序：原会话先读，续接/复制会话后读，保证去重时归到原会话
    # 同一时刻起点的分叉副本：先读大的（通常是超集），结果与读取顺序无关地稳定
    return sorted(set(mains), key=lambda f: (first_ts(f), -os.path.getsize(f), f))


def main():
    ap = argparse.ArgumentParser(description="Claude Code / Codex 会话用量画像（只读）")
    ap.add_argument("inputs", nargs="*", help="会话 .jsonl 或项目目录（含多个会话）")
    ap.add_argument("--out", default="usage_profile_out", help="输出目录（写 usage_profile.json / .txt）")
    ap.add_argument("--tag", default="", help="输出文件名后缀，如 _bx3")
    ap.add_argument("--since", help="起始时间（含），如 2026-09-15 或 2026-09-15T08:00，按 --tz 解释")
    ap.add_argument("--until", help="截止时间（不含）")
    ap.add_argument("--tz", default="local", help="日期分组时区：local / +08:00 / Asia/Shanghai")
    ap.add_argument("--line", help="只统计某条线：必修三 / 题库线 / 必修二 / 其他")
    ap.add_argument("--session", action="append", help="只统计会话 id 前缀（可多次）")
    ap.add_argument("--weights", help='JSON，如 {"cache_read":0.1,"output":5}')
    ap.add_argument("--prices", help='JSON，每百万加权当量美元，按模型名前缀匹配，如 {"claude-fable-5":9.2}')
    ap.add_argument("--line-map", default="", help="人工覆盖：会话id前缀=线，逗号分隔，如 d6caf4c4=其他,bf450d67=其他")
    ap.add_argument("--classify-only", action="store_true", help="只输出会话判定")
    ap.add_argument("--codex", nargs="*", default=[], help="Codex rollout 文件")
    ap.add_argument("--codex-scan", help="Codex sessions 根目录（按文件名日期 + 首行 cwd 过滤后抽样）")
    ap.add_argument("--codex-dates", default="", help="逗号分隔日期 YYYY-MM-DD")
    ap.add_argument("--codex-cwd", default=r"gpt6|gpt和claude", help="首行 cwd 正则")
    ap.add_argument("--codex-sample", type=int, default=5)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    tz = make_tz(args.tz)
    W = dict(DEFAULT_WEIGHTS)
    if args.weights:
        W.update(json.loads(args.weights))
    prices = dict(DEFAULT_PRICES)
    if args.prices:
        prices.update(json.loads(args.prices))
    P = Profiler(W, tz, prices)
    mains = collect_inputs(args.inputs)
    for f in mains:
        if not args.quiet:
            print("读取 %s …" % os.path.basename(f), file=sys.stderr)
        P.add_session(f)
    P.finalize()
    for item in [x for x in args.line_map.split(",") if "=" in x]:
        pre, ln = item.split("=", 1)
        for sg in P.segs:
            if sg["session"].startswith(pre.strip()):
                sg["line"], sg["line_basis"] = ln.strip(), "人工覆盖"
                if ln.strip() not in ("必修三", "必修二"):
                    sg["batch"] = day_of(sg["start"], tz) if sg["start"] else "?"
    since = parse_bound(args.since, tz)
    until = parse_bound(args.until, tz)
    R = P.aggregate(since, until, args.line, args.session)
    sess_rows = P.session_table() if mains else []

    codex_results = []
    cfiles = list(args.codex)
    n_match = None
    if args.codex_scan:
        dates = [d for d in args.codex_dates.split(",") if d]
        picked, n_match = codex_scan(os.path.expanduser(args.codex_scan), dates, args.codex_cwd, args.codex_sample)
        cfiles += picked
    for f in cfiles:
        if not args.quiet:
            print("读取 Codex %s …" % os.path.basename(f), file=sys.stderr)
        codex_results.append(parse_codex(f, W, tz))
    if n_match is not None:
        for c in codex_results:
            c["scan_matched_files"] = n_match

    os.makedirs(args.out, exist_ok=True)
    js = to_json(P, R, sess_rows, codex_results, args)
    jp = os.path.join(args.out, "usage_profile%s.json" % args.tag)
    tp = os.path.join(args.out, "usage_profile%s.txt" % args.tag)
    with open(jp, "w", encoding="utf-8") as fh:
        json.dump(js, fh, ensure_ascii=False, indent=1, default=str)
    txt = build_report(P, R, args, sess_rows, codex_results)
    if args.classify_only:
        k = txt.find("== 会话判定")
        txt = "\n".join(txt.splitlines()[:4]) + "\n\n" + (txt[k:] if k >= 0 else "（无会话）")
    with open(tp, "w", encoding="utf-8") as fh:
        fh.write(txt + "\n")
    if not args.quiet:
        print(txt)
        print("\n已写：%s\n      %s" % (jp, tp), file=sys.stderr)


if __name__ == "__main__":
    main()
