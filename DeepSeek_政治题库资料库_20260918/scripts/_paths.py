#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共享配置与工具定位。

本模块是 DeepSeek 政治题库资料库的唯一路径真相来源。
所有脚本一律通过本模块取路径，禁止依赖 PATH 或硬编码别处。

运行环境：/usr/bin/python3 (3.9.6)
"""
import os
import subprocess
import sys

# ---------------------------------------------------------------- 输出根
OUT_ROOT = "/Users/wanglifei/Desktop/gpt和claude共同的小窝/DeepSeek_政治题库资料库_20260918"

INDEX_DIR = os.path.join(OUT_ROOT, "indexes")
MD_DIR = os.path.join(OUT_ROOT, "processed_markdown")
Q_DIR = os.path.join(OUT_ROOT, "questions")
ASSET_DIR = os.path.join(OUT_ROOT, "assets")
EVID_DIR = os.path.join(OUT_ROOT, "evidence")
VAL_DIR = os.path.join(OUT_ROOT, "validation")
SCRIPT_DIR = os.path.join(OUT_ROOT, "scripts")
TMP_DIR = os.path.join(OUT_ROOT, "tmp")

# ---------------------------------------------------------------- 输入根
HOME = os.path.expanduser("~")
WORKSPACE = "/Users/wanglifei/Desktop/gpt和claude共同的小窝"
DESKTOP = "/Users/wanglifei/Desktop"

# 主输入根（工作区已去重副本）
PRIMARY_ROOT = os.path.join(WORKSPACE, "00_共同资料", "原材料")

# 已授权原料根（仅用于对账，逐项按内容哈希判定重复）
# role: primary = 主输入；alias_check = 只对账，不重复处理
AUTHORIZED_ROOTS = [
    {"root_id": "W-COPY", "path": PRIMARY_ROOT,
     "role": "primary", "label": "工作区副本 00_共同资料/原材料"},
    {"root_id": "D-2023", "path": os.path.join(DESKTOP, "2023模拟题"),
     "role": "alias_check", "label": "桌面 2023模拟题"},
    {"root_id": "D-2024", "path": os.path.join(DESKTOP, "2024模拟题"),
     "role": "alias_check", "label": "桌面 2024模拟题"},
    {"root_id": "D-2025", "path": os.path.join(DESKTOP, "2025模拟题"),
     "role": "alias_check", "label": "桌面 2025模拟题"},
    {"root_id": "D-2026", "path": os.path.join(DESKTOP, "2026模拟题"),
     "role": "alias_check", "label": "桌面 2026模拟题（工程目录，须按内容哈希核对独有原件）"},
    {"root_id": "D-GAOKAO", "path": os.path.join(DESKTOP, "历年高考题及细则"),
     "role": "alias_check", "label": "桌面 历年高考题及细则"},
    {"root_id": "W-2026STU", "path": os.path.join(WORKSPACE, "2026模拟题_学生题库_按考试类型整理_20260914"),
     "role": "alias_check", "label": "工作区 2026模拟题_学生题库（2026 的再组织副本）"},
]

# 相关压缩包（须对账，登记包路径与成员路径）
ZIP_CANDIDATES = [
    os.path.join(WORKSPACE, "2026模拟题 完整版.zip"),
    os.path.join(DESKTOP, "2025模拟题.zip"),
    os.path.join(DESKTOP, "历年高考题及细则.zip"),
]

# 明确排除的目录（工程产物/缓存；不得进入递归扫描）
EXCLUDE_DIR_NAMES = {
    "__pycache__", ".git", ".DS_Store", "node_modules", ".workbuddy-ai",
}

# 大型工程目录中允许作为题源候选的子目录（约束1：不得未经核对就认定无独有原件）
D_2026_SOURCE_SUBDIRS = [
    "2026各区一模", "2026各区二模", "2026各区期末和期中", "只有答案没有细则的",
]

# 范围外目录（仅登记，不处理）
OUT_OF_SCOPE_SUBDIRS = ["宝典制作原料"]

# ---------------------------------------------------------------- 工具绝对路径
POPPLER_BIN = os.path.join(
    HOME, ".cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/poppler/bin")
PDFTOTEXT = os.path.join(POPPLER_BIN, "pdftotext")
PDFINFO = os.path.join(POPPLER_BIN, "pdfinfo")
PDFTOPPM = os.path.join(POPPLER_BIN, "pdftoppm")
PDFIMAGES = os.path.join(POPPLER_BIN, "pdfimages")
PDFFONTS = os.path.join(POPPLER_BIN, "pdffonts")
PDFTOCAIRO = os.path.join(POPPLER_BIN, "pdftocairo")

SOFFICE = os.path.join(
    HOME, ".cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/soffice")
SOFFICE_BARE = os.path.join(
    HOME, ".cache/codex-runtimes/codex-primary-runtime/dependencies/native/"
         "libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/MacOS/soffice")

OCR_VISION = os.path.join(HOME, ".local/bin/ocr-vision")

PY_SYS = "/usr/bin/python3"

# LibreOffice 中文字体配置（已存在的可复用配置，按优先级探测）
FONTCONFIG_CANDIDATES = [
    os.path.join(WORKSPACE, "必修三_第48批接续_WorkBuddy_20260918/构建/lo_profile/fontconfig/fonts.conf"),
    os.path.join(WORKSPACE, "必修三_最新Skill修订_20260913/协作/候选/Claude/"
                            "R45候选_Claude_20260915/构建/lo_profile/fontconfig/fonts.conf"),
]


def fontconfig_file():
    for p in FONTCONFIG_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def env_with_fontconfig():
    env = dict(os.environ)
    fc = fontconfig_file()
    if fc:
        env["FONTCONFIG_FILE"] = fc
    return env


def run(cmd, timeout=300, env=None, cwd=None):
    """运行命令，返回 (returncode, stdout, stderr)。绝不抛异常。"""
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env, cwd=cwd)
        return (p.returncode,
                p.stdout.decode("utf-8", "replace"),
                p.stderr.decode("utf-8", "replace"))
    except subprocess.TimeoutExpired:
        return (-9, "", "TIMEOUT after %ss" % timeout)
    except Exception as e:  # noqa
        return (-1, "", "EXEC_ERROR: %r" % (e,))


def ensure_dirs(*paths):
    for p in paths:
        os.makedirs(p, exist_ok=True)


if __name__ == "__main__":
    print("OUT_ROOT =", OUT_ROOT)
    print("PRIMARY_ROOT =", PRIMARY_ROOT, os.path.isdir(PRIMARY_ROOT))
    for r in AUTHORIZED_ROOTS:
        print("  %-12s %-7s %s  %s" % (r["root_id"], r["role"], "OK " if os.path.isdir(r["path"]) else "MISSING", r["path"]))
    for z in ZIP_CANDIDATES:
        print("  ZIP %s %s" % ("OK " if os.path.isfile(z) else "MISSING", z))
    for name, p in [("pdftotext", PDFTOTEXT), ("pdfinfo", PDFINFO), ("pdftoppm", PDFTOPPM),
                    ("pdfimages", PDFIMAGES), ("pdffonts", PDFFONTS),
                    ("soffice", SOFFICE), ("ocr-vision", OCR_VISION), ("python3", PY_SYS)]:
        print("  TOOL %-11s %s %s" % (name, "OK " if os.path.exists(p) else "MISSING", p))
    print("  FONTCONFIG =", fontconfig_file())
    sys.exit(0)
