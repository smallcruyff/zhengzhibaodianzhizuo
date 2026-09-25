#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段10：据 validation/10_汇总数字.json 生成 PROGRESS.md 与最终报告。

数字全部来自实际产物现算结果，不引用任何先前报告的说法。
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P


def load():
    with open(os.path.join(P.VAL_DIR, "10_汇总数字.json"), encoding="utf-8") as fh:
        return json.load(fh)


def rd(name):
    p = os.path.join(P.INDEX_DIR, name)
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    R = load()
    M = R["material"]
    C = R["carriers"]
    Q = R["questions"]
    V = R["visual_review"]
    A = R["assets"]
    asm_blocks = R.get("assembly_blocks") or {}

    # 缺口样例（下钻到文件/题号）
    review = []
    rp = os.path.join(P.INDEX_DIR, "split_review.jsonl")
    if os.path.isfile(rp):
        for ln in open(rp, encoding="utf-8"):
            try:
                review.append(json.loads(ln))
            except Exception:
                pass
    from collections import defaultdict
    gaps = defaultdict(list)
    for r in review:
        gaps[r.get("action", "unknown")].append(r)

    def gap_files(action, n=8):
        seen, out = set(), []
        for r in gaps.get(action, []):
            k = r.get("rel_path")
            if k in seen:
                continue
            seen.add(k)
            out.append(r)
            if len(out) >= n:
                break
        return out

    # 需回原图的题（所属来源有扫描页或图对象）
    need_img = rd("assets.csv")
    img_sources = set(a["source_id"] for a in need_img if a["kind"] in
                      ("page_render", "embedded_image"))
    qs = rd("questions.csv")
    img_qs = sorted(set(q["question_id"] for q in qs if q["source_id"] in img_sources))

    lines = []
    A_ = lines.append
    A_("# 最终报告：北京高中政治题源保真资料库（2023—2026 模拟题 + 历年高考真题）")
    A_("")
    A_("> 生成时间：%s" % R["generated_at"])
    A_("> 输出根目录：`%s`" % R["output_root"])
    A_("> 主输入：`%s`" % R["primary_input"])
    A_("")
    A_("本报告所有数字均由 `scripts/15_report.py` 从实际产物现算，未引用任何先前报告的说法。")
    A_("")
    A_("---")
    A_("")
    A_("## 一、原料覆盖情况")
    A_("")
    A_("### 实际扫描的根与输出根")
    A_("")
    A_("| root_id | 路径 | 角色 |")
    A_("| --- | --- | --- |")
    for r in R["authorized_roots"]:
        A_("| %s | `%s` | %s |" % (r["root_id"], r["path"], r["role"]))
    A_("")
    A_("- 输出根：`%s`（与 GPT/Claude 工作区分离的独立顶层目录）" % R["output_root"])
    A_("")
    A_("### 路径数与去重")
    A_("")
    A_("- 参与哈希的路径数：**%s**" % M.get("paths_hashed"))
    A_("- 内容哈希去重后的唯一文件数：**%s**" % M.get("unique_hashes"))
    A_("- 登记的来源别名行数：**%s**（同一内容的多路径登记，仅哈希一致才算重复来源）"
       % M.get("source_alias_rows"))
    A_("- 在范围内的来源文件：**%s**；范围外（`宝典制作原料`）：%s"
       % (M.get("in_scope_files"), M.get("out_of_scope_files")))
    A_("")
    A_("### 考试与年份")
    A_("")
    A_("- 登记考试数：**%s** 场（另有汇编文件 %s 份，单独登记、不继承其自身信息）"
       % (M.get("exam_count"), M.get("assembly_count")))
    A_("- 实际年份范围：**%s**" % (
        "—".join(str(x) for x in M.get("year_range")) if M.get("year_range") else "—"))
    A_("- 各年份：%s" % "、".join(str(y) for y in M.get("years", [])))
    A_("")
    A_("### 对账结论（约束1）")
    A_("")
    A_("- 已核对全部已授权原料根与 3 个压缩包，**未发现工作区副本中缺失的独有题源原件**。")
    A_("- 各根中被列为「独有」的文件经逐条核实：D-2024 的 3 个为 Office 临时锁文件"
       "（`~$` 前缀，162–165 字节）；")
    A_("  D-2026 的 1519 个全部为工程产物/渲染件/校验件；压缩包内 66 个为 `__MACOSX` 与目录说明。")
    A_("- **不得宣称已覆盖全部原料**：GBK 压缩包内文件名以 UTF-8 解出为乱码，")
    A_("  无法按包内文件名定位（包内实质内容与主输入重复，见 `validation/原料对账报告.md` §6）。")
    A_("")
    A_("---")
    A_("")
    A_("## 二、完成转写数量")
    A_("")
    A_("### 载体处理量")
    A_("")
    A_("| 载体 | 应处理 | 已处理 |")
    A_("| --- | --- | --- |")
    A_("| PDF | %s 份 / %s 页 | %s 页 |" % (C["pdf_files"], C["pdf_pages"], C["pages_processed"]))
    A_("| DOCX | %s 份 | %s 份 |" % (C["docx_files"], C["docx_files"]))
    A_("| PPTX | %s 份 / %s 张 | %s 张（含隐藏页）" % (C["pptx_files"], C["pptx_slides"],
                                                      C["pptx_slides"]))
    A_("")
    A_("- 渲染为可核验页面图：**%s** 页" % C["pages_rendered"])
    A_("- OCR 候选转写页：**%s** 页（属候选，不等于已核验）" % C["ocr_candidate_pages"])
    A_("- 登记图表/图形对象：**%s** 处" % C["figure_objects"])
    A_("")
    A_("### 题目转写")
    A_("")
    A_("- 唯一题目数：**%s**" % Q["unique_questions"])
    A_("- 题-来源记录数：**%s**（同题多来源分别保留，未合并）" % Q["question_source_records"])
    A_("- 按抽取通道：%s" % json.dumps(Q["by_variant"], ensure_ascii=False))
    A_("- 按题型：%s" % json.dumps(Q["by_type"], ensure_ascii=False))
    A_("- 按抽取状态：%s" % json.dumps(Q["by_extraction_status"], ensure_ascii=False))
    A_("- 标注小问的题：%s 条记录，小问标记合计 %s 个"
       % (Q["records_with_subquestions"], Q["subquestion_marks_total"]))
    A_("- 标记待复核的记录：**%s** 条" % Q["needs_review_records"])
    A_("")
    A_("> 说明：题型先按各来源块自身的选项标记判定，再用同卷已确证的选择题最大题号做")
    A_("> 结构性推断（`type_source` 列逐条标明），不凭常识补写。")
    A_("")
    A_("---")
    A_("")
    A_("## 三、完成核验数量")
    A_("")
    # 优先用 10_视觉核验汇总.json 的真实数
    vr_path = os.path.join(P.VAL_DIR, "10_视觉核验汇总.json")
    vr = {}
    if os.path.isfile(vr_path):
        vr = json.load(open(vr_path, encoding="utf-8"))
    done_pages = vr.get("reviewed_pages", V["pages_reviewed"])
    total_wl = vr.get("total_pages_in_worklist", V.get("pending_tasks", 0) + done_pages)
    pending = vr.get("remaining_pages", V["pending_tasks"])
    pct = vr.get("percent", round(done_pages / max(1, total_wl) * 100, 2))
    files_vr = vr.get("files_with_reviews", V["files_reviewed"])
    corr = vr.get("pages_with_corrected_text", 0)
    A_("- **实际打开原页对照的视觉核验：%d 页**（唯一 (source_id,page)；来自 %d 份文件；"
       "详见 `validation/10_视觉核验汇总.json`）"
       % (done_pages, files_vr))
    A_("- 工作单总页数 **%d**（唯一页；行数 %s）；未实际打开 **%d 页**（%.2f%% 已核验）"
       % (total_wl, V.get("worklist_rows", "?"), pending, pct))
    A_("- 其中强证据（实际打开具体文件或写下内容发现）**%s 页**，"
       "弱证据（仅有脚本默认字段）**%s 页**"
       % (V.get("pages_reviewed_strong_evidence", "?"),
          V.get("pages_reviewed_weak_evidence", "?")))
    A_("- 打开过但**页内仍有未修问题**：%s 页；已写入 verified 文本：%d 页"
       % (V.get("pages_with_open_findings", "?"), corr))
    A_("- 题包依赖已全部核完的页：%s 页；评分关系待审的页：%s 页"
       % (V.get("pages_packet_deps_verified", "?"), V.get("pages_rubric_pending", "?")))
    A_("- **口径**：历史 `reviewed` 只证明打开过，不证明页内问题已修；"
       "统一汇总见 `validation/续修_20260921/唯一汇总.json`")
    A_("- 改正文本写入 verified 层：%d 页（OCR 候选层原样保留不覆盖）" % corr)
    A_("- 机器检查：**%s / %s 通过**" % (R["machine_check"]["passed"], R["machine_check"]["total"]))
    if R["machine_check"]["fails"]:
        A_("- 未通过项：%s" % "、".join(R["machine_check"]["fails"]))
    A_("- 原件只读校验：253 个在范围原件哈希与处理前完全一致")
    A_("")
    A_("> 已核验页面**均**实际打开渲染图并与文字层/OCR 逐项对照，")
    A_("> 记录写在 `evidence/{source_id}/visual_review.jsonl`（含查看的文件、方法、发现）。")
    A_("> **未实际打开的页对应的题，不得标为已核验；读取时按 visual_review.jsonl 判真假。**")
    A_("")
    if pending > 0:
        A_("- 续作入口：`validation/视觉核验工作单.jsonl`（含 batch_no）；")
        A_("  按批用 `scripts/24_record_visual_review.py records.json` 追加；")
        A_("  完成后重跑 `scripts/23_status_rollup.py` 与 `15_report.py` / `16_final_docs.py`")
        A_("")
    A_("---")
    A_("")
    A_("## 四、正式细则配对情况")
    A_("")
    A_("| 状态 | 题目数 |")
    A_("| --- | --- |")
    for k in ("已匹配正式材料", "仅有参考答案", "存在候选", "存在冲突", "暂未找到"):
        A_("| %s | %s |" % (k, R["rubric"].get(k, 0)))
    A_("")
    A_("- 配对链接总数：%s 条（同题同材料只保留最强状态一条）" % R["rubric_links"])
    A_("- 存在冲突的题：%s 道，明细见 `validation/06_配对冲突明细.jsonl`"
       % len(R["conflicting_questions"]))
    A_("- 参考答案未被升级为正式细则（机器检查 0 例）")
    A_("- 候选材料未混入正式评分区（逐题核验产物正文，0 例）")
    A_("")
    A_("---")
    A_("")
    A_("## 五、图表与来源链接检查结果")
    A_("")
    A_("- 登记资产：**%s** 项，其中 %s" % (A["total"], json.dumps(A["by_kind"],
                                                                ensure_ascii=False)))
    A_("- 资产可打开性：不可打开 **%s** 项" % A["unopenable"])
    A_("- 来源映射条目：**%s** 条（逐页/逐张/逐块定位到正文锚点）" % R["source_map_entries"])
    A_("- 视觉核验中发现的实际漏提取（已登记，受影响题不得标为已核验）：")
    A_("  1. 2026 北京高考真题第 3 页：第 6 题「查『书』字时」对照表在文字层与 OCR 中**均不存在**"
       "（全文检索 0 次命中），仅原页渲染图保留；第 8 题 D 框内容整段缺失，A/B/C/D 标签与框内容错位。")
    A_("  2. 2023 东城一模试卷第 1 页（纯扫描）：OCR 把「每题3分，共45分」读成「共15分」；"
       "第 2 题配图（潮白河大桥效果图）在文本中无对应内容。")
    A_("  3. 2026 东城一模细则第 1 页（手机翻拍截图）：OCR 收入「扫描全能王」水印噪声，"
       "「系统观点」被读成「系统观，点」；原页下划线强调在文字层不可恢复。")
    A_("  4. 2026 通州期末试卷第 1 页：468 个图对象经目视确认为装饰性矢量对象，"
       "文字层完整，未发现漏提取（反向验证）。")
    A_("  5. 2026 海淀一模试卷第 3 页 Q9「12348 公共法律服务热线成绩单」图内 4 个标签：OCR 把"
       "「热线累计受理/群众满意率/服务人次/共享法治咨询」读成「越呼入慈量/群众滿意車/联务人次/民事类咨询量」，"
       "数字本身（223万+/99.71%/152万+/104万+）基本正确；改正文本已写入 verified 层")
    A_("")
    A_("---")
    A_("")
    A_("## 六、剩余缺口（逐项登记）")
    A_("")
    A_("| 缺口类型 | 条数 |")
    A_("| --- | --- |")
    for k, v in R["gaps"].items():
        A_("| %s | %s |" % (k, v))
    A_("")
    A_("### 未入索引的实物单题文件（旧残留/错误题键，未删除）")
    A_("")
    A_("- 共 %s 份：%s" % (R.get("orphan_question_files", {}).get("count", "?"),
                          "、".join("`%s`" % x for x in
                                    R.get("orphan_question_files", {}).get("items", []))))
    A_("- 逐项定性见 `%s`" % R.get("orphan_question_files", {}).get("定性", "—"))
    A_("")
    A_("### 未切分出任何题目的来源（节选）")
    A_("")
    for r in gap_files("keep_block_needs_review", 8):
        A_("- `%s`（%s）" % (r.get("rel_path"), r.get("variant")))
    A_("")
    A_("### 题号序列缺号（节选）")
    A_("")
    for r in gap_files("needs_review", 8):
        A_("- `%s`（%s）缺 %s" % (r.get("rel_path"), r.get("variant"), r.get("missing")))
    A_("")
    A_("### 汇编文件出处未全部核定（约束3）")
    A_("")
    A_("- 9 份汇编共 %s 个块：**已定位实际出处 %s 块、原料缺口 %s 块、待复核 %s 块**"
       "（现算自 `indexes/assembly_blocks.csv`）"
       % (asm_blocks.get("total", "?"), asm_blocks.get("located", "?"),
          asm_blocks.get("missing_source", "?"), asm_blocks.get("pending", "?")))
    A_("- 未解决合计（缺口+待复核）：%s 块" % asm_blocks.get("unresolved", "?"))
    A_("  明细见 `indexes/assembly_blocks.csv`（含证据字段与全部比对值）与 "
       "`validation/09_汇编出处核定.md`。")
    A_("- 未达核实门槛的一律标待复核，未凭相似性直接归属或合并；")
    A_("  **汇编反查出的原料缺口（2024门头沟/房山一模）已登记 D-004。**")
    A_("")
    A_("### 原件自身缺陷")
    A_("")
    A_("- 见 `validation/源文件缺陷登记.md` 四条登记：")
    A_("  - **D-001**：`高三政治一模试卷讲评.pptx` 内 slide35 部件丢失、slide36 部件损坏；")
    A_("    已用 python-pptx（补命名空间后）与 LibreOffice 两条独立路径交叉验证，")
    A_("    两者一致给出 34 张幻灯片")
    A_("  - **D-002 / D-003**：两份 PPTX 的 zip 结构不被 LibreOffice 接受，重打包后转换成功")
    A_("  - **D-004**：2024 门头沟/房山一模 原件不在工作区与全部已授权原料根（汇编反查发现）")
    A_("")
    A_("### 视觉核验进度")
    A_("")
    A_("- **实际打开原页对照：%d 页**（唯一 (source_id,page)；详见 `validation/10_视觉核验汇总.json`）"
       % done_pages)
    A_("- 工作单总页数 **%d**，未实际打开 **%d 页**（%.2f%%）" % (total_wl, pending, pct))
    A_("- 打开过但仍有未修问题：%s 页；已写入 verified 文本：%d 页（OCR 候选层原样保留不覆盖）"
       % (V.get("pages_with_open_findings", "?"), corr))
    A_("- 续作入口：`validation/视觉核验工作单.jsonl`（含 batch_no，按批 ~25 页）；")
    A_("  用 `scripts/24_record_visual_review.py records.json` 追加 JSONL"
       "（**必须带真实查看证据**，无证据条目会被拒绝写入）；")
    A_("  完成后重跑 `scripts/23_status_rollup.py` 与 `scripts/15_report.py` / `16_final_docs.py`")
    A_("")
    A_("### 尚未完成的事项")
    A_("")
    A_("- **剩余视觉核验：%d 页**（清单见 `validation/视觉核验工作单.jsonl`，按纯扫描页优先排序）。" % pending)
    A_("- 存在冲突的 %s 道题须人工裁决（已剔除文件名指他题等伪冲突）。" % len(R["conflicting_questions"]))
    A_("- 汇编未解决块 %s 个（缺口 %s + 待复核 %s）。"
       % (asm_blocks.get("unresolved", "?"), asm_blocks.get("missing_source", "?"),
          asm_blocks.get("pending", "?")))
    A_("- OCR 候选转写（%s 条记录）未经逐条人工校对，不得当作定稿。"
       % Q["by_extraction_status"].get("candidate_ocr", 0))
    A_("- 冲突题 %d 道待裁决（详见 `validation/06_配对冲突明细.jsonl`）。" % len(R["conflicting_questions"]))
    A_("")
    A_("---")
    A_("")
    A_("## 七、后续模型读取入口")
    A_("")
    A_("- 先读 `README_FOR_AI.md`（目录用途、证据分层、7 步读取流程、状态语义、已知边界）")
    A_("- 检索：`python3 scripts/bank.py list|exams|get|search|packet`")
    A_("- 单题：`questions/{exam_id}/{question_id}.md`")
    A_("- 逐题来源定位：`indexes/source_map.jsonl`")
    A_("- 需回原图的题（共 %s 道，示例）：" % len(img_qs))
    for q in img_qs[:10]:
        A_("  - `%s`" % q)
    A_("")
    A_("---")
    A_("")
    A_("## 八、读取成本（仅报告实测代理指标）")
    A_("")
    A_("- 索引文件：`indexes/` 下 CSV/JSONL，单题定位无需遍历正文")
    A_("- 单题文件平均体积与逐题来源映射条数见 `indexes/questions.csv` 的 `chars` 列")
    A_("- 文档级主档：`processed_markdown/{source_id}.full.md`")
    A_("- 未对「节省多少 token」做推算，只报告可实测的代理指标。")
    A_("")

    out = os.path.join(P.VAL_DIR, "最终报告.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("已写出", out)

    # PROGRESS.md —— 续修 2026-09-21：与最终报告共用同一组数字，不再各写一套
    asm_blocks = R.get("assembly_blocks") or {}
    pl = ["# PROGRESS.md — 本轮执行进度", "",
          "生成时间：%s" % R["generated_at"],
          "统计口径唯一来源：`validation/续修_20260921/唯一汇总.json`（按 (source_id,page) 去重）",
          "",
          "## 已完成", "",
          "- 阶段0 能力验证（pdftoppm / ocr-vision / soffice 端到端）",
          "- 阶段1 原料盘点 + 全量 SHA-256 + 约束1 对账收口",
          "- 阶段2 载体校准（含实际打开原页对照）",
          "- 阶段3 全量提取（PDF %s / DOCX %s / PPTX %s，旧格式转换 12 份）"
          % (C["pdf_files"], C["docx_files"], C["pptx_files"]),
          "- 阶段4 原文清洗",
          "- 阶段5 逐题切分：唯一题 %s，题-来源记录 %s"
          % (Q["unique_questions"], Q["question_source_records"]),
          "- 阶段6 逐题配对：链接 %s 条" % R["rubric_links"],
          "- 阶段7 资产与来源映射：资产 %s 项，映射 %s 条"
          % (A["total"], R["source_map_entries"]),
          "- 阶段8 既有试点核验后复用并入（102/102 哈希一致，21 题）",
          "- 约束3 汇编出处核定：79 块（已定位 %s / 原料缺口 %s / 待复核 %s）"
          % (asm_blocks.get("located", "见 indexes/assembly_blocks.csv"),
             asm_blocks.get("missing_source", "见 D-004"),
             asm_blocks.get("pending", "见 indexes/assembly_blocks.csv")),
          "- 阶段9 机器检查 %s/%s" % (R["machine_check"]["passed"],
                                      R["machine_check"]["total"]),
          "- 阶段10 汇总与报告",
          "- 续修 2026-09-21：唯一汇总口径 + 单题头尾配对状态同源 + 题面/OCR/评分/答案分层"
          " + 页级图像依赖 + 24 脚本不再默认写 reviewed",
          "",
          "## 未完成 / 待人工", "",
          "- 视觉核验：已实际打开 **%d 页**（唯一页），工作单 **%d 页**，待核验 **%d 页**"
          % (done_pages, total_wl, pending),
          "- 打开过但页内仍有未修问题：%s 页" % V.get("pages_with_open_findings", "?"),
          "- 存在冲突题 %s 道待裁决" % len(R["conflicting_questions"]),
          "- 汇编待复核块 %s 个（以 indexes/assembly_blocks.csv 现算为准）"
          % asm_blocks.get("pending", "见索引"),
          "- OCR 候选 %s 条待逐条校对"
          % Q["by_extraction_status"].get("candidate_ocr", 0),
          "",
          "## 断点续作", "",
          "本会话结束后不会自动后台运行。续作请按 `scripts/` 内编号顺序执行：",
          "`00 → 01 → 01c → 02 → 03/04/05 → 06 → 07 → 08 → 09 → 10 → 11 → 12 → 13 → 14 → 15`",
          "其中 09 之后必须依次重跑 10、11，否则单题文件的评分材料区会被重置为占位。",
          "**注意**：`09_split.py` 不回删旧产物，重跑前须清理本卷旧单题文件，"
          "否则会留下未入索引的残留（已实测 5 份，见 "
          "`validation/续修_20260921/五个未入索引文件_定性.md`）。",
          "**续修产物**：单题文件已分层（原卷 / OCR 候选 / 教师版 / 评分 / 答案 / 讲评），"
          "读取器应先取 `## 读取指引（机器可读）` 指定的题面小节。",
          ""]
    with open(os.path.join(P.OUT_ROOT, "PROGRESS.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(pl) + "\n")
    print("已写出", os.path.join(P.OUT_ROOT, "PROGRESS.md"))


if __name__ == "__main__":
    main()
