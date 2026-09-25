#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段1b：考试身份登记 + 文件角色判定。

产出 indexes/exams.csv、indexes/exam_files.csv

原则：
  - 来源文件 / 考试 / 具体题目 三者分层登记（约束3）
  - 汇编文件单独标记，其内部题目的年份/地区/题号不得继承汇编文件自身信息
  - 年份/地区/阶段先按路径推断并记录 evidence，内容核对阶段再确认
"""
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

REGIONS = ["东城", "西城", "海淀", "朝阳", "丰台", "石景山", "通州", "顺义", "昌平",
           "房山", "门头沟", "延庆", "大兴", "密云", "平谷", "怀柔", "燕山", "经开区"]
REGION_CODE = {"东城": "DC", "西城": "XC", "海淀": "HD", "朝阳": "CY", "丰台": "FT",
               "石景山": "SJS", "通州": "TZ", "顺义": "SY", "昌平": "CP",
               "房山": "FS", "门头沟": "MTG", "延庆": "YQ", "大兴": "DX",
               "密云": "MY", "平谷": "PG", "怀柔": "HR", "燕山": "YS", "经开区": "JKQ",
               "北京": "BJ"}

STAGE_CODE = [("一模", "YIMO"), ("二模", "ERMO"), ("期中", "QIZHONG"), ("期末", "QIMO"),
              ("适应性", "SHIYING"), ("联考", "LIANKAO"), ("高考", "GAOKAO"),
              ("开学考", "KAIXUE"), ("零模", "LINGMO")]

ASSEMBLY_HINTS = ["分类汇编", "试题分类", "按模块", "汇编"]
ASSEMBLY_RE = re.compile(r"(各区.*考题|考题-wlf|各区.*分类)")
# 高考分题切片：形如 2023.16.pdf / 2023.18（1）（2）.pdf
GAOKAO_SLICE_RE = re.compile(r"^\s*20\d{2}\s*[.．]\s*\d")
# 角色判定时须剔除的路径段：顶层根名与"历年高考题及细则"本身，
# 否则目录名里的"细则"会把参考答案误判为评分材料
ROLE_PATH_DROP = {"历年高考题及细则"}


def norm(s):
    return s.replace("（", "(").replace("）", ")")


def role_path(rel):
    parts = rel.split(os.sep)
    parts = parts[1:] if len(parts) > 1 else []
    parts = [p for p in parts if p not in ROLE_PATH_DROP]
    return "/".join(parts)


def infer_role(rel, fn):
    """文件角色。返回 (role, evidence)

    注意：只用去掉根名后的路径，避免目录名污染。
    """
    p = role_path(rel)
    f = norm(fn)
    if "分题细则" in p:
        return "评分细则_分题切片", "路径含 分题细则"
    if "阅卷总结" in p or "阅卷总结" in f:
        return "阅卷总结", "路径/文件名含 阅卷总结"
    if any(h in p or h in f for h in ASSEMBLY_HINTS) or ASSEMBLY_RE.search(rel):
        return "汇编", "路径/文件名含 汇编/分类/各区考题"
    if "教师版" in f:
        return "教师版", "文件名含 教师版"
    if "讲评" in p or "讲评" in f:
        return "讲评", "路径/文件名含 讲评"
    if "勘误" in f or "补充说明" in f:
        return "勘误", "文件名含 勘误/补充说明"
    if "评分标准" in f or "评分参考" in f or "评分细则" in f or "阅卷标准" in f or "细则汇总" in f:
        return "评分材料", "文件名含 评分标准/评分参考/评分细则/阅卷标准/细则汇总"
    if "细则" in f or "评标" in f or "细则" in p or "评标" in p:
        return "评分材料", "路径/文件名含 细则/评标"
    if "答案" in f:
        return "参考答案", "文件名含 答案"
    if "试卷" in p or "试题" in f or "试卷" in f or "原卷" in f:
        return "原卷", "路径/文件名含 试卷/试题/原卷"
    if "答案" in p:
        return "参考答案", "路径含 答案"
    # 高考语境：无角色词且形如 2023.16.pdf -> 分题切片（具体角色待内容确认）
    if GAOKAO_SLICE_RE.match(f):
        return "分题切片_待定", "文件名形如 年份.题号，角色须内容确认"
    if "高考" in f:
        return "原卷", "高考语境且无其他角色词，按原卷登记（待内容确认）"
    return "未知", "无角色线索"


def infer_exam(rel, fn):
    """从相对路径推断考试身份。返回 dict。"""
    parts = rel.split(os.sep)
    top = parts[0] if parts else ""
    d = {"year": "unknown", "school_year": "unknown", "region": "unknown",
         "institution": "unknown", "grade": "高三", "stage": "unknown",
         "paper_type": "unknown", "version": "", "evidence": []}

    # 年份
    if "历年高考题及细则" in top or "高考" in rel:
        m = re.search(r"(20\d{2})", rel)
        if not m:
            # 两位数年份，如 23北京高考.pdf
            m2 = re.search(r"(?<!\d)(\d{2})\s*北京高考", rel)
            if m2:
                m = m2
        if m:
            y = m.group(1)
            if len(y) == 2:
                y = "20" + y
            d["year"] = y
            d["evidence"].append("路径含高考年份 %s" % y)
        d["stage"] = "高考"
        d["paper_type"] = "高考真题"
        d["region"] = "北京"
        d["evidence"].append("高考真题统一归北京")
    else:
        m = re.match(r"(20\d{2})模拟题", top)
        if m:
            d["year"] = m.group(1)
            d["evidence"].append("顶层目录 %s" % top)
            d["school_year"] = "%s-%s学年" % (int(m.group(1)) - 1, m.group(1))

    # 阶段：取"最靠近文件的"含阶段关键词的路径段，避免父目录名污染
    # （例如 "2026各区期末和期中" 含"期中"，会使全部子卷被误判）
    STAGE_NAME = {"一模": "一模", "二模": "二模", "期中": "期中", "期末": "期末",
                  "适应性": "适应性测试", "联考": "联考", "高考": "高考",
                  "开学考": "开学考", "零模": "零模"}
    parts_desc = list(reversed(parts))
    for seg in parts_desc:
        seg_s = seg[:-5] if seg.lower().endswith(".docx") or seg.lower().endswith(".pptx") else seg
        seg_s = os.path.splitext(seg)[0]
        hit = None
        for key in STAGE_NAME:
            if key in seg_s:
                hit = key
                break
        if hit:
            d["stage"] = STAGE_NAME[hit]
            d["evidence"].append("最深含阶段段 `%s` -> %s" % (seg, hit))
            break

    # 地区
    for r in REGIONS:
        if r in rel:
            d["region"] = r
            d["evidence"].append("路径含地区 %s" % r)
            break
    if d["region"] == "unknown":
        m = re.search(r"(东城|西城|海淀|朝阳|丰台|石景山|通州|顺义|昌平|房山|门头沟|延庆|大兴|密云|平谷|怀柔)", rel)
        if m:
            d["region"] = m.group(1)
            d["evidence"].append("正则命中地区 %s" % m.group(1))

    # 联考/机构
    if "联考" in rel or "联考" in fn:
        d["institution"] = "联考"

    # 卷别/版本
    if "学生版" in fn:
        d["version"] = "学生版"
    if "教师版" in fn:
        d["version"] = (d["version"] + "+教师版").strip("+")
    if "扫描" in fn:
        d["version"] = (d["version"] + "+扫描版").strip("+")

    # 年级
    if "高二" in rel:
        d["grade"] = "高二"
    elif "高一" in rel:
        d["grade"] = "高一"

    if "期末" in d["stage"]:
        d["paper_type"] = "期末考试"
    elif "期中" in d["stage"]:
        d["paper_type"] = "期中考试"
    elif d["stage"] in ("一模", "二模"):
        d["paper_type"] = "模拟考试"
    elif d["stage"] == "高考":
        d["paper_type"] = "高考真题"
    return d


def make_exam_id(d):
    y = d["year"] if d["year"] != "unknown" else "XXXX"
    rc = REGION_CODE.get(d["region"], d["region"] if d["region"] != "unknown" else "UNK")
    sc = d["stage"] if d["stage"] != "unknown" else "UNK"
    sc = {"一模": "YIMO", "二模": "ERMO", "期中": "QIZHONG", "期末": "QIMO",
          "高考": "GAOKAO", "适应性测试": "SHIYING", "联考": "LIANKAO"}.get(sc, sc)
    return "BJ-%s-%s-%s" % (y, rc, sc)


def main():
    P.ensure_dirs(P.INDEX_DIR)
    man = os.path.join(P.INDEX_DIR, "source_manifest.csv")
    with open(man, "r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    files = []
    for r in rows:
        rel = r["rel_path"]
        fn = os.path.basename(rel)
        role, role_ev = infer_role(rel, fn)
        d = infer_exam(rel, fn)
        is_assembly = (role == "汇编")
        eid = "ASM-%s" % os.path.splitext(fn)[0][:24] if is_assembly else make_exam_id(d)
        files.append({
            "source_id": r["source_id"], "rel_path": rel, "format": r["format"],
            "size": r["size"], "pages": r["pages"], "in_scope": r["in_scope"],
            "role": role, "role_evidence": role_ev,
            "exam_id": eid,
            "exam_id_evidence": "汇编文件独立登记，题目出处须逐题核实" if is_assembly else "; ".join(d["evidence"]),
            "year": d["year"], "school_year": d["school_year"], "region": d["region"],
            "institution": d["institution"], "grade": d["grade"], "stage": d["stage"],
            "paper_type": d["paper_type"], "version": d["version"],
            "is_assembly": "Y" if is_assembly else "N",
        })

    cols = ["source_id", "exam_id", "rel_path", "format", "size", "pages", "role",
            "role_evidence", "is_assembly", "year", "school_year", "region", "institution",
            "grade", "stage", "paper_type", "version", "exam_id_evidence", "in_scope"]
    with open(os.path.join(P.INDEX_DIR, "exam_files.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for f in files:
            w.writerow({k: f.get(k, "") for k in cols})

    # exams.csv 汇总
    ex = {}
    for f in files:
        if f["in_scope"] != "Y":
            continue
        e = ex.setdefault(f["exam_id"], {
            "exam_id": f["exam_id"], "year": f["year"], "school_year": f["school_year"],
            "region": f["region"], "institution": f["institution"], "grade": f["grade"],
            "stage": f["stage"], "paper_type": f["paper_type"], "versions": set(),
            "files": 0, "roles": {}, "is_assembly": f["is_assembly"],
        })
        e["files"] += 1
        e["roles"][f["role"]] = e["roles"].get(f["role"], 0) + 1
        if f["version"]:
            e["versions"].add(f["version"])
    with open(os.path.join(P.INDEX_DIR, "exams.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["exam_id", "year", "school_year", "region", "institution", "grade",
                    "stage", "paper_type", "versions", "file_count", "has_paper", "has_rubric",
                    "has_answer", "has_lecture", "is_assembly", "question_count", "subq_count",
                    "extract_status", "notes"])
        for k in sorted(ex):
            e = ex[k]
            w.writerow([e["exam_id"], e["year"], e["school_year"], e["region"], e["institution"],
                        e["grade"], e["stage"], e["paper_type"], "+".join(sorted(e["versions"])),
                        e["files"],
                        "Y" if e["roles"].get("原卷") else "N",
                        "Y" if e["roles"].get("评分材料") or e["roles"].get("评分细则_分题切片") else "N",
                        "Y" if e["roles"].get("参考答案") else "N",
                        "Y" if e["roles"].get("讲评") else "N",
                        e["is_assembly"], "", "", "pending", ""])
    print("exam_files.csv:", len(files))
    print("exams.csv:", len(ex))
    print("exam_id 列表：")
    for k in sorted(ex):
        e = ex[k]
        print("  %-24s files=%-3d paper=%s rubric=%s answer=%s assembly=%s" % (
            k, e["files"], "Y" if e["roles"].get("原卷") else "-",
            "Y" if (e["roles"].get("评分材料") or e["roles"].get("评分细则_分题切片")) else "-",
            "Y" if e["roles"].get("参考答案") else "-", e["is_assembly"]))


if __name__ == "__main__":
    main()
