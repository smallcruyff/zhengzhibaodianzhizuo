# BJ-2025-SY-YIMO — A_r1 卷级候选与来源索引

## 状态和边界

这是A侧来源核查与逐题补全候选包，供独立B复核。卷内21道题全部按当前live BANK题稿哈希为父稿，基于East `controller_ready`材料化底稿；Q4/Q7从已核验父哈希的`post_overlay_staging_v2_20260922`覆盖底稿继续。仅作为本卷隔离候选，不代表整卷PASS、合并、验收或接受。Q6 E3答案冲突和学生样卷不可读文字留有HOLD。

- 原卷PDF（source_id `S9dd43cae443f`）：`/Users/wanglifei/Desktop/2025模拟题/2025各区一模/2025顺义一模/试卷/试卷.pdf`；SHA-256 `9dd43cae443f853c0799034210e45b3e1040c48facb2cdf3d42dbba195ee4b16`；18页。题面E0为p1–p8，卷内答案与解析E3为p9–p18。
- 评分DOCX（source_id `Sbef8332e23ce`）：`/Users/wanglifei/Desktop/2025模拟题/2025各区一模/2025顺义一模/细则/细则.docx`；SHA-256 `bef8332e23ce30ac4e04eef21ff030c777eb4088111eb581c4b5257ae37a8fcc`；原生XML共86段、0个Word表、16个嵌入媒体；细则DOCX同时含E3参考答案、E1评分标准、非计分阅卷诊断和学生样卷。
- 细则普通渲染有字体替代/文字缺损；`assets/rubric_pages_font_substitute/p-01.png`至`p-11.png`是同一原始DOCX的可读字体替代渲染（不是另一个答案来源）。7张原普通渲染图也保留于`assets/rubric_pages/`以供核验；不得把字体替代渲染称作原DOCX原生显示成功。
- 无独立参考答案文件：`N/A_with_basis`。试卷PDF内页p9–p18含E3答案/解析，DOCX段落5–7含E3选择题答案键。

<a id="q1-q15-docx-answer-key-e3"></a>
## Q1–Q15 DOCX答案键（E3）

以下直接转写细则DOCX p-01原生段落5–7。段落7将`13B`无点号连写，本文为可读索引格式`Q13=B`，原始拼写仍见页图。该答案键属于E3，不能充当E1。

| 题号 | DOCX E3答案 | 原生定位 | 去向 |
|---|---|---|---|
| Q1 | A | DOCX p-01／段落5 | Q1文件；DOCX答案键逐题对照 |
| Q2 | C | DOCX p-01／段落5 | Q2文件；DOCX答案键逐题对照 |
| Q3 | B | DOCX p-01／段落5 | Q3文件；DOCX答案键逐题对照 |
| Q4 | D | DOCX p-01／段落5 | Q4文件；DOCX答案键逐题对照 |
| Q5 | B | DOCX p-01／段落5 | Q5文件；DOCX答案键逐题对照 |
| Q6 | C | DOCX p-01／段落6 | Q6文件；DOCX答案键逐题对照 |
| Q7 | A | DOCX p-01／段落6 | Q7文件；DOCX答案键逐题对照 |
| Q8 | C | DOCX p-01／段落6 | Q8文件；DOCX答案键逐题对照 |
| Q9 | B | DOCX p-01／段落6 | Q9文件；DOCX答案键逐题对照 |
| Q10 | A | DOCX p-01／段落6 | Q10文件；DOCX答案键逐题对照 |
| Q11 | D | DOCX p-01／段落7 | Q11文件；DOCX答案键逐题对照 |
| Q12 | C | DOCX p-01／段落7 | Q12文件；DOCX答案键逐题对照 |
| Q13 | B | DOCX p-01／段落7 | Q13文件；DOCX答案键逐题对照 |
| Q14 | D | DOCX p-01／段落7 | Q14文件；DOCX答案键逐题对照 |
| Q15 | A | DOCX p-01／段落7 | Q15文件；DOCX答案键逐题对照 |

**Q6冲突HOLD：**原卷PDF E3 p9答案表与解析均为`6.A`；评分DOCX E3 p-01／段落6为`6.C`。两项并列保存于Q6，未选择胜者，待有权限的教研负责人裁定。

## Source page destinations

每张原卷页图保留于`assets/exam_pages/pNNN.png`；下列为逐页目视检查后确认的题目目的地。E0/E3区别见各Q文件；p9包含答案键并开始Q1–Q3的E3解析，p10–p18继续提供E3解析/参考作答。

| 主卷PDF页 | 内容角色 | E0题面去向／E3题目去向 |
|---|---|---|
| p01 | E0题面 | Q1, Q2, Q3, Q4 |
| p02 | E0题面 | Q4, Q5, Q6, Q7 |
| p03 | E0题面 | Q7, Q8, Q9, Q10 |
| p04 | E0题面 | Q10, Q11, Q12, Q13 |
| p05 | E0题面 | Q13, Q14, Q15, Q16, Q17 |
| p06 | E0题面 | Q17, Q18, Q19 |
| p07 | E0题面 | Q19, Q20, Q21 |
| p08 | E0题面 | Q21 |
| p09 | E3答案键+解析 | Q1, Q2, Q3, Q4, Q5, Q6, Q7, Q8, Q9, Q10, Q11, Q12, Q13, Q14, Q15 |
| p10 | E3解析/参考作答 | Q4, Q5, Q6, Q7 |
| p11 | E3解析/参考作答 | Q7, Q8, Q9, Q10 |
| p12 | E3解析/参考作答 | Q10, Q11, Q12, Q13, Q14 |
| p13 | E3解析/参考作答 | Q14, Q15, Q16 |
| p14 | E3解析/参考作答 | Q16, Q17 |
| p15 | E3解析/参考作答 | Q17, Q18 |
| p16 | E3解析/参考作答 | Q18, Q19 |
| p17 | E3解析/参考作答 | Q19, Q20, Q21 |
| p18 | E3解析/参考作答 | Q21 |
细则11张可读字体替代页图保留于`assets/rubric_pages_font_substitute/p-01.png`至`p-11.png`；逐页落点如下（原生DOCX段落号为更稳定的定位）：

| DOCX可读渲染页 | 段落范围及题目目的地 |
|---|---|
| [p-01](assets/rubric_pages_font_substitute/p-01.png) | 段落1–17：页题头、Q1–Q15答案键（Q1–15）；Q16参考角度（Q16） |
| [p-02](assets/rubric_pages_font_substitute/p-02.png) | 段落18–25：Q16 E1分档细则、优秀卷标记/样卷；段落26 Q17(1)题头（Q16、Q17） |
| [p-03](assets/rubric_pages_font_substitute/p-03.png) | 段落27–32：Q17(1) E3参考答案、E1评分点、诊断和样卷锚点（Q17） |
| [p-04](assets/rubric_pages_font_substitute/p-04.png) | 段落33–42：Q17(2) E3答案、E1评分点（Q17） |
| [p-05](assets/rubric_pages_font_substitute/p-05.png) | 段落43–49：Q17(2)样卷/诊断、Q18评分细则（Q17、Q18） |
| [p-06](assets/rubric_pages_font_substitute/p-06.png) | 段落50–54：Q19(1)案例1 E1、空白诊断标题及图像锚点（Q19） |
| [p-07](assets/rubric_pages_font_substitute/p-07.png) | 段落55–59：Q19(1)案例2 E1、Q19(2) E3参考答案（Q19） |
| [p-08](assets/rubric_pages_font_substitute/p-08.png) | 段落60–64：Q19(2)阅卷细则；段落65 Q20 E1细则开头（Q19、Q20） |
| [p-09](assets/rubric_pages_font_substitute/p-09.png) | 段落66–71：Q20 E1续文、材料关联说明、阅卷诊断（Q20） |
| [p-10](assets/rubric_pages_font_substitute/p-10.png) | 段落72–80：Q20样卷媒体；Q21 E1媒体锚点/优秀卷诊断（Q20、Q21） |
| [p-11](assets/rubric_pages_font_substitute/p-11.png) | 段落81–86：Q21问题卷诊断、样卷媒体（Q21） |

## DOCX paragraph and media destinations

- 段落1–4：本卷身份、学科及第一部分说明；卷级README。

细则 DOCX 原生段落1–4原文：

| 段落 | 原文 |
|---|---|
| 1 | 顺义区2025年高三统一测试参考答案（2025.3） |
| 2 | 思想政治 |
| 3 | 第一部分 |
| 4 | 本部分共15题，每题3分，共45分。 |

- 段落5–7：Q1–Q15选择题E3答案键；本README表格与Q1–Q15逐题链接。
- 段落8空白；段落9“第二部分”分隔符；README卷级结构。
- 段落10–23：Q16参考角度/知识提示（11–17，按E3参考思路保留）与E1评分分档/计分描述（18–23）；Q16文件。
- 段落24–25与image1–2：Q16优秀样卷标签和学生答案图片；Q16文件，图片原样链接。
- 段落26–32：Q17(1)，段落27为E3参考答案，28–29为E1评分细则，32为非计分诊断；Q17文件。
- 段落30–31/image3：Q17(1)学生样卷；Q17文件。
- 段落33–45：Q17(2)，段落34为E3参考答案，35–42为E1评分细则，45为非计分诊断；image4–5/段落43–44为学生样卷；Q17文件。
- 段落46–49：Q18 E1评分细则；Q18文件。
- 段落50–57：Q19(1)，50–51为案例1 E1，52空白诊断标题，53–57含样卷图像/锚点与案例2细则段落55；Q19文件。
- 段落58–64：Q19(2)，59为E3参考答案，60–64为E1评分细则；Q19文件。
- 段落65–71：Q20 E1评分细则及材料关联扣分说明（65–69），70–71为非计分阅卷诊断；Q20文件。
- 段落72/image10–11：Q20学生样卷；Q20文件。
- 段落73–74/image12–13：Q21嵌入式E1评分图像及结构化转写；Q21文件。
- 段落75–84：Q21优秀卷/问题卷/空白卷阅卷诊断（非E1）；Q21文件。
- 段落79/image14、段落85/image15、段落86/image16：Q21学生样卷；Q21文件。

DOCX媒体逐个保留原始嵌入文件名于`assets/rubric_embedded/`：image1–2属于Q16；image3–5属于Q17；image6–9属于Q19（image6/7在DOCX中有重复锚点但媒体不重复）；image10–11属于Q20；image12–13是Q21 E1；image14–16是Q21学生样卷。没有独立逐生计分表，个人得分为`N/A_with_basis`。

## 已确认的原件文字状态

- Q5 PDF E0选项D按页面原字保留“只有富有哲理，才文笔生动。”；标点不是题库候选替换出来的“、”。
- Q15 PDF p13 E3原文“发出发点”；Q17 DOCX段落27末句“上述判断为真的条件是杭州是由于杭州既获得…”；Q19题面“提起讼诉”“甲公司公司合法权益”和DOCX段落55“主观故意他人已经建立的商业信誉”；Q20 E0“援建买加”、DOCX段落69“200口井牙买加中国园林”均保留原文并标识，未静默校改。
- Q13时间轴框、Q15报告盒、Q18材料框、Q20中心辐射图及Q21“家”字谱系和说明框已作文字层结构转写；对应原卷页图仍是最终形状/位置/连线依据。

## Candidate bundle contents

本包重建21道题为独立题目Markdown，携带所引用原卷18页图、细则7张普通渲染图、11张字体替代页图及16个DOCX原始媒体。source images remain unchanged byte-for-byte from reviewed East assets; candidate question Markdown is A_r1 rebase/repair layer and requires independent B full-volume review. No merge or acceptance performed.

现有来源转换已于 2026-09-24T15:09:47.205887+00:00 由主控 codex:01a0cff1-36ce-77e1-a013-5b10d6c6271c 按 approval plan `codex-bj-2025-sy-yimo-source-accept-20260924-v2` 验收；源边界、页数和缺源说明见逐卷不可变验收回执。

现有来源转换已于 2026-09-24T17:46:55.420280+00:00 由主控 codex:01a0cff1-36ce-77e1-a013-5b10d6c6271c 按 approval plan `codex-retro-sy-yimo-q20-resign-20260924-v1` 验收；源边界、页数和缺源说明见逐卷不可变验收回执。
