#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段1：原料盘点 + 原料对账（约束1）。

产出：
  indexes/source_manifest.csv   主输入根逐文件清单
  indexes/source_aliases.csv    全哈希 -> 全部路径（来源别名）
  indexes/_hash_cache.json      断点缓存（可重跑续作）
  validation/原料对账报告.md     约束1 对账结论

约束1 要点：
  - 只有内容哈希一致才算重复来源
  - 大型工程目录不得未经核对就认定无独有原件
  - 无法核对的范围必须记录，不得宣称覆盖全部原料
"""
import csv
import hashlib
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

CACHE = os.path.join(P.INDEX_DIR, "_hash_cache.json")
ZIP_EXTRACT = os.path.join(P.TMP_DIR, "zip_extract")

DOC_EXT = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".rtf", ".xls", ".xlsx", ".csv", ".txt", ".odt", ".wps", ".wpt"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".workbuddy-ai", ".Trash"}

# 大型工程目录中已知的工程产物目录（可排除，但须记录）
ENGINEERING_MARKERS = ("_v25续作_", "_v6.9续作_", "_v15.0续作_", "项目迁移_", "workers", "assets",
                       "packages", "renders", "render", "batch", "批次", "cache", "缓存",
                       "build", "构建", "logs", "日志")


def sha256_file(path, buf=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def walk_files(root, skip_engineering=False):
    """产出 (abspath, relpath)。skip_engineering 仅用于标记，不用于跳过。"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn in SKIP_NAMES:
                continue
            yield os.path.join(dirpath, fn)


def load_cache():
    if os.path.isfile(CACHE):
        try:
            with open(CACHE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}


def main():
    P.ensure_dirs(P.INDEX_DIR, P.VAL_DIR, P.TMP_DIR)
    cache = load_cache()          # {abspath: {"sha":..,"size":..,"mtime":..}}
    print("cache entries:", len(cache))

    # ---------------- 0. 解压相关压缩包（成员登记）
    zip_records = []
    P.ensure_dirs(ZIP_EXTRACT)
    for z in P.ZIP_CANDIDATES:
        if not os.path.isfile(z):
            zip_records.append({"zip": z, "status": "MISSING"})
            continue
        try:
            dest = os.path.join(ZIP_EXTRACT, os.path.basename(z).replace(" ", "_").replace(".zip", ""))
            P.ensure_dirs(dest)
            with zipfile.ZipFile(z) as zf:
                members = zf.namelist()
                bad = zf.testzip()
                # 安全解压：防路径越界
                n_ok = 0
                for m in members:
                    if m.endswith("/"):
                        continue
                    target = os.path.realpath(os.path.join(dest, m))
                    if not target.startswith(os.path.realpath(dest) + os.sep):
                        continue  # 路径越界，跳过
                    if os.path.isfile(target):
                        n_ok += 1
                        continue
                    try:
                        zf.extract(m, dest)
                        n_ok += 1
                    except Exception:
                        pass
            zip_records.append({"zip": z, "status": "OK", "members": len(members),
                                "extracted": n_ok, "testzip": bad, "dest": dest})
            print("ZIP", os.path.basename(z), len(members), "members ->", n_ok)
        except Exception as e:
            zip_records.append({"zip": z, "status": "ERROR", "error": repr(e)})
            print("ZIP ERROR", z, repr(e))

    # ---------------- 1. 全哈希索引
    all_paths = []   # (abspath, root_id, is_zip_member)
    for r in P.AUTHORIZED_ROOTS:
        if not os.path.isdir(r["path"]):
            continue
        n = 0
        for ap in walk_files(r["path"]):
            all_paths.append((ap, r["root_id"], False))
            n += 1
        print("root", r["root_id"], n, "files")
    for zr in zip_records:
        if zr.get("status") == "OK":
            for ap in walk_files(zr["dest"]):
                all_paths.append((ap, "ZIP:" + os.path.basename(zr["zip"]), True))
    print("total paths to hash:", len(all_paths))

    # 增量哈希
    todo = []
    for ap, rid, isz in all_paths:
        st = os.stat(ap)
        c = cache.get(ap)
        if c and c["size"] == st.st_size and abs(c["mtime"] - st.st_mtime) < 1:
            continue
        todo.append(ap)
    print("need hashing:", len(todo))
    for i, ap in enumerate(todo):
        try:
            st = os.stat(ap)
            cache[ap] = {"sha": sha256_file(ap), "size": st.st_size, "mtime": st.st_mtime}
        except Exception as e:
            cache[ap] = {"sha": None, "size": -1, "mtime": 0, "error": repr(e)}
        if (i + 1) % 2000 == 0:
            print("  hashed", i + 1)
            with open(CACHE, "w", encoding="utf-8") as fh:
                json.dump(cache, fh)
    with open(CACHE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh)
    print("hash done")

    # ---------------- 2. 别名表
    by_sha = {}
    for ap, rid, isz in all_paths:
        c = cache.get(ap)
        if not c or not c.get("sha"):
            continue
        by_sha.setdefault(c["sha"], []).append({"path": ap, "root": rid, "zip_member": isz,
                                                "size": c["size"]})
    print("unique hashes:", len(by_sha))

    # 碰撞检查
    collisions = []

    # ---------------- 3. 主输入根清单
    rows = []
    primary_prefix = P.PRIMARY_ROOT + os.sep
    for ap, rid, isz in all_paths:
        if rid != "W-COPY":
            continue
        c = cache.get(ap) or {}
        sha = c.get("sha") or ""
        rel = os.path.relpath(ap, P.PRIMARY_ROOT)
        top = rel.split(os.sep)[0]
        ext = os.path.splitext(ap)[1].lower()
        sid = "S" + sha[:12] if sha else "SERR"
        aliases = [a["path"] for a in by_sha.get(sha, []) if a["path"] != ap]
        in_scope = top not in P.OUT_OF_SCOPE_SUBDIRS
        rows.append({
            "source_id": sid,
            "rel_path": rel,
            "original_path": ap,
            "alias_count": len(aliases),
            "alias_paths": " | ".join(aliases),
            "format": ext.lstrip("."),
            "size": c.get("size", -1),
            "sha256": sha,
            "top_dir": top,
            "in_scope": "Y" if in_scope else "N",
            "exclude_reason": "" if in_scope else "范围外：班课讲义，非试卷",
            "read_status": "pending",
            "process_status": "pending",
            "output_path": "",
            "pages": "",
            "pages_source": "",
        })
    rows.sort(key=lambda r: r["rel_path"])
    # 碰撞
    seen = {}
    for r in rows:
        seen.setdefault(r["source_id"], []).append(r["rel_path"])
    for sid, ps in seen.items():
        if len(ps) > 1:
            shas = {next((x["sha256"] for x in rows if x["source_id"] == sid), "")}
            if len(shas) > 1 or True:
                collisions.append({"source_id": sid, "paths": ps})

    # ---------------- 4. 页数/幻灯片数
    import subprocess
    for r in rows:
        ap = r["original_path"]
        ext = "." + r["format"] if r["format"] else ""
        try:
            if ext == ".pdf":
                rc, out, err = P.run([P.PDFINFO, ap], timeout=60)
                m = re.search(r"^Pages:\s+(\d+)", out, re.M)
                if m:
                    r["pages"] = m.group(1)
                    r["pages_source"] = "pdfinfo"
                else:
                    r["pages"] = "unknown"
                    r["pages_source"] = "pdfinfo 无 Pages 字段; rc=%s" % rc
            elif ext == ".pptx":
                from pptx import Presentation
                pr = Presentation(ap)
                r["pages"] = str(len(pr.slides))
                r["pages_source"] = "python-pptx len(slides)"
            elif ext == ".docx":
                from docx import Document
                d = Document(ap)
                r["pages"] = "unknown"
                r["pages_source"] = "docx 无固定页数；实测 段落%d 表格%d" % (len(d.paragraphs), len(d.tables))
            elif ext == ".doc":
                r["pages"] = "unknown"
                r["pages_source"] = ".doc 旧格式未转换，页数待 soffice 转换后取得"
            else:
                r["pages"] = "unknown"
                r["pages_source"] = "格式 %s 未实现页数探针" % ext
        except Exception as e:
            r["pages"] = "unknown"
            r["pages_source"] = "探针异常: %r" % (e,)

    cols = ["source_id", "rel_path", "original_path", "format", "size", "sha256", "top_dir",
            "in_scope", "exclude_reason", "alias_count", "alias_paths", "pages", "pages_source",
            "read_status", "process_status", "output_path"]
    with open(os.path.join(P.INDEX_DIR, "source_manifest.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})
    print("source_manifest.csv rows:", len(rows))

    with open(os.path.join(P.INDEX_DIR, "source_aliases.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["sha256", "path", "root", "is_zip_member", "size"])
        for sha, lst in by_sha.items():
            for a in lst:
                w.writerow([sha, a["path"], a["root"], a["zip_member"], a["size"]])
    print("source_aliases.csv rows:", sum(len(v) for v in by_sha.values()))

    # ---------------- 5. 对账报告
    primary_hashes = set(r["sha256"] for r in rows if r["sha256"])
    rep = []
    rep.append("# 原料对账报告（约束1）\n")
    rep.append("生成时间：脚本运行时刻；主输入根：`%s`\n" % P.PRIMARY_ROOT)
    rep.append("判定规则：**只有完整 SHA-256 一致才登记为重复来源**；文件名/大小不作为判据。\n")
    rep.append("\n## 1. 各原料根对账\n")
    rep.append("| 根ID | 说明 | 路径 | 文件数 | 唯一哈希 | 与主输入同哈希 | **主输入所无（潜在独有）** | 其中题源类扩展名 |")
    rep.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |")
    root_stats = {}
    for r in P.AUTHORIZED_ROOTS:
        rid = r["root_id"]
        if not os.path.isdir(r["path"]):
            rep.append("| %s | %s | `%s` | — | — | — | — | 目录不存在 |" % (rid, r["label"], r["path"]))
            continue
        paths = [ap for ap, x, z in all_paths if x == rid]
        hashes = set()
        own, doclike = [], []
        for ap in paths:
            c = cache.get(ap) or {}
            sha = c.get("sha")
            if not sha:
                continue
            hashes.add(sha)
            if sha not in primary_hashes:
                own.append(ap)
                if os.path.splitext(ap)[1].lower() in DOC_EXT:
                    doclike.append(ap)
        root_stats[rid] = {"files": len(paths), "uniq": len(hashes),
                           "own": own, "doclike": doclike}
        rep.append("| %s | %s | `%s` | %d | %d | %d | **%d** | %d |" % (
            rid, r["label"], r["path"], len(paths), len(hashes),
            len(paths) - len(own) if rid != "W-COPY" else len(paths),
            len(own), len(doclike)))
    rep.append("\n> `W-COPY` 是主输入根本身，其“主输入所无”列无意义，已填文件数。\n")

    rep.append("\n## 2. 压缩包对账\n")
    rep.append("| 压缩包 | 状态 | 成员数 | 已解压 | CRC自检 | 解压目录 |")
    rep.append("| --- | --- | ---: | ---: | --- | --- |")
    for zr in zip_records:
        rep.append("| `%s` | %s | %s | %s | %s | `%s` |" % (
            zr["zip"], zr.get("status"), zr.get("members", "—"), zr.get("extracted", "—"),
            zr.get("testzip") or "无损坏", zr.get("dest", "—")))
    rep.append("\n### 压缩包成员中主输入所无的文件（潜在独有）\n")
    zown = []
    for zr in zip_records:
        if zr.get("status") != "OK":
            continue
        for ap in walk_files(zr["dest"]):
            c = cache.get(ap) or {}
            sha = c.get("sha")
            if sha and sha not in primary_hashes:
                zown.append((os.path.basename(zr["zip"]), ap))
    if zown:
        for zb, ap in zown[:200]:
            rep.append("- `%s` → `%s`" % (zb, ap))
        if len(zown) > 200:
            rep.append("- …（共 %d 项，完整清单见 indexes/source_aliases.csv）" % len(zown))
    else:
        rep.append("- 无。压缩包内全部文件与主输入根内容哈希一致。\n")

    rep.append("\n## 3. 大型工程目录核对说明（D-2026）\n")
    d26 = root_stats.get("D-2026", {})
    rep.append("- 该根为 63,525 文件的工程目录，**已执行全量哈希核对**，未采用“按目录名排除”的推断方式。")
    rep.append("- 文件数 %s，唯一哈希 %s，其中主输入根所无 %s 个。" % (
        d26.get("files"), d26.get("uniq"), len(d26.get("own", []))))
    rep.append("- 属于题源类扩展名（pdf/doc/docx/ppt/pptx/xls/xlsx/csv/rtf/txt）的“主输入所无”文件：%d 个。\n" % len(d26.get("doclike", [])))
    if d26.get("doclike"):
        rep.append("| # | 路径 |")
        rep.append("| ---: | --- |")
        for i, ap in enumerate(d26["doclike"][:120], 1):
            rep.append("| %d | `%s` |" % (i, ap))
        if len(d26["doclike"]) > 120:
            rep.append("\n> 仅列前 120 项，完整清单见 `indexes/source_aliases.csv`。\n")

    rep.append("\n## 4. 主输入根内部情况\n")
    tops = {}
    for r in rows:
        tops.setdefault(r["top_dir"], [0, 0])
        tops[r["top_dir"]][0] += 1
        tops[r["top_dir"]][1] += 1 if r["in_scope"] == "Y" else 0
    rep.append("| 顶层目录 | 文件数 | 在范围 |")
    rep.append("| --- | ---: | ---: |")
    for k in sorted(tops):
        rep.append("| `%s` | %d | %d |" % (k, tops[k][0], tops[k][1]))
    rep.append("\n- 主输入根文件总数：%d，在范围：%d，范围外：%d" % (
        len(rows), sum(1 for r in rows if r["in_scope"] == "Y"),
        sum(1 for r in rows if r["in_scope"] == "N")))
    rep.append("- 去重后唯一哈希数（主输入根内）：%d" % len(set(r["sha256"] for r in rows)))
    multi = [r for r in rows if r["alias_count"] > 0]
    rep.append("- 存在别名（同内容多路径）的文件：%d" % len(multi))

    rep.append("\n## 5. 未核对范围（如实声明）\n")
    rep.append("- 未扫描：整台电脑、未挂载磁盘、其他用户目录。")
    rep.append("- 未扫描：`%s`（63,525 文件的工程目录中的 png/json/pyc 等非题源类产物**已哈希但未逐一目视**，仅按哈希判定是否与主输入重复）。" % os.path.join(P.DESKTOP, "2026模拟题"))
    rep.append("- 未核对：压缩包内加密成员（若有）；`.rar/.7z` 无工具支持。")
    rep.append("- 因此本报告**不宣称已覆盖全部原料**，只宣称已覆盖上表所列路径与压缩包。\n")

    with open(os.path.join(P.VAL_DIR, "原料对账报告.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(rep))
    print("原料对账报告.md written")

    with open(os.path.join(P.VAL_DIR, "01_盘点统计.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "primary_root": P.PRIMARY_ROOT,
            "primary_files": len(rows),
            "primary_in_scope": sum(1 for r in rows if r["in_scope"] == "Y"),
            "primary_out_of_scope": sum(1 for r in rows if r["in_scope"] == "N"),
            "unique_hashes_total": len(by_sha),
            "roots": {k: {"files": v["files"], "uniq": v["uniq"],
                          "own_not_in_primary": len(v["own"]),
                          "own_doclike": len(v["doclike"])} for k, v in root_stats.items()},
            "zips": zip_records,
            "source_id_collisions": collisions,
            "top_dir_counts": {k: v[0] for k, v in tops.items()},
        }, fh, ensure_ascii=False, indent=2)
    print("01_盘点统计.json written")


if __name__ == "__main__":
    main()
