# BJ-2025-DC-ERMO 当前共享来源入口

当前21题、100分，沿用已经核验的题稿字节；本轮只补齐来源包与索引，合后验证已完成。题内旧“候选”字样属于形成记录，当前状态以本入口和[共享状态](shared_conversion_state.json)为准。

## AI读取顺序

先读对应完整题稿中的视觉核对题面、E3和E1，再结合[已核视觉字形差异](source_support/transcriptions/visual_variants.md)。原生文字与清洗缓存用于保留原始提取记录；其中已登记的异常字符不能覆盖视觉核对文字。读取器的新标题与完整段落保留修复已通过部署后22项测试；需要全部形成记录时可用 `get --all`。

## 整卷资料

- [来源角色、逐页题号和21题SHA](source_support/source_index.json)
- [卷首与印刷说明](source_support/transcriptions/frontmatter_and_printed_instructions.md)
- [原卷8页全文缓存](source_support/transcriptions/cached_cleaned/main_exam_full.md)
- [正式评分5页全文缓存](source_support/transcriptions/cached_cleaned/formal_scoring_full.md)
- [原卷原生提取](source_support/transcriptions/cached_native/main_exam_raw.txt)及[版面提取](source_support/transcriptions/layout/main_exam_layout.txt)
- [正式评分原生提取](source_support/transcriptions/cached_native/formal_scoring_raw.txt)及[版面提取](source_support/transcriptions/layout/formal_scoring_layout.txt)
- [原卷PDF](source_support/sources/original/main_exam_试卷.pdf)、[正式评分PDF](source_support/sources/original/formal_scoring_细则.pdf)
- [Q3原图与署名](source_support/assets/figures/Q3_painting_caption.png)
- [来源补充独立复核](source_support/review/verification.md)

原卷p7–p8为内嵌E3答案与等级表，正式评分PDF p1–p5为独立E1与汇总阅卷报告。正式材料只含Q16–Q21，不把其中分点编号认成Q1–Q15。未提供个人学生样卷、原答、批注或实得分，也没有独立答案文件；这些是实际来源边界。

## 题目

[Q1](BJ-2025-DC-ERMO-Q1.md)、[Q2](BJ-2025-DC-ERMO-Q2.md)、[Q3](BJ-2025-DC-ERMO-Q3.md)、[Q4](BJ-2025-DC-ERMO-Q4.md)、[Q5](BJ-2025-DC-ERMO-Q5.md)、[Q6](BJ-2025-DC-ERMO-Q6.md)、[Q7](BJ-2025-DC-ERMO-Q7.md)、[Q8](BJ-2025-DC-ERMO-Q8.md)、[Q9](BJ-2025-DC-ERMO-Q9.md)、[Q10](BJ-2025-DC-ERMO-Q10.md)、[Q11](BJ-2025-DC-ERMO-Q11.md)、[Q12](BJ-2025-DC-ERMO-Q12.md)、[Q13](BJ-2025-DC-ERMO-Q13.md)、[Q14](BJ-2025-DC-ERMO-Q14.md)、[Q15](BJ-2025-DC-ERMO-Q15.md)、[Q16](BJ-2025-DC-ERMO-Q16.md)、[Q17](BJ-2025-DC-ERMO-Q17.md)、[Q18](BJ-2025-DC-ERMO-Q18.md)、[Q19](BJ-2025-DC-ERMO-Q19.md)、[Q20](BJ-2025-DC-ERMO-Q20.md)、[Q21](BJ-2025-DC-ERMO-Q21.md)

## 完整页图

- [原卷与内嵌E3 p001](source_support/assets/main_exam_pages/p001.png)
- [原卷与内嵌E3 p002](source_support/assets/main_exam_pages/p002.png)
- [原卷与内嵌E3 p003](source_support/assets/main_exam_pages/p003.png)
- [原卷与内嵌E3 p004](source_support/assets/main_exam_pages/p004.png)
- [原卷与内嵌E3 p005](source_support/assets/main_exam_pages/p005.png)
- [原卷与内嵌E3 p006](source_support/assets/main_exam_pages/p006.png)
- [原卷与内嵌E3 p007](source_support/assets/main_exam_pages/p007.png)
- [原卷与内嵌E3 p008](source_support/assets/main_exam_pages/p008.png)
- [正式评分材料 p001](source_support/assets/formal_scoring_pages/p001.png)
- [正式评分材料 p002](source_support/assets/formal_scoring_pages/p002.png)
- [正式评分材料 p003](source_support/assets/formal_scoring_pages/p003.png)
- [正式评分材料 p004](source_support/assets/formal_scoring_pages/p004.png)
- [正式评分材料 p005](source_support/assets/formal_scoring_pages/p005.png)

现有全部来源的转换已于2026-09-22验收。验收保留真实缺源及源层差异，不提高来源证据等级，也不代表任何宝典书稿的验收。

现有来源转换已于 2026-09-24T10:32:35.593820+00:00 由主控 codex:01a0cff1-36ce-77e1-a013-5b10d6c6271c 按 approval plan `codex-retro-batch2-resign-20260924-v1` 验收；源边界、页数和缺源说明见逐卷不可变验收回执。

现有来源转换已于 2026-09-24T11:00:56.256411+00:00 由主控 codex:01a0cff1-36ce-77e1-a013-5b10d6c6271c 按 approval plan `codex-retro-batch2-stagefix-resign-20260924-v2` 验收；源边界、页数和缺源说明见逐卷不可变验收回执。
