#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""续修 2026-09-21 · B5-1：2026 丰台一模 试卷（S6e8f2df5ef86）10 页逐页校对。

本批实际打开 evidence/S6e8f2df5ef86/pages/p001..p010.png（10 页，全部为扫描页），
逐页对照 native/OCR 候选与页面内容，产出：

  1. 对已入索引的题写入独立 verified 题面小节（原始 OCR/native 原样保留）；
  2. 对**原页确有、但本库未切出**的题（Q5/Q7/Q9/Q14/Q21）补建单题文件并登记索引；
  3. 逐页登记 visual_review 记录（带真实查看证据）。

扫描件 OCR 实测错字（本批已改正）：
  Q1  殷切寄语→OCR"殿切寄语"；改革开放→OCR"改革放"（漏"开"）；融入→OCR"融人"
  Q4  选项 D.③④→OCR 断成 "D." + "⑧④"（③误读为⑧，且串行）
  Q6  塔影入湖→OCR"塔影人湖"；"借景"→OCR"借暴"；立足局部→OCR"立足良部"；
      选项 A.①②→OCR"A.②"（漏①）；B.①④→OCR"B.O④"
  Q7  诊治→OCR"诊活"；思维→OCR"恩维"；③题肢圈号缺失
  Q3  最后一道防线→OCR"最后～道防线"；题末混入页脚与"扫描全能王"水印
  Q2  "全国人民陪审员"→OCR 多出引号"“民陪审员"
"""
import csv
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

SID = "S6e8f2df5ef86"
EXAM = "BJ-2026-FT-YIMO"
RELPATH = "2026模拟题/2026各区一模/2026丰台一模/试卷/试卷.pdf"
VERIFIED_TITLE = "题面（原页核验改正，verified）"

# ---------------------------------------------------------------- 逐页校对结论
PAGE_FINDINGS = {
    1: {
        "carries": ["BJ-2026-FT-YIMO-Q1", "BJ-2026-FT-YIMO-Q2", "BJ-2026-FT-YIMO-Q3"],
        "findings": [
            "Q1：OCR『殿切寄语』应为『殷切寄语』（错字）",
            "Q1：OCR『改革放是决定党和国家前途命运的根本力量』漏『开』，应为『改革开放』",
            "Q1：OCR『融人国家和民族』应为『融入』（错字）",
            "Q2：OCR『全国人 / “民陪审员达34万人』多出引号并串行，应为『全国人民陪审员达34万人』",
            "Q2：OCR 选项『C ②④』缺间隔点，页面为『C. ②④』",
            "Q3：OCR『最后～道防线』应为『最后一道防线』（错字）",
            "Q3：OCR 题末混入页脚『高三思想政治 第1页（共10页）』与『扫描全能王』水印噪声",
            "Q1—Q3 题干、四个题肢与组合选项的圈号与组合关系均与页面一致",
        ],
        "verdict": "有错漏（OCR 错字/漏字/串行），题面结构与选项组合正确",
    },
    2: {
        "carries": ["BJ-2026-FT-YIMO-Q4", "BJ-2026-FT-YIMO-Q5", "BJ-2026-FT-YIMO-Q6",
                    "BJ-2026-FT-YIMO-Q7"],
        "findings": [
            "Q4：OCR 选项 D 被断成两行『D.』+『⑧④』，③误读为⑧，应为『D. ③④』",
            "Q4：『资料卡』为原页右上虚线框内容（在重力作用下，物体从高处到低处运动速度最快的路线并非直线，而是旋轮线，也称为“最速降线”），OCR 已取到",
            "Q5：**原页确有第5题（量子通信），但本库未切出**，OCR 有文本、索引无题键",
            "Q6：OCR『塔影人湖成景』应为『塔影入湖成景』",
            "Q6：OCR『“借暴”』应为『“借景”』",
            "Q6：OCR『立足良部景观』应为『立足局部景观』",
            "Q6：OCR 选项『A. ②』漏①，应为『A. ①②』；『B.O④』应为『B. ①④』",
            "Q7：**原页确有第7题（四诊法），但本库未切出**",
            "Q7：OCR『方法诊活』应为『方法诊治』；『超前恩维』应为『超前思维』；③题肢圈号缺失",
        ],
        "verdict": "有错漏（含两题未切出：Q5、Q7）",
    },
    3: {
        "carries": ["BJ-2026-FT-YIMO-Q8", "BJ-2026-FT-YIMO-Q9", "BJ-2026-FT-YIMO-Q10",
                    "BJ-2026-FT-YIMO-Q11"],
        "findings": [
            "Q8：题干含右图（『北京志愿者 BEIJING VOLUNTEERS』心形标识），须打开原页可见；OCR 未取到该图内容",
            "Q8：四个题肢①—④与选项 A.①③ B.①④ C.②③ D.②④ 与页面一致",
            "Q9：**原页确有第9题（元宵节猜灯谜），但本库未切出**；四个选项为 A—D 直接选项（非①②③④组合）",
            "Q10：题干、四题肢与选项 A.①② B.①③ C.②④ D.③④ 与页面一致",
            "Q11：题干、四题肢与选项 A.①② B.①④ C.②③ D.③④ 与页面一致",
        ],
        "verdict": "有缺口（Q9 未切出）；Q8 依赖右图",
    },
    4: {
        "carries": ["BJ-2026-FT-YIMO-Q12", "BJ-2026-FT-YIMO-Q13", "BJ-2026-FT-YIMO-Q14"],
        "findings": [
            "Q12：题干与传导路径①—④、选项 A.①② B.①③ C.②④ D.③④ 与页面一致",
            "Q13：题干含《互联网平台价格行为规则》四方面要点框（一是…四是…），OCR 已取到框内文字",
            "Q14：**第14题（中非外交关系70周年）自本页开始、跨至第5页结束，本库未切出**",
            "Q14：本页含三个圆角框（接待来访／零关税／人文交流年），第5页为『中非关系新发展』四题肢与选项",
        ],
        "verdict": "有缺口（Q14 未切出，且跨第4—5页）",
    },
    5: {
        "carries": ["BJ-2026-FT-YIMO-Q14", "BJ-2026-FT-YIMO-Q15"],
        "findings": [
            "Q14（接第4页）：『中非关系新发展』四题肢与选项 A.①② B.①③ C.②④ D.③④ 与页面一致",
            "Q15：题干含 APEC 第一次高官会『一个目标／两条路径／三个转型／多元合作』要点框，OCR 已取到框内文字",
            "Q15：四题肢与选项 A.①② B.①④ C.②③ D.③④ 与页面一致",
        ],
        "verdict": "Q14 跨页关系确认；Q15 内容一致",
    },
    6: {
        "carries": ["BJ-2026-FT-YIMO-Q16", "BJ-2026-FT-YIMO-Q17"],
        "findings": [
            "本页为『第二部分』起始，『本部分共6题，共55分』",
            "Q16（8分）：人工智能主题，材料两段 + 设问『结合材料，运用《哲学与文化》知识，谈谈你对这一时代命题的思考。』与页面一致",
            "Q17（8分）：生态环境法典主题，材料三段 + 设问『结合材料，运用《政治与法治》知识，阐释生态环境法典的诞生为什么是中华民族迈向永续发展的宣言书和路线图。』与页面一致",
        ],
        "verdict": "未发现错漏",
    },
    7: {
        "carries": ["BJ-2026-FT-YIMO-Q18"],
        "findings": [
            "Q18（14分）：含『用好“加减乘除”推动消费持续增长』2×2 要点框（加法／减法／乘法／除法）",
            "第（1）问：运用《经济与社会》知识，分析『加减乘除』在推动消费持续增长的过程中是怎样发挥作用的。（8分）",
            "第（2）问：甲乙两位同学推理（甲为必要条件假言推理、乙为三段论），『分别写出上述推理的类型，判断是否正确，并说明理由。（6分）』",
            "两小问的分值与设问与页面一致",
        ],
        "verdict": "未发现错漏",
    },
    8: {
        "carries": ["BJ-2026-FT-YIMO-Q19"],
        "findings": [
            "Q19（8分）：含『可持续发展目标』17 个图标网格（1无贫穷…17促进目标实现的伙伴关系）",
            "三个要点框：消除贫困／教育普及／卫生健康",
            "设问：结合材料，运用《当代国际政治与经济》知识，说明中国在全球可持续发展中彰显了怎样的大国情怀与担当。",
            "17 图标网格为图形化内容，文字层与 OCR 均无法完整恢复，须依赖原页图",
        ],
        "verdict": "有图形依赖（17 目标图标网格）；文字一致",
    },
    9: {
        "carries": ["BJ-2026-FT-YIMO-Q20"],
        "findings": [
            "Q20（8分）：民法典第一千一百九十八条引用框 + 【基本案情】+【裁判结果】+ 设问（运用《法律与生活》知识，阐明人民法院作出该判决的法理依据和现实意义）",
            "与页面一致",
        ],
        "verdict": "未发现错漏",
    },
    10: {
        "carries": ["BJ-2026-FT-YIMO-Q21"],
        "findings": [
            "Q21（9分）：**原页确有第21题，但本库未切出**",
            "含『精准识变／科学应变／主动求变』三个要点框",
            "设问：结合材料，综合运用所学，谈谈你对善于识变应变求变的理解。",
        ],
        "verdict": "有缺口（Q21 未切出）",
    },
}


def load_verified_texts():
    p = os.path.join(P.VAL_DIR, "续修_20260921", "B5_FTYIMO_题面.json")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def split_sections(md):
    ms = list(re.finditer(r"^## (.+)$", md, re.M))
    out = []
    for i, m in enumerate(ms):
        e = ms[i + 1].start() if i + 1 < len(ms) else len(md)
        out.append((m.group(1).strip(), m.start(), m.end(), md[m.end():e]))
    return out


def main():
    now = datetime.datetime.now().isoformat(timespec="seconds")
    texts = load_verified_texts()
    log = []

    for num_s, item in sorted(texts.items(), key=lambda kv: int(kv[0])):
        qid = item["question_id"]
        fp = os.path.join(P.Q_DIR, EXAM, "%s.md" % qid)
        new_file = not os.path.isfile(fp)

        hdr = ("\n## %s\n\n" % VERIFIED_TITLE
               + "> **核验依据**：实际打开 `evidence/%s/pages/p%03d.png`"
                 "（2026 北京丰台一模 思想政治 试卷 第 %d 页，纯扫描件），逐字对照 OCR 候选。\n"
                 % (SID, item["page"], item["page"])
               + "> **原图依据**：`assets/%s/pages/p%03d.png`\n" % (SID, item["page"])
               + "> **执行者**：DeepSeek-V4.1-Flash（本会话）；**时间**：%s\n" % now
               + "> **本批**：B5-1（2026 丰台一模试卷 10 页逐页校对）\n"
               + ("> **改正内容**：%s\n" % item["fixes"] if item.get("fixes") else
                  "> **改正内容**：本页未发现文字错漏；题面按原页逐字录入。\n")
               + ("> **父稿**：原始 OCR 候选块原样保留在下方，未被覆盖。\n"
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
                  + "- 原页核验: 已核（2026-09-21，B5-1 丰台一模试卷逐页校对）\n"
                  + hdr
                  + "\n## 正式评分材料原文\n\n（未找到已确认的正式评分材料）\n\n"
                  + "## 参考答案原文\n\n（无）\n\n"
                  + "## 来源定位\n- `%s`（原卷 / 扫描件，第 %d 页）\n"
                    % (RELPATH, item["page"])
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
                        r"- 评分关系状态: \1\n- 原页核验: 已核（2026-09-21，B5-1 丰台一模试卷逐页校对）",
                        md, count=1, flags=re.M)
            md = re.sub(r"^- extraction_status: .*$", "- extraction_status: verified",
                        md, count=1, flags=re.M)
            md = re.sub(r"^- needs_review: .*$", "- needs_review: N（题面已按原页核验）",
                        md, count=1, flags=re.M)

        with open(fp, "w", encoding="utf-8") as fh:
            fh.write(md)
        log.append({"question_id": qid, "page": item["page"],
                    "new_file": new_file, "fixes": item.get("fixes", ""),
                    "原图依据": "evidence/%s/pages/p%03d.png" % (SID, item["page"]),
                    "执行者": "DeepSeek-V4.1-Flash", "时间": now})
        print("%s %s" % (qid, "新建" if new_file else "写入 verified"))

    out = os.path.join(P.VAL_DIR, "续修_20260921", "B5_1_丰台一模修复日志.jsonl")
    with open(out, "w", encoding="utf-8") as fh:
        for x in log:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    print("日志:", out, "共", len(log), "题")

    # 逐页登记 visual_review
    recs = []
    for pg, d in PAGE_FINDINGS.items():
        recs.append({
            "source_id": SID, "page": pg,
            "viewed_file": "evidence/%s/pages/p%03d.png" % (SID, pg),
            "method": "实际打开原页渲染图（纯扫描件），逐字对照 OCR 候选与页面内容",
            "page_class": "scan_or_empty",
            "findings": d["findings"],
            "affected_questions": d["carries"],
            "action": "本页已实际打开逐项对照；结论：%s" % d["verdict"],
            "reviewer": "DeepSeek-V4.1-Flash",
        })
    rp = os.path.join(P.VAL_DIR, "续修_20260921", "B5_1_丰台一模逐页记录.json")
    with open(rp, "w", encoding="utf-8") as fh:
        json.dump(recs, fh, ensure_ascii=False, indent=2)
    print("逐页记录:", rp)


if __name__ == "__main__":
    main()
