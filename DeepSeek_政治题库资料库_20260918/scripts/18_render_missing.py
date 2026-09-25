#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A1：补齐视觉核验任务清单里缺失的页面渲染图。

实测发现：清单里 425 个缺图页**全部是 PPTX 幻灯片**——PPTX/DOCX 此前从未渲染成图片。
因此本脚本对非 PDF 来源先经 LibreOffice headless 转 PDF（写入 evidence/{sid}/converted/，
不碰原件），再按页 pdftoppm 渲染。

注意（须如实登记）：PPTX 的视觉核验对象是 **LibreOffice 渲染出的图像**，
不是原件二进制本身。若转换缺字体或版式漂移，会在 visual_review 里注明。
"""
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

TASK = os.path.join(P.VAL_DIR, "视觉核验任务清单.jsonl")
DPI = "300"


def find_or_make_pdf(sid, m, log):
    """返回可渲染的 pdf 路径；非 PDF 先转换。"""
    src = m["original_path"]
    if src.lower().endswith(".pdf"):
        return src, False
    cdir = os.path.join(P.EVID_DIR, sid, "converted")
    P.ensure_dirs(cdir)
    for f in os.listdir(cdir):
        if f.lower().endswith(".pdf"):
            return os.path.join(cdir, f), True
    env = P.env_with_fontconfig()
    rc, out, err = P.run([P.SOFFICE, "--headless", "--norestore",
                          "--convert-to", "pdf", "--outdir", cdir, src],
                         timeout=600, env=env)
    made = [f for f in os.listdir(cdir) if f.lower().endswith(".pdf")]
    if made:
        return os.path.join(cdir, made[0]), True
    # 替代路径：命名空间修补版
    rep = os.path.join(P.EVID_DIR, sid, "repaired", "repaired.pptx")
    if os.path.isfile(rep):
        rc, out, err = P.run([P.SOFFICE, "--headless", "--norestore",
                              "--convert-to", "pdf", "--outdir", cdir, rep],
                             timeout=600, env=env)
        made = [f for f in os.listdir(cdir) if f.lower().endswith(".pdf")]
        if made:
            log.append("%s: 原件转换失败，改用命名空间修补版转出 PDF" % sid)
            return os.path.join(cdir, made[0]), True
    # 替代路径2：重新打包（实测有原件 zip 结构不被 LibreOffice 接受，重打包即可转换）
    try:
        import zipfile
        zin = zipfile.ZipFile(src)
        names = zin.namelist()
        rez = os.path.join(cdir, "rezipped.pptx")
        with zipfile.ZipFile(rez, "w", zipfile.ZIP_DEFLATED) as zout:
            for n in names:
                if n.startswith("__MACOSX"):
                    continue
                try:
                    zout.writestr(n, zin.read(n))
                except Exception:
                    pass
        rc, out, err = P.run([P.SOFFICE, "--headless", "--norestore",
                              "--convert-to", "pdf", "--outdir", cdir, rez],
                             timeout=900, env=env)
        made = [f for f in os.listdir(cdir) if f.lower().endswith(".pdf")]
        if made:
            log.append("%s: 原件无法被 LibreOffice 加载；重新打包后转换成功"
                       "（原件 zip 结构问题，属原件缺陷，已登记）" % sid)
            return os.path.join(cdir, made[0]), True
    except Exception as e:
        log.append("%s: 重打包失败 %r" % (sid, e))
    log.append("%s: 转换失败 rc=%d %s" % (sid, rc, err[:120]))
    return None, True


def main():
    rows = [json.loads(l) for l in open(TASK, encoding="utf-8")]
    man = {m["source_id"]: m for m in csv.DictReader(
        open(os.path.join(P.INDEX_DIR, "source_manifest.csv"), encoding="utf-8"))}

    by_src = {}
    for r in rows:
        if os.path.isfile(os.path.join(P.OUT_ROOT, r["render"])):
            continue
        by_src.setdefault(r["source_id"], []).append(r["page"])
    print("待补渲: %d 页 / %d 个文件" % (sum(len(v) for v in by_src.values()), len(by_src)))

    log = []
    done = fail = 0
    for sid, pages in sorted(by_src.items(), key=lambda x: -len(x[1])):
        m = man.get(sid)
        if not m:
            continue
        pdf, converted = find_or_make_pdf(sid, m, log)
        if not pdf:
            fail += len(pages)
            continue
        pdir = os.path.join(P.EVID_DIR, sid, "pages")
        P.ensure_dirs(pdir)
        for pg in sorted(pages):
            target = os.path.join(pdir, "p%03d.png" % pg)
            if os.path.isfile(target):
                done += 1
                continue
            rc, out, err = P.run([os.path.join(P.POPPLER_BIN, "pdftoppm"),
                                  "-r", DPI, "-png", "-f", str(pg), "-l", str(pg),
                                  pdf, os.path.join(pdir, "p")], timeout=300)
            # poppler 实际命名为 p-NN.png / p-NNN.png（零填充位数随总页数变化），统一改名
            pat = re.compile(r"^p-0*%d\.png$" % pg)
            got = [f for f in os.listdir(pdir) if pat.match(f)]
            if got:
                os.replace(os.path.join(pdir, got[0]), target)
                done += 1
            else:
                fail += 1
                log.append("%s p%d 渲染失败 rc=%d: %s" % (sid, pg, rc, err[:100]))
        # 记录渲染原因
        mp = os.path.join(P.EVID_DIR, sid, "meta.json")
        if os.path.isfile(mp):
            try:
                meta = json.load(open(mp, encoding="utf-8"))
            except Exception:
                meta = {}
            rsn = meta.setdefault("render_reasons", {})
            for pg in pages:
                rsn.setdefault(str(pg), [])
                if "supplement_for_visual_review" not in rsn[str(pg)]:
                    rsn[str(pg)].append("supplement_for_visual_review")
            if converted:
                meta["render_source"] = "LibreOffice 渲染（非原件二进制本身）"
            json.dump(meta, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("  %-22s 补渲 %d 页 %s" % (sid, len(pages),
                                       "(经 LibreOffice 转 PDF)" if converted else ""))

    print("补渲完成: 成功 %d / 失败 %d" % (done, fail))
    miss = [r for r in rows if not os.path.isfile(os.path.join(P.OUT_ROOT, r["render"]))]
    print("剩余缺图页:", len(miss))
    with open(os.path.join(P.VAL_DIR, "08b_补渲日志.json"), "w", encoding="utf-8") as fh:
        json.dump({"done": done, "fail": fail, "remaining": len(miss), "log": log},
                  fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
