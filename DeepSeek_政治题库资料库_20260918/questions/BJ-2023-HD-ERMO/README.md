# BJ-2023-HD-ERMO 整卷读取入口

## 卷首与状态

- package_status: `conversion_layer_v3_full_support_transcripts_Q20_Q21_structured_source_conflict_s38_caveat`
- question items: 21
- candidate manifest SHA-256: `30d38cd657df38929d597d1f10d7b187dc9f18ffe4910deaf5793c641f0850bc`
- independent review: `verification/independent_review.json`
- shared bank modified: 2026-09-22由新总控按SHA部分合入
- 印刷卷首文字：[exam_front_matter.md](exam_front_matter.md)

## 来源角色

- `Sdf79f0c4f74e`: role recorded in sources/index.json
- `S0a294f8799f7`: role recorded in sources/index.json
- `Scd8eee06ecf3`: role recorded in sources/index.json

原件、完整文本层转写和来源SHA见 [sources/index.json](sources/index.json)；页图与题图在 `assets/`。`[NO_NATIVE_TEXT_LAYER]`表示原件图像为权威。

## 题级导航

- [BJ-2023-HD-ERMO-Q1](BJ-2023-HD-ERMO-Q1.md)
- [BJ-2023-HD-ERMO-Q10](BJ-2023-HD-ERMO-Q10.md)
- [BJ-2023-HD-ERMO-Q11](BJ-2023-HD-ERMO-Q11.md)
- [BJ-2023-HD-ERMO-Q12](BJ-2023-HD-ERMO-Q12.md)
- [BJ-2023-HD-ERMO-Q13](BJ-2023-HD-ERMO-Q13.md)
- [BJ-2023-HD-ERMO-Q14](BJ-2023-HD-ERMO-Q14.md)
- [BJ-2023-HD-ERMO-Q15](BJ-2023-HD-ERMO-Q15.md)
- [BJ-2023-HD-ERMO-Q16](BJ-2023-HD-ERMO-Q16.md)
- [BJ-2023-HD-ERMO-Q17](BJ-2023-HD-ERMO-Q17.md)
- [BJ-2023-HD-ERMO-Q18](BJ-2023-HD-ERMO-Q18.md)
- [BJ-2023-HD-ERMO-Q19](BJ-2023-HD-ERMO-Q19.md)
- [BJ-2023-HD-ERMO-Q2](BJ-2023-HD-ERMO-Q2.md)
- [BJ-2023-HD-ERMO-Q20](BJ-2023-HD-ERMO-Q20.md)
- [BJ-2023-HD-ERMO-Q21](BJ-2023-HD-ERMO-Q21.md)
- [BJ-2023-HD-ERMO-Q3](BJ-2023-HD-ERMO-Q3.md)
- [BJ-2023-HD-ERMO-Q4](BJ-2023-HD-ERMO-Q4.md)
- [BJ-2023-HD-ERMO-Q5](BJ-2023-HD-ERMO-Q5.md)
- [BJ-2023-HD-ERMO-Q6](BJ-2023-HD-ERMO-Q6.md)
- [BJ-2023-HD-ERMO-Q7](BJ-2023-HD-ERMO-Q7.md)
- [BJ-2023-HD-ERMO-Q8](BJ-2023-HD-ERMO-Q8.md)
- [BJ-2023-HD-ERMO-Q9](BJ-2023-HD-ERMO-Q9.md)

## 包结构

本目录只含一份当前MD版本及自包含`assets/`、`sources/`。题稿链接已归一为本目录内`assets/`。


## 共享状态与来源边界

21题、原卷8页、参考答案3页、评分载体43页及完整文本缓存已合入；第20题三列表和第21题三组原因框已按原卷补全并独立复核。

原卷和答案印刷“第二学期期末练习／2023.05”，工程键为ERMO、评分载体为“海淀二模”，三重身份并列保留；未强改原来源登记。评分第38页PNG只反映动画的一个静态状态，四条学生问题文字在TXT/XML完整保留。全卷仍待保真终验，不据此提升学生样卷或选择题E1状态。

- [共享状态与题稿SHA](shared_conversion_state.json)
- [43张评分幻灯片完整XML文字](sources/transcripts/Scd8eee06ecf3.slides.json)

## 评分PPT（43张）非题目专属页

以下幻灯片不专属任何一题，全部文字已在此列出，不再单独建小节：

- s01（封面）：全部文字为“海淀二模”，即评分PPTX标题页，无其他内容。
- s02“16题”、s07“17题 （6分）”、s12“18题 （6分）”、s17“19题”、s23“20（1）题”、s24“20（2）题”、s29“20（3）题”、s34“21（1）题”、s39“21（2）题”：均为题号/分值的分隔标题页，全部文字已包含在对应题号（“题号”“分值”字段），页图已在各题“正式评分材料（E1）”小节的幻灯片列表中链接，不重复转写。

其余34张（“一、试题分析”“三、试题讲解示例”“四、学生问题”及评分表图片页）均已按题号分别转写进 BJ-2023-HD-ERMO-Q16～Q21.md 的“正式评分材料（E1）”与“评分PPT讲评页（试题分析/讲解示例，讲评，非评分依据）”两个部分，见各题文件。

现有来源转换已于 2026-09-23T02:58:50.460261+00:00 由主控 codex:01a0cbfa-7dfb-7b82-b886-9b4101a90b29 按 approval plan `codex-bank-direct-hd-ermo-20260922` 验收；源边界、页数和缺源说明见逐卷不可变验收回执。
