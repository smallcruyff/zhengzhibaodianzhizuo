# BJ-2026-CY-YIMO（2026北京朝阳高三一模·政治）当前共享来源入口

卷身份：2026北京朝阳高三一模 政治（2026.4，考试时间90分钟，满分100分）。共21个唯一父题（Q1–Q21），22个计分项（15道选择题各3分=45分；Q16（8分）、Q17（分两小问：Q17.1=7分+Q17.2=8分，合计15分，单父稿不拆分文件）、Q18（8分）、Q19（8分）、Q20（8分）、Q21（8分）=55分），总分100分。

本README主体源自 claude_bank_20260922 r1/r2 的题源转写与独立复核记录。2026-09-24 主控依据 G7 r2 最终独立复核，已按题将 Q16–Q21 的 Word 原生可读细则页图合入共享题库；本次更新细则渲染依据与导航，不改动原件，也不代表整卷重新验收。

## 原件清单与页数

- 原卷：[`sources/试卷.pdf`](sources/试卷.pdf)，13页，SHA-256 `585b15124610aff7afffd93a3c4753f4b89eb9cd2dc1060a17022cecb4d8a8d9`。第1–4页：选择题Q1–Q15；第5–8页：非选择题Q16–Q21；第9页：参考答案（选择题答案表）；第9–13页：Q16–Q21参考答案与详解（同一PDF内嵌，非独立答案文件）。
- 评分材料：[`sources/细则.docx`](sources/细则.docx)，标题《高三思想政治主观题阅卷细则》，7页可读渲染，SHA-256 `3a11db4bade216d1f174fab8e1b27f29e9b12e1a6b309296103b20e7c67c230d`。原生内容从Q16起（Q1–Q15为选择题，本细则不含选择题评分材料）。Q16对应细则第1页；Q17对应第2–3页；Q18对应第4页；Q19对应第5页；Q20对应第6页；Q21对应第7页。
- 来源限制（按conversion_manifest.json记录）：无独立参考答案文件；无学生答卷、学生原答、涂改/圈划、教师批注、评分标记或实得分文件。学生层全部21题记为`N/A_with_basis`。

## 证据分层

- **E0 原卷**：`sources/试卷.pdf` 第1–8页原文，各题MD“原题（E0：原卷）”节。
- **E3 参考答案**：`sources/试卷.pdf` 第9页选择题答案表（Q1–Q15）与第9–13页Q16–Q21【答案】【详解】，属同一PDF内嵌参考答案，不提升为E1。
- **E1 正式评分细则**：`sources/细则.docx` 原生段落，仅覆盖Q16–Q21（Q17拆两小问共7个计分项）；Q1–Q15为选择题，`rubric_status: not_applicable_choice`，不得把主观题细则误配到选择题。
- **细则可读渲染**：原始 `sources/细则.docx` 保持不变。旧 `assets/rubric_pages/rubric-01.png` 至 `rubric-07.png` 为LibreOffice缺字历史渲染，保留但不作为当前视觉证据。现新增 `sources/readable_word_native_20260924/细则.pdf`，由 Microsoft Word 对该DOCX原生导出，共7页，SHA256 `547fe780fa2b2bb98fba3dba12d59beef522018bfa0a43df8d00e6d62ea77499`；200dpi页图位于 `assets/rubric_pages/word_native_20260924/`，逐页对应：p1→Q16，p2–3→Q17，p4→Q18，p5→Q19，p6→Q20，p7→Q21。Q21页红色“22.”按本卷 `word/numbering.xml` 核验属于Q21评分列表第二项，不是缺失的Q22；其内容已在Q21 E1段落转写。
- **学生层**：`N/A_with_basis`，本卷输入目录未提供学生答卷/批注/实得分文件。

## 题目导航

- [Q1](BJ-2026-CY-YIMO-Q1.md) [Q2](BJ-2026-CY-YIMO-Q2.md) [Q3](BJ-2026-CY-YIMO-Q3.md) [Q4](BJ-2026-CY-YIMO-Q4.md) [Q5](BJ-2026-CY-YIMO-Q5.md)
- [Q6](BJ-2026-CY-YIMO-Q6.md) [Q7](BJ-2026-CY-YIMO-Q7.md) [Q8](BJ-2026-CY-YIMO-Q8.md) [Q9](BJ-2026-CY-YIMO-Q9.md) [Q10](BJ-2026-CY-YIMO-Q10.md)
- [Q11](BJ-2026-CY-YIMO-Q11.md) [Q12](BJ-2026-CY-YIMO-Q12.md) [Q13](BJ-2026-CY-YIMO-Q13.md) [Q14](BJ-2026-CY-YIMO-Q14.md) [Q15](BJ-2026-CY-YIMO-Q15.md)
- [Q16](BJ-2026-CY-YIMO-Q16.md)（哲学与文化，8分） [Q17](BJ-2026-CY-YIMO-Q17.md)（逻辑与思维+政治与法治，7+8=15分） [Q18](BJ-2026-CY-YIMO-Q18.md)（法律与生活，8分）
- [Q19](BJ-2026-CY-YIMO-Q19.md)（经济与社会，8分） [Q20](BJ-2026-CY-YIMO-Q20.md)（当代国际政治与经济，8分） [Q21](BJ-2026-CY-YIMO-Q21.md)（政治与法治综合，8分）

## 来源导航

- 原卷页图：[p1](assets/source_pages/paper-01.png) [p2](assets/source_pages/paper-02.png) [p3](assets/source_pages/paper-03.png) [p4](assets/source_pages/paper-04.png) [p5](assets/source_pages/paper-05.png) [p6](assets/source_pages/paper-06.png) [p7](assets/source_pages/paper-07.png) [p8](assets/source_pages/paper-08.png) [p9 答案](assets/source_pages/paper-09.png) [p10](assets/source_pages/paper-10.png) [p11](assets/source_pages/paper-11.png) [p12](assets/source_pages/paper-12.png) [p13](assets/source_pages/paper-13.png)
- 细则当前可读渲染页：[Word原生p1](assets/rubric_pages/word_native_20260924/rubric-01.png) [Word原生p2](assets/rubric_pages/word_native_20260924/rubric-02.png) [Word原生p3](assets/rubric_pages/word_native_20260924/rubric-03.png) [Word原生p4](assets/rubric_pages/word_native_20260924/rubric-04.png) [Word原生p5](assets/rubric_pages/word_native_20260924/rubric-05.png) [Word原生p6](assets/rubric_pages/word_native_20260924/rubric-06.png) [Word原生p7](assets/rubric_pages/word_native_20260924/rubric-07.png)。旧LibreOffice缺字页图仍保留于 `assets/rubric_pages/rubric-01.png` 至 `rubric-07.png`，仅作历史派生。
- 原生文字提取：[原卷 native](evidence/extracts/paper_native_by_page.md) · [细则 native](evidence/extracts/rubric_docx_native.md)

## 已知非本卷范围的相邻文件

- `BJ-2026-CY-YIMO-Q25.md`：经比对，其内容是Q13同一段材料/选项的OCR候选重复件（编号错位为“25.1”，OCR来源角色标注为`ocr_candidate`，非独立第22题或第25题）。本轮判断为应删除的重复/垃圾文件，已列入本轮`findings.json`的`proposed_removals`，本轮不做删除，留待主控裁决。

现有来源转换已于 2026-09-23T01:30:06.122838+00:00 由主控 claude:13295440-b4bb-4013-b7bd-0daa95ed1858 按 approval plan `claude-accept3b-20260922` 验收；源边界、页数和缺源说明见逐卷不可变验收回执。
