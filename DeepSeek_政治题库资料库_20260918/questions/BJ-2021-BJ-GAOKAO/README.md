# BJ-2021-BJ-GAOKAO 整卷读取入口

## 卷首与状态

- package_status: `accepted_for_all_available_sources; Q18 unit and Q20 E1 chart deltas closed; question-local pending-review labels are pre-review provenance; scanned low-confidence glyphs remain bounded by source images`
- question items: 21
- candidate manifest SHA-256: `4a6e3aeb82f50027ed56dae491d35c9ce24e25c15c8e7f2599eda12ba833fee6`
- independent review: `verification/independent_review.json`
- shared bank modified: 2026-09-22由新总控按v4实物SHA合入
- 印刷卷首文字：[exam_front_matter.md](exam_front_matter.md)

## 来源角色

- `Sbfb92664a987`: 混合载体：p1-p10原卷；p11-p12参考答案/E3
- `S515af99fb5a8`: Q16-Q21正式评分细则/E1

原件、完整文本层转写和来源SHA见 [sources/index.json](sources/index.json)；页图与题图在 `assets/`。`[NO_NATIVE_TEXT_LAYER]`表示原件图像为权威。

## 题级导航

- [BJ-2021-BJ-GAOKAO-Q1](BJ-2021-BJ-GAOKAO-Q1.md)
- [BJ-2021-BJ-GAOKAO-Q10](BJ-2021-BJ-GAOKAO-Q10.md)
- [BJ-2021-BJ-GAOKAO-Q11](BJ-2021-BJ-GAOKAO-Q11.md)
- [BJ-2021-BJ-GAOKAO-Q12](BJ-2021-BJ-GAOKAO-Q12.md)
- [BJ-2021-BJ-GAOKAO-Q13](BJ-2021-BJ-GAOKAO-Q13.md)
- [BJ-2021-BJ-GAOKAO-Q14](BJ-2021-BJ-GAOKAO-Q14.md)
- [BJ-2021-BJ-GAOKAO-Q15](BJ-2021-BJ-GAOKAO-Q15.md)
- [BJ-2021-BJ-GAOKAO-Q16](BJ-2021-BJ-GAOKAO-Q16.md)
- [BJ-2021-BJ-GAOKAO-Q17](BJ-2021-BJ-GAOKAO-Q17.md)
- [BJ-2021-BJ-GAOKAO-Q18](BJ-2021-BJ-GAOKAO-Q18.md)
- [BJ-2021-BJ-GAOKAO-Q19](BJ-2021-BJ-GAOKAO-Q19.md)
- [BJ-2021-BJ-GAOKAO-Q2](BJ-2021-BJ-GAOKAO-Q2.md)
- [BJ-2021-BJ-GAOKAO-Q20](BJ-2021-BJ-GAOKAO-Q20.md)
- [BJ-2021-BJ-GAOKAO-Q21](BJ-2021-BJ-GAOKAO-Q21.md)
- [BJ-2021-BJ-GAOKAO-Q3](BJ-2021-BJ-GAOKAO-Q3.md)
- [BJ-2021-BJ-GAOKAO-Q4](BJ-2021-BJ-GAOKAO-Q4.md)
- [BJ-2021-BJ-GAOKAO-Q5](BJ-2021-BJ-GAOKAO-Q5.md)
- [BJ-2021-BJ-GAOKAO-Q6](BJ-2021-BJ-GAOKAO-Q6.md)
- [BJ-2021-BJ-GAOKAO-Q7](BJ-2021-BJ-GAOKAO-Q7.md)
- [BJ-2021-BJ-GAOKAO-Q8](BJ-2021-BJ-GAOKAO-Q8.md)
- [BJ-2021-BJ-GAOKAO-Q9](BJ-2021-BJ-GAOKAO-Q9.md)

## 包结构

本目录只含一份当前MD版本及自包含`assets/`、`sources/`。题稿链接已归一为本目录内`assets/`。
`raw_history/`只保留已明确降级的低置信原始转写，不得当作正文或E1。


## 当前共享状态

21题、100分；教师版12页（试卷区p1—p10、E3答案p11—p12）、正式细则7页完整保存。原卷封面印刷共9页，仍原样保留。Q8四栏、Q18植树图“760亿株”、Q20教师版与正式评分载体各自图表、Q21已核字形均独立复核；Q20旧图形OCR残片单独存入raw_history，未混入可读E1。

题级历史pending标记属于形成记录，当前以[共享状态与21题SHA](shared_conversion_state.json)为准。个人学生样卷未提供；汇总阅卷反馈与个人样卷分开。
