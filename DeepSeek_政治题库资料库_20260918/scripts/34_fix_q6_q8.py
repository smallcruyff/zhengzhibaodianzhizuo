#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""续修 2026-09-21 · B4：2026 北京高考 Q6 表格与 Q8 选项框定向修复。

任务书第一步第 5 条：纠正已知的 2026 北京高考 Q6 表格行列与阅读顺序、
Q8 四个选项框及 B/C 标签；恢复原卷边界，不按答案反推原题。
图表需具体到原页/裁切资产，不能只给整个 source_id 文件夹。

依据（实际打开，非推断）：
  assets/S150b8360ec5c/pages/p003.png（2026 北京高考思想政治 第 3 页）
  + evidence/S150b8360ec5c/native_text/pages.jsonl 的逐块 bbox
  + evidence/S150b8360ec5c/visual_transcript/p003.ocr.txt

改正写入**独立 verified 小节**（`## 题面（原页核验改正，verified）`），
原始 native / OCR 候选块原样保留、不覆盖；读取指引改为优先采用该小节。
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

SID = "S150b8360ec5c"
PAGE = 3
EXAM = "BJ-2026-BJ-GAOKAO"
VERIFIED_TITLE = "题面（原页核验改正，verified）"

Q6 = """6．2026 年 2 月，根据《现代汉语词典》（第 7 版）改排而成的《现代汉语词典》（第 7 版·倒序本）出版发行。两者的区别是正序本的多字条目按构词首字排序，倒序本则是按构词末字排序。倒序本传承了我国古代倒序辞书的编纂传统，是国家通用语言文字高质量普及的缩影。《现代汉语词典》倒序本

**【原页表格：查“书”字时】**（原页为两列表格，表头「查“书”字时」跨两列合并；下列 HTML 表保留合并单元格与行列关系）

<table>
<tr><td colspan="2" align="center">查“书”字时</td></tr>
<tr><td align="center">正序本</td><td align="center">倒序本</td></tr>
<tr><td align="center">首字为书</td><td align="center">末字为书</td></tr>
<tr><td align="center">书店</td><td align="center">草书</td></tr>
<tr><td align="center">书法</td><td align="center">楷书</td></tr>
<tr><td align="center">书房</td><td align="center">历书</td></tr>
<tr><td align="center">书画</td><td align="center">隶书</td></tr>
<tr><td align="center">书写</td><td align="center">韵书</td></tr>
</table>

A．按照构词末字聚合词汇，便于查阅特定门类知识
B．为文字研究提供独特视角，替代正序本查字功能
C．丰富了词语的内涵，方便通过词语联想加深理解
D．扩展了词语的外延，为诗词用韵提供查考便利
"""

Q8 = """8．《负荆请罪》中深明大义的廉颇，《红岩》中铁骨铮铮的江姐……在校园课本剧展演活动中，同学们以话剧、音乐剧、歌舞剧等多种形式将课文转化为生动的舞台情景，感受真善美的力量。在活动中，所有展演剧目都是学生出演的，且有些展演剧目是音乐剧。以上划线的联言判断为真，则下列哪个选项是可以确保得到真实结论的演绎推理

**【原页四个选项框】**（原页为 2×2 虚线框，标签位于各框正下方居中；下列按框还原，A=左上、B=右上、C=左下、D=右下）

| 框位 | 标签 | 框内原文（按行） |
| --- | --- | --- |
| 左上 | A | 展演剧目要么是学生出演的，要么是音乐剧。 |
| 右上 | B | 有些学生出演的是音乐剧。<br>所以，有些音乐剧是学生出演的。 |
| 左下 | C | 有些展演剧目不是音乐剧，且所有的展演剧目都是学生出演的。<br>所以，有些学生出演的不是音乐剧。 |
| 右下 | D | 有些展演剧目是音乐剧。<br>有些展演剧目是学生出演的。<br>所以，有些学生出演的是音乐剧。 |

按框逐字还原：

**A**（左上框）
```
展演剧目要么是学生出演的，要么是音乐剧。
```

**B**（右上框）
```
有些学生出演的是音乐剧。
所以，有些音乐剧是学生出演的。
```

**C**（左下框）
```
有些展演剧目不是音乐剧，且所有的展演剧目都是学生出演的。
所以，有些学生出演的不是音乐剧。
```

**D**（右下框）
```
有些展演剧目是音乐剧。
有些展演剧目是学生出演的。
所以，有些学生出演的是音乐剧。
```
"""

DET = {
    "BJ-2026-BJ-GAOKAO-Q6": {
        "corrected": Q6,
        "改正说明": (
            "① 恢复题干阅读顺序：native 把「（第 7 版·倒序本）出版发行。…多字条目」与"
            "「词典》」拆错位，现将「《现代汉语词典》（第 7 版·倒序本）」还原为连续文本；"
            "② 恢复原页表格：native 完全没有该表，OCR 把 5 行压成平铺行"
            "（「书房历书」「书写韵书」串行）；现按原页还原为两列、表头跨列、5 行数据；"
            "③ 四个选项 A—D 按原页顺序保留。"
        ),
        "原值": ("native：题干阅读顺序错位且无右侧表格；"
                 "OCR：表中文字存在但被压为平铺行（书房历书／书写韵书 串行）"),
        "裁切资产": "validation/续修_20260921/裁切资产/BJ-2026-BJ-GAOKAO-Q6_p003_table.png",
        "旧needs_review": "N（旧标记不可靠）",
    },
    "BJ-2026-BJ-GAOKAO-Q8": {
        "corrected": Q8,
        "改正说明": (
            "① native 把左右栏四个选项框交织成一段，选项边界丢失；"
            "② OCR 有错字（「展演剧苜」「学生茁演」「音乐前」等）、B/C 标签缺失与串行；"
            "③ 现按原页 2×2 虚线框还原 A/B/C/D 四框原文，并恢复 A=左上、B=右上、"
            "C=左下、D=右下的标签对应关系。未按答案反推原题。"
        ),
        "原值": ("native：左右栏交织、无框边界；"
                 "OCR：错字 + B/C 标签缺失 + 串行"),
        "裁切资产": "validation/续修_20260921/裁切资产/BJ-2026-BJ-GAOKAO-Q8_p003_boxes.png",
        "旧needs_review": "N（旧标记不可靠）",
    },
}


def split_sections(md):
    ms = list(re.finditer(r"^## (.+)$", md, re.M))
    out = []
    for i, m in enumerate(ms):
        e = ms[i + 1].start() if i + 1 < len(ms) else len(md)
        out.append((m.group(1).strip(), m.start(), m.end(), md[m.end():e]))
    return out


def main():
    now = datetime.datetime.now().isoformat(timespec="seconds")
    log = []
    for qid, d in DET.items():
        fp = os.path.join(P.Q_DIR, EXAM, "%s.md" % qid)
        md = open(fp, encoding="utf-8").read()
        if VERIFIED_TITLE in md:
            print("%s 已有 verified 小节，跳过" % qid)
            continue
        secs = split_sections(md)
        # 备份原值片段
        old_stem = ""
        for t, _s, _e, body in secs:
            if t.startswith("题目原文（原卷"):
                old_stem = body
                break
        if not old_stem:
            for t, _s, _e, body in secs:
                if t.startswith("原卷 OCR 候选"):
                    old_stem = body
                    break

        hdr = ("\n## %s\n\n" % VERIFIED_TITLE
               + "> **核验依据**：实际打开 `assets/%s/pages/p%03d.png`"
                 "（2026 北京高考思想政治 第 %d 页），对照逐块 bbox 与 OCR 候选。\n"
                 % (SID, PAGE, PAGE)
               + "> **改正内容**：%s\n" % d["改正说明"]
               + "> **原值**：%s\n" % d["原值"]
               + "> **原图依据**：`assets/%s/pages/p%03d.png`；裁切 `%s`\n"
                 % (SID, PAGE, d["裁切资产"])
               + "> **执行者**：DeepSeek-V4.1-Flash（本会话）；**时间**：%s\n" % now
               + "> **父稿**：原始 native / OCR 候选块原样保留在下方各节，未被覆盖。\n\n"
               + d["corrected"] + "\n")

        # 插到"读取指引"之后、"题目原文"之前
        idx_guide = next((i for i, s in enumerate(secs)
                          if s[0] == "读取指引（机器可读）"), None)
        if idx_guide is None:
            raise SystemExit("%s 无读取指引小节" % qid)
        insert_at = secs[idx_guide][2] + len(secs[idx_guide][3])
        new_md = md[:insert_at] + hdr + md[insert_at:]

        # 更新读取指引：优先采用 verified 小节
        new_md = re.sub(
            r"^- 采用题面小节: .*$",
            "- 采用题面小节: `%s`" % VERIFIED_TITLE, new_md, count=1, flags=re.M)
        new_md = re.sub(
            r"^- 采用题面来源性质: .*$",
            "- 采用题面来源性质: 原页核验改正（依据 `assets/%s/pages/p%03d.png`，"
            "见本小节核验依据）" % (SID, PAGE), new_md, count=1, flags=re.M)
        new_md = re.sub(
            r"^- 评分关系状态: (.*)$",
            r"- 评分关系状态: \1\n- 原页核验: 已核（2026-09-21，Q6 表格/阅读顺序、"
            "Q8 四框与 B/C 标签）", new_md, count=1, flags=re.M)

        with open(fp, "w", encoding="utf-8") as fh:
            fh.write(new_md)
        log.append({
            "question_id": qid,
            "file": os.path.relpath(fp, P.OUT_ROOT),
            "verified_section_added": True,
            "parent_preserved": True,
            "旧题面片段首200字": old_stem.strip()[:200],
            "改正说明": d["改正说明"],
            "原图依据": "assets/%s/pages/p%03d.png" % (SID, PAGE),
            "裁切资产": d["裁切资产"],
            "执行者": "DeepSeek-V4.1-Flash",
            "时间": now,
            "分类": "复核（非新增页面）",
        })
        print("%s 已写入 verified 小节" % qid)

    out = os.path.join(P.VAL_DIR, "续修_20260921", "34_Q6_Q8修复日志.jsonl")
    with open(out, "w", encoding="utf-8") as fh:
        for x in log:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    print("日志:", out)


if __name__ == "__main__":
    main()
