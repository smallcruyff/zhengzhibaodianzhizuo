# BJ-2022-BJ-GAOKAO 整卷读取入口

## 卷首与状态

- package_status: `accepted_for_all_available_sources`
- question items: 21
- candidate manifest SHA-256: `76ed2b5ac425b64ce031c7e5b63d179a8c2a4dfd2504790349a3e8743ad3df76`
- independent review: `verification/independent_review.json`
- shared bank modified: 2026-09-22按v4身份合入共享库
- 印刷卷首文字：[exam_front_matter.md](exam_front_matter.md)

## 来源角色

- `Sb2dd3b8daa4d`: 混合载体：p1-p7原卷题面，p8-p22参考答案/解析E3
- `S07b058a51918`: Q16-Q21正式阅卷标准/E1

原件、完整文本层转写和来源SHA见 [sources/index.json](sources/index.json)；页图与题图在 `assets/`。`[NO_NATIVE_TEXT_LAYER]`表示原件图像为权威。

## 题级导航

- [BJ-2022-BJ-GAOKAO-Q1](BJ-2022-BJ-GAOKAO-Q1.md)
- [BJ-2022-BJ-GAOKAO-Q10](BJ-2022-BJ-GAOKAO-Q10.md)
- [BJ-2022-BJ-GAOKAO-Q11](BJ-2022-BJ-GAOKAO-Q11.md)
- [BJ-2022-BJ-GAOKAO-Q12](BJ-2022-BJ-GAOKAO-Q12.md)
- [BJ-2022-BJ-GAOKAO-Q13](BJ-2022-BJ-GAOKAO-Q13.md)
- [BJ-2022-BJ-GAOKAO-Q14](BJ-2022-BJ-GAOKAO-Q14.md)
- [BJ-2022-BJ-GAOKAO-Q15](BJ-2022-BJ-GAOKAO-Q15.md)
- [BJ-2022-BJ-GAOKAO-Q16](BJ-2022-BJ-GAOKAO-Q16.md)
- [BJ-2022-BJ-GAOKAO-Q17](BJ-2022-BJ-GAOKAO-Q17.md)
- [BJ-2022-BJ-GAOKAO-Q18](BJ-2022-BJ-GAOKAO-Q18.md)
- [BJ-2022-BJ-GAOKAO-Q19](BJ-2022-BJ-GAOKAO-Q19.md)
- [BJ-2022-BJ-GAOKAO-Q2](BJ-2022-BJ-GAOKAO-Q2.md)
- [BJ-2022-BJ-GAOKAO-Q20](BJ-2022-BJ-GAOKAO-Q20.md)
- [BJ-2022-BJ-GAOKAO-Q21](BJ-2022-BJ-GAOKAO-Q21.md)
- [BJ-2022-BJ-GAOKAO-Q3](BJ-2022-BJ-GAOKAO-Q3.md)
- [BJ-2022-BJ-GAOKAO-Q4](BJ-2022-BJ-GAOKAO-Q4.md)
- [BJ-2022-BJ-GAOKAO-Q5](BJ-2022-BJ-GAOKAO-Q5.md)
- [BJ-2022-BJ-GAOKAO-Q6](BJ-2022-BJ-GAOKAO-Q6.md)
- [BJ-2022-BJ-GAOKAO-Q7](BJ-2022-BJ-GAOKAO-Q7.md)
- [BJ-2022-BJ-GAOKAO-Q8](BJ-2022-BJ-GAOKAO-Q8.md)
- [BJ-2022-BJ-GAOKAO-Q9](BJ-2022-BJ-GAOKAO-Q9.md)

## 包结构

本目录只含一份当前MD版本及自包含`assets/`、`sources/`。题稿链接已归一为本目录内`assets/`。
`raw_history/`只保留已明确降级的低置信原始转写，不得当作正文或E1。


## 当前共享状态

21题、100分；教师版22页（题面p1–p7，E3答案与解析p8–p22）及正式评分7页完整保存。Q17评分表、Q18三列表格/空格/本源设问、Q19原印字形、Q20法律层级图与评分文字的修补均经过独立复核。题稿旧候选字样是形成记录，当前以[共享状态与21题SHA](shared_conversion_state.json)为准；原提取异常隔离为历史，源上真实错字/分值差异仍分别保留。

现有全部来源的转换已于2026-09-22验收。验收保留真实缺源及源层差异，不提高来源证据等级，也不代表任何宝典书稿的验收。
