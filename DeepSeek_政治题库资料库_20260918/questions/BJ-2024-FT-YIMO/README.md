# BJ-2024-FT-YIMO 卷说明

## 卷身份

- exam_id：`BJ-2024-FT-YIMO`
- 年份/地区/阶段：2024年 · 北京市丰台区 · 高三第二学期综合练习（一）（即"丰台一模"）
- 科目：思想政治；满分100分，考试时长90分钟；共21题（选择题15题共45分，非选择题6题共55分）
- 转换/验收状态：以本卷 `shared_conversion_state.json` 与总清单 `后勤管理/MD全库流水线_20260921/conversion_manifest.json` 中 `exam_id=BJ-2024-FT-YIMO` 条目为准；不在本文件重复标注整卷验收结论。

## 原件清单与页数

| 角色 | 文件 | source_id | 页数/规模 | SHA-256 |
|---|---|---|---|---|
| 原卷（E0，题面来源） | `assets/sources/试卷.pdf` | S4800d0b858f | 8页 | `4800d0b858f0ede60439e12a5beb3bc2fc32754fa602054f5f6fd74ce4bb6bc4` |
| 参考答案（E3，非正式评分细则） | `assets/sources/2024北京丰台高三一模政治试题及答案.pdf` | S5f5486bfc3ba | 9页 | `5f5486bfc3baab2bc1a8e43b06b8aac6377e1402d4402e5d0bb90ad292755521` |
| 评分细则（E1，正式评分材料） | `assets/sources/细则.docx` | S950d6b2d3cdd | 1个DOCX，非空原生段落121个（编号P0–P131，其余编号为文档中的空段落，提取时已跳过）+1个表格 | `950d6b2d3cdda441625d9b2a0c2329d7ae34212d804c3fe005a66b23fb369a49` |

原卷PDF原生文字层仅第1页非空（891字符），第2–8页文字层为空，故第2–8页均以整页PNG视觉核校为准；参考答案PDF与评分细则DOCX的原生文字层完整可用。评分细则DOCX因中文字体缺字，另有 `sources/readable_visual_20260922/`（LibreOffice私有字体渲染的9页可读派生PDF/页图，字体问题已修复，OOXML段落锚点P001–P131与原生XML一一对应），仅作可读版式佐证，正式文字仍以DOCX原生XML段落为准。

## 证据分层

- **E0 原卷题面**：题号、材料、选项、设问、分值以原卷PDF文字/视觉为准；每题MD"原卷题面（视觉核校转写）"节即为该层。
- **E3 参考答案（非正式评分细则）**：来自 `2024北京丰台高三一模政治试题及答案.pdf`；每题MD"参考答案（E3，不是正式评分细则）"节；选择题客观答案见该PDF第8页答案表，按题拆分登记。
- **E1 正式评分材料**：来自 `细则.docx`（标题"丰台一模评分细则 2024.3.30"）；仅覆盖Q16–Q21六道非选择题（Q1–Q15为客观题，未在提供的DOCX中找到题级正式细则，各题MD已如实标注 `not_located_in_provided_scoring_source`，不代为编造）；每题MD"正式评分材料（E1）"节，含DOCX原生段落引用（`[DOCX Pn]`格式）与表格（Q18、Q21各含一个等级水平表，已转为真正的Markdown表格，原PDF/DOCX交错文本层另存于`<details>`折叠块供追溯）。
- **来源分层裁决**：E3与E1字面不一致处（如Q17"根据/依据""公平/平等"、Q19"食品/视频"字面辨认、Q20"意向/意象"、Q21等级档位6-7分/7-8分冲突）在对应题MD设"来源分层裁决"或"源间差异与冲突"节，两层原文并列保留，不静默改写、不升级证据等级；结论索引见 `sources/source_layer_differences.md` 与 `sources/evidence/adjudicate_2024_ft_yimo_conflicts.json`（如存在）。
- **学生样卷/教师批注/实得分**：本卷源集不含学生答题卡、教师批注样卷或逐份实得分记录；各题MD"学生示例、教师批注与实得分"节按 `N/A_with_basis` 如实登记，不补造。
- **讲评材料**：本卷评分材料为DOCX文本细则，未见PPT形式的"试题分析/讲解示例/学生问题"等讲评页；如后续发现此类材料，按规则补入对应题MD并标注"讲评，非评分依据"。

## 图像与图示说明

本卷无统计图表（无坐标轴/图例类图形）。含结构化图示的题目：Q9（漫画）、Q16/Q17（并列信息卡/资料卡）、Q18（三栏措施卡）、Q19（三段对话框+人物头像）、Q20（虚线项目符号材料框）、Q21（引文卡）。每题MD均有"图示拓扑与图中文字"或"视觉结构核验"节，转写图题/框线/图例式装饰、箭头或连线方向（含"无连线/无箭头"的明确说明）、图中全部文字；放大裁图见各题目录下 `assets/Q*_original_*.png` 及 `assets/review_crops/`。

## 题级导航

选择题（Q1–Q15，各3分）：
[Q1](BJ-2024-FT-YIMO-Q1.md) · [Q2](BJ-2024-FT-YIMO-Q2.md) · [Q3](BJ-2024-FT-YIMO-Q3.md) · [Q4](BJ-2024-FT-YIMO-Q4.md) · [Q5](BJ-2024-FT-YIMO-Q5.md) · [Q6](BJ-2024-FT-YIMO-Q6.md) · [Q7](BJ-2024-FT-YIMO-Q7.md) · [Q8](BJ-2024-FT-YIMO-Q8.md) · [Q9](BJ-2024-FT-YIMO-Q9.md)（漫画） · [Q10](BJ-2024-FT-YIMO-Q10.md) · [Q11](BJ-2024-FT-YIMO-Q11.md) · [Q12](BJ-2024-FT-YIMO-Q12.md) · [Q13](BJ-2024-FT-YIMO-Q13.md) · [Q14](BJ-2024-FT-YIMO-Q14.md) · [Q15](BJ-2024-FT-YIMO-Q15.md)

非选择题（Q16–Q21，共55分）：
[Q16](BJ-2024-FT-YIMO-Q16.md)（8分，三卡） · [Q17](BJ-2024-FT-YIMO-Q17.md)（8分，法条卡+资料卡） · [Q18](BJ-2024-FT-YIMO-Q18.md)（16分，两小问，三栏措施卡） · [Q19](BJ-2024-FT-YIMO-Q19.md)（8分，两小问，三段对话框） · [Q20](BJ-2024-FT-YIMO-Q20.md)（7分，项目符号材料框） · [Q21](BJ-2024-FT-YIMO-Q21.md)（8分，两张引文卡）

## 来源导航

- 逐页原图：`assets/original_p001.png`–`assets/original_p008.png`（原卷8页）、`assets/answer_p001.png`–`assets/answer_p009.png`（参考答案9页）、`assets/scoring_p001.png`–`assets/scoring_p004.png`（评分DOCX旧渲染4页，中文缺字，仅历史存档）。
- 重点题目裁图：`assets/Q09_original_figure.png`、`assets/Q16_original_cards.png`、`assets/Q17_original_cards.png`、`assets/Q18_original_material2.png`、`assets/Q19_original_dialogue.png`、`assets/Q20_original_box.png`、`assets/Q21_original_callouts.png`；补充放大证据在 `assets/review_crops/`。
- 原件字节副本：`assets/sources/试卷.pdf`、`assets/sources/2024北京丰台高三一模政治试题及答案.pdf`、`assets/sources/细则.docx`（另有 `assets/sources/细则_rendered_by_libreoffice.pdf` 为旧渲染，缺字仅存历史）。
- 原生文字层：`assets/raw_extraction/`（原卷/答案PDF文字层、评分DOCX段落与表格原始提取）。
- 整卷完整转写（逐页/逐段，供交叉核对，不替代题级MD为一手正文）：`sources/transcriptions/original_paper_full.md`（原卷p1–p8逐页转写，含全部图示拓扑细节）、`sources/transcriptions/reference_answer_full.md`（参考答案PDF全文）、`sources/transcriptions/scoring_native_full.md`、`sources/transcriptions/scoring_docx_native_paragraphs.txt`、`sources/transcriptions/scoring_docx_native_table_0.txt`。
- 中文可读来源页（细则DOCX字体修复渲染）：[sources/readable_visual_20260922/README.md](sources/readable_visual_20260922/README.md)，含派生PDF与9页页图、原件身份与页码映射。
- 来源差异登记：[sources/source_layer_differences.md](sources/source_layer_differences.md)。
- 来源索引与机器化覆盖记录：`sources/index.json`、`sources/evidence/index.json`、`sources/evidence/42_full.json`（页题映射/coverage）、`sources/evidence/40_gap_report.json`、`sources/evidence/41_review.json`（历史独立复核记录）。

## 修订记录（本README相关）

- c1轮（claude_bank_20260922，2026-09-22）：本README此前仅是指向 `sources/readable_visual_20260922/` 的一句话入口，未含卷身份、原件页数、证据分层、题级/来源导航，本轮按主控要求改写为完整卷说明；同轮同时补齐Q1原卷卷首/第一部分说明文字（此前只存在于sources/转写，未进入任何题级MD）、订正Q20项目符号字形（➢→❖，按原图字形）、并加深Q16/Q17/Q19/Q21的图示结构化转写。

现有来源转换已于 2026-09-23T01:30:06.122838+00:00 由主控 claude:13295440-b4bb-4013-b7bd-0daa95ed1858 按 approval plan `claude-accept3b-20260922` 验收；源边界、页数和缺源说明见逐卷不可变验收回执。

现有来源转换已于 2026-09-24T12:11:41.393803+00:00 由主控 codex:01a0cff1-36ce-77e1-a013-5b10d6c6271c 按 approval plan `codex-retro-batch1-resign-20260924-v1` 验收；源边界、页数和缺源说明见逐卷不可变验收回执。
