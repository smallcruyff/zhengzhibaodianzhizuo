# BJ-2024-HD-ERMO 卷说明

## 1. 卷身份

- exam_id：`BJ-2024-HD-ERMO`
- 原卷标题（原卷 PDF/DOCX 页首原文）：“海淀区2023—2024学年第二学期期末练习　高三思想政治　2024.5”
- 年份/地区/阶段（`conversion_manifest.json`）：2024年 / 海淀区 / 二模（期末练习）
- 卷面结构：第一部分 15 道选择题（每题 3 分，共 45 分）+ 第二部分 6 道非选择题（共 55 分），满分 100 分，考试时长 90 分钟
- 题目：Q1–Q21，共 21 题（选择题 Q1–Q15，非选择题 Q16–Q21）
- 制作/复核状态（以 `conversion_manifest.json` 当前记录为准，本 README 不代为升级）：`status=待复核`、`transcription_status=已转写`、`acceptance_status=待复核`；`full_acceptance_suspended_reason` 记录的旧 DOCX 缺字视觉问题已由 `sources/readable_visual_20260922/` 的可读派生页替代解决，但整卷验收仍以主控/复核链路的最新回执为准，本 README 不改变验收结论。

## 2. 原件清单与页数

| 角色 | 原件路径（相对 `/Users/wanglifei/Desktop/`） | 格式 | 原生页数 | 渲染/可读页数 | source_id |
| --- | --- | --- | --- | --- | --- |
| 原卷（权威采用层） | `2024模拟题/海淀二模/试卷/试卷.pdf` | PDF | 8 页 | 8 页（`sources/authority_pdf/2024-HD-ERMO-试卷.pdf`） | `S5355283f436e` |
| 原卷（DOCX，source-specific 审计层） | `2024模拟题/海淀二模/试卷/补充材料/高三二模：政治试题（以PDF为准）(1).docx` | DOCX | 无固定页码 | 9 页可读派生页 | `S13d454fdd813` |
| 评分材料（正式细则，E1） | `2024模拟题/海淀二模/细则/细则.docx` | DOCX | 无固定页码 | 5 页可读派生页 | `S227192d22e10` |
| 独立参考答案（E3） | `2024模拟题/海淀二模/细则/补充材料/高三二模：政治答案(2).docx` | DOCX | 无固定页码 | 2 页可读派生页 | `S8f109fb09efc` |
| 学生样卷/教师批注 | 未提供 | — | — | — | `N/A_with_basis`（原件未见独立学生样卷或批注扫描件） |

4 份原件、共 8 + 9 + 5 + 2 = 24 个原生/派生页已逐页打开核对（PDF 8 页见 `sources/authority_pdf/`；DOCX 16 页可读派生页见 `sources/readable_visual/rendered/`）。

## 3. 证据分层

- **原卷 PDF（权威采用层）**：Q1–Q21 的“题目原文”均以 PDF 原生文字层为准；PDF 与 DOCX 出现异文时（见第 6 节），采用层保留 PDF 文字，DOCX 差异仅作 source-specific 审计记录，不覆盖采用层。
- **原卷 DOCX（`S13d454fdd813`，source-specific 审计层）**：完整原生块转写见 [S13 完整原生块](sources/transcripts/S13d454fdd813_full_native.md)；Q13/Q14 的段落级差分另在题级 MD 内以“Source-specific DOCX native 题面层”小节保留（`P086`/`P090`），Q11/Q18/Q21 的缺口段落已通过已核定的内容差分并入题级 MD（民法典第二百七十四条法条框、Q18 材料一/二、Q21 热词侧栏与答题技法图示）。
- **评分材料 DOCX（`S227192d22e10`，E1 正式评分细则）**：完整原生块转写见 [S227 完整原生块](sources/transcripts/S227192d22e10_full_native.md)。Q16、Q19、Q20、Q21 的评分细则原为浮动嵌入表格图片（`word/media/image1.png`–`image4.png`，Q21 另有技法图示 `image5.png`），均已转写为正文 Markdown 表格并保留红字“替代”标注；Q17 的时间安排表与三维度（科学思维/创新思维/辩证思维）细则表为原生 Word 表格，直接转写。Q1–Q15（选择题）未见逐题正式评分细则；本文件前置段落另有一份与 E3 相同的 15 题答案键（见第 6 节），不构成逐题 E1 细则。
- **独立参考答案 DOCX（`S8f109fb09efc`，E3，非正式评分细则）**：完整原生块转写见 [S8 完整原生块](sources/transcripts/S8f109fb09efc_full_native.md)。角色裁定见 [S8 角色证据](sources/reference_answer_role.md)：Q1–Q15 提供单一答案键字母，Q16–Q21 提供参考答案方向文字，并附两张与 S227 相同的通用四级等级表（[通用等级表转写](sources/transcripts/generic_level_tables.md)）；该等级表不建立逐题评分槽、不设固定分值/替代/封顶，不得升级为 E1。
- **学生样卷/教师批注**：原件未提供独立学生作答扫描件或教师批注、实得分记录；本卷该层记 `N/A_with_basis`，依据为 `conversion_manifest.json` 与 `sources/coverage/` 内历史回执均未记录任何学生层来源文件。
- 三份来源角色的边界总述见 [来源角色边界](sources/role_boundaries.md)；图表/表格与原卷框线的对应关系见 [图示与表格拓扑](sources/diagram_topology.md)。

## 4. 卷首与分部说明（原文，闭合覆盖缺口）

原卷 PDF 第 1 页页首（`assets/pages/p001.png`）：

> 海淀区2023—2024学年第二学期期末练习
> 高三思想政治　　　　　　　　　　　　2024.05
> 本试卷共8页，100分。考试时长90分钟。考生务必将答案答在**答题卡**上，在试卷上作答无效。考试结束后，将本试卷和**答题卡**一并交回。
>
> 第一部分
> 本部分共15题，每题3分，共45分。在每题列出的四个选项中，选出最符合题目要求的一项。

原卷 PDF 第 5 页页首（`assets/pages/p005.png`，Q16 之前）：

> 第二部分
> 本部分共6题，共55分。

来源差分（审计记录，不改变采用层）：原卷 DOCX `S13d454fdd813` P002 对应段落写作“考生务必将答案答在**答题纸**上……将本试卷和**答题纸**一并交回”，与 PDF 的“答题卡”不同；采用层保留 PDF 文字“答题卡”，DOCX“答题纸”仅作差分记录（同类差分处理方式见第 6 节 Q13/Q14）。独立参考答案 DOCX `S8f109fb09efc` P000–P003 与评分材料 DOCX `S227192d22e10` P000–P002 均各自重复了一遍与上方相同的卷头（标题/日期）与分部说明文字，且 `S227192d22e10` 的 P002 还额外重复了一份与 E3 完全相同的 15 题答案键字母串（`1．C 2．D 3．C 4．B 5．A 6．C 7．D 8．B 9．D 10．B 11．A 12．B 13．A 14．C 15．D`，见 [S227 完整原生块](sources/transcripts/S227192d22e10_full_native.md) P000–P002）；三处内容与本节已转写文字一致，此处合并记录以闭合“全部段落须进入题MD或README”的覆盖要求，不再逐题重复。另：`S227192d22e10`（细则.docx）P000 原文写作“海淀区2023-2024学年第二学期期末练习高三思想政治**参考答案**　　2024.5”，标题字样与该文件本身角色（评分材料/细则）不符，疑为原件编辑时从答案文档复制标题所致；原文如此，不改写，仅在此说明。

## 5. 题级导航

| 题号 | 题型 | 分值 | 选择题答案键（E3，非评分依据） | 评分材料状态 | 链接 |
| --- | --- | --- | --- | --- | --- |
| Q1 | 选择题 | 3分 | C | 未见本题正式评分细则 | [BJ-2024-HD-ERMO-Q1.md](BJ-2024-HD-ERMO-Q1.md) |
| Q2 | 选择题 | 3分 | D | 未见本题正式评分细则 | [BJ-2024-HD-ERMO-Q2.md](BJ-2024-HD-ERMO-Q2.md) |
| Q3 | 选择题 | 3分 | C | 未见本题正式评分细则 | [BJ-2024-HD-ERMO-Q3.md](BJ-2024-HD-ERMO-Q3.md) |
| Q4 | 选择题 | 3分 | B | 未见本题正式评分细则 | [BJ-2024-HD-ERMO-Q4.md](BJ-2024-HD-ERMO-Q4.md) |
| Q5 | 选择题 | 3分 | A | 未见本题正式评分细则 | [BJ-2024-HD-ERMO-Q5.md](BJ-2024-HD-ERMO-Q5.md) |
| Q6 | 选择题 | 3分 | C | 未见本题正式评分细则 | [BJ-2024-HD-ERMO-Q6.md](BJ-2024-HD-ERMO-Q6.md) |
| Q7 | 选择题 | 3分 | D | 未见本题正式评分细则 | [BJ-2024-HD-ERMO-Q7.md](BJ-2024-HD-ERMO-Q7.md) |
| Q8 | 选择题 | 3分 | B | 未见本题正式评分细则 | [BJ-2024-HD-ERMO-Q8.md](BJ-2024-HD-ERMO-Q8.md) |
| Q9 | 选择题 | 3分 | D | 未见本题正式评分细则 | [BJ-2024-HD-ERMO-Q9.md](BJ-2024-HD-ERMO-Q9.md) |
| Q10 | 选择题 | 3分 | B | 未见本题正式评分细则 | [BJ-2024-HD-ERMO-Q10.md](BJ-2024-HD-ERMO-Q10.md) |
| Q11 | 选择题 | 3分 | A | 未见本题正式评分细则 | [BJ-2024-HD-ERMO-Q11.md](BJ-2024-HD-ERMO-Q11.md) |
| Q12 | 选择题 | 3分 | B | 未见本题正式评分细则 | [BJ-2024-HD-ERMO-Q12.md](BJ-2024-HD-ERMO-Q12.md) |
| Q13 | 选择题 | 3分 | A | 未见本题正式评分细则 | [BJ-2024-HD-ERMO-Q13.md](BJ-2024-HD-ERMO-Q13.md) |
| Q14 | 选择题 | 3分 | C | 未见本题正式评分细则 | [BJ-2024-HD-ERMO-Q14.md](BJ-2024-HD-ERMO-Q14.md) |
| Q15 | 选择题 | 3分 | D | 未见本题正式评分细则 | [BJ-2024-HD-ERMO-Q15.md](BJ-2024-HD-ERMO-Q15.md) |
| Q16 | 非选择题 | 6分 | — | 已匹配正式评分材料 | [BJ-2024-HD-ERMO-Q16.md](BJ-2024-HD-ERMO-Q16.md) |
| Q17 | 非选择题 | 11分（(1)7分+(2)4分） | — | 已匹配正式评分材料 | [BJ-2024-HD-ERMO-Q17.md](BJ-2024-HD-ERMO-Q17.md) |
| Q18 | 非选择题 | 16分（(1)8分+(2)8分） | — | 已匹配正式评分材料 | [BJ-2024-HD-ERMO-Q18.md](BJ-2024-HD-ERMO-Q18.md) |
| Q19 | 非选择题 | 6分 | — | 已匹配正式评分材料 | [BJ-2024-HD-ERMO-Q19.md](BJ-2024-HD-ERMO-Q19.md) |
| Q20 | 非选择题 | 8分 | — | 已匹配正式评分材料 | [BJ-2024-HD-ERMO-Q20.md](BJ-2024-HD-ERMO-Q20.md) |
| Q21 | 非选择题 | 8分 | — | 已匹配正式评分材料 | [BJ-2024-HD-ERMO-Q21.md](BJ-2024-HD-ERMO-Q21.md) |

选择题答案键均来自 E3 独立参考答案（`S8f109fb09efc`），与 `S227192d22e10` 前置段落的同一份答案键字母串一致（见第 4 节），仅作参考，不构成逐题评分依据。

## 6. 图片/图表结构化转写索引（图的硬标准落点）

| 位置 | 图像类型 | 结构化转写落点 |
| --- | --- | --- |
| Q2 建筑照片（PDF 内嵌 237×139 + DOCX 内嵌 715×420 并存） | 纪实照片 | [BJ-2024-HD-ERMO-Q2.md](BJ-2024-HD-ERMO-Q2.md) “图片结构化转写”小节：主体、斗拱、瓦作、鸟形剪影、背景、无文字均已列出 |
| Q9 民商事判决互认安排原框（PDF p003） | 法条文本框 | [BJ-2024-HD-ERMO-Q9.md](BJ-2024-HD-ERMO-Q9.md)：条款全文已转写为表格+“图表/框线关系注记” |
| Q11 民法典第二百七十四条法条框（PDF p003） | 法条文本框 | [BJ-2024-HD-ERMO-Q11.md](BJ-2024-HD-ERMO-Q11.md)：法条全文已转写，DOCX 重复串接另作 source-specific 记录 |
| Q13/Q14 DOCX 派生页 5（`assets/docx_pages/page-005.png`） | 文档整页渲染（非数据图） | [BJ-2024-HD-ERMO-Q13.md](BJ-2024-HD-ERMO-Q13.md)、[BJ-2024-HD-ERMO-Q14.md](BJ-2024-HD-ERMO-Q14.md)：页内印刷文字已按 `P086`/`P090` 原始块逐字转写，并记录与 PDF 权威层的“物流/五六包装”“17种/7种”两处异文 |
| Q16 可能性/必要性/重要性评分表（原为 `image1.png` 浮动图） | 评分细则表格 | [BJ-2024-HD-ERMO-Q16.md](BJ-2024-HD-ERMO-Q16.md)：已转写为 Markdown 表格，含“替代”标注与合并单元格说明 |
| Q17 时间安排表 + 三维度细则表（原生 Word 表格） | 表格 | [BJ-2024-HD-ERMO-Q17.md](BJ-2024-HD-ERMO-Q17.md)：均为 Markdown 表格 |
| Q18 逻辑角度/细则内容表（原为 `image2.png` 浮动图） | 评分细则表格 | [BJ-2024-HD-ERMO-Q18.md](BJ-2024-HD-ERMO-Q18.md)：已转写为 Markdown 表格 |
| Q19 判决内容/社会价值表（原为 `image3.png` 浮动图） | 评分细则表格 | [BJ-2024-HD-ERMO-Q19.md](BJ-2024-HD-ERMO-Q19.md)：已转写为 Markdown 表格，红字“替代”以 `<span style="color:red">` 保留颜色语义 |
| Q20 因素/内容表（PDF p007，原生表格）+ 角度/细则分值表（原为 `image4.png` 浮动图） | 材料表格 + 评分细则表格 | [BJ-2024-HD-ERMO-Q20.md](BJ-2024-HD-ERMO-Q20.md)：均已转写为 Markdown 表格，含红字分值批注差分记录 |
| Q21 政府工作报告“新”热词侧栏（PDF p008 绿框）+ 答题技法图示（原为 `image5.png`，S227 第 5 页） | 侧栏文本框 + 教学示意图 | [BJ-2024-HD-ERMO-Q21.md](BJ-2024-HD-ERMO-Q21.md)：热词侧栏全文转写；技法图示（黄色高亮词、手绘气泡、红字口诀、第三个空白标注框及指示线锚点）已逐要素转写，标明“讲评/教学提示，非评分依据”，不新增采分点 |

未在上表出现的题目（Q1、Q3–Q8、Q10、Q12、Q15）在原件中只有纯印刷题干与选项，无独立图像对象，其页面图（`assets/pages/pXXX.png`）仅作文字层核对并存，不含需要单独结构化转写的图表内容。

## 7. 来源导航（具体文件）

- [原卷 PDF（权威采用层）](sources/authority_pdf/2024-HD-ERMO-试卷.pdf)
- [原卷 DOCX 原件复制件 S13](sources/source_copies/S13d454fdd813_source.docx) / [S13 完整原生块转写](sources/transcripts/S13d454fdd813_full_native.md) / [S13 完整 OOXML](sources/ooxml/S13d454fdd813.json) / [S13 页序映射](sources/mapping/S13d454fdd813.json) / [S13 Q13/Q14 原始块专项转写](sources/native_blocks/S13d454fdd813_P086_P090_native.md)
- [评分材料 DOCX 原件复制件 S227](sources/source_copies/S227192d22e10_source.docx) / [S227 完整原生块转写](sources/transcripts/S227192d22e10_full_native.md) / [S227 完整 OOXML](sources/ooxml/S227192d22e10.json) / [S227 页序映射](sources/mapping/S227192d22e10.json)
- [独立参考答案 DOCX 原件复制件 S8](sources/source_copies/S8f109fb09efc_source.docx) / [S8 完整原生块转写](sources/transcripts/S8f109fb09efc_full_native.md) / [S8 完整 OOXML](sources/ooxml/S8f109fb09efc.json) / [S8 页序映射](sources/mapping/S8f109fb09efc.json) / [S8 角色证据](sources/reference_answer_role.md)
- [通用等级表转写（S8/S227 共用）](sources/transcripts/generic_level_tables.md)
- [来源角色边界总述](sources/role_boundaries.md)
- [机器可读角色记录](sources/source_roles.json)
- [图示与表格拓扑说明](sources/diagram_topology.md)
- [可读派生页导航](sources/readable_pages.md)
- [完整来源索引（含全部导航链接）](sources/full_source_index.md)

资产目录 `assets/`（页面图、DOCX 派生页、嵌入图）与历史核对回执目录 `sources/coverage/`（`accepted_*`、`gap_table.json`、`full_gap.json`、`sha256_checklist_*.json` 等只读留存文件）均在题级 MD 与本节链接中被逐一引用；未被引用的原始抽取文件仅作历史存档，不构成独立证据层。

## 8. 已知边界与差分（不改变采用层，仅供追溯）

- 原卷 PDF 第 1 页 OCR 候选层（部分题目保留）存在真实识别错字与断行，回原页对照前不得直接采用；采用层始终以“题目原文（原卷·native/PDF权威）”小节为准。
- Q13：PDF p004 权威文字“制定物流包装标准和服务标准”与 DOCX `P086` 原文“制定五六包装标准和服务标准”不同，采用 PDF。
- Q14：PDF p004 权威文字“其中包括17种战略原材料”与 DOCX `P090` 原文“其中包括7种战略原材料”不同，采用 PDF。
- 卷首说明：PDF“答题卡”与 DOCX“答题纸”不同，采用 PDF（见第 4 节）。
- Q20：材料表格中“近5年来……中部地区发展站到了更高起点上”一句在来源中出现重复措辞，已在 Q20 题级 MD 中原样记录，`affects_answering: false`。
- 学生作答/教师批注/实得分：原件未提供，记 `N/A_with_basis`，不补造。

现有来源转换已于 2026-09-23T01:30:06.122838+00:00 由主控 claude:13295440-b4bb-4013-b7bd-0daa95ed1858 按 approval plan `claude-accept3b-20260922` 验收；源边界、页数和缺源说明见逐卷不可变验收回执。
