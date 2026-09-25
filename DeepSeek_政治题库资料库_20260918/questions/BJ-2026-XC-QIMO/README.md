# BJ-2026-XC-QIMO 共享题库入口

> 本卷已物化到共享题库；题面、答案、正式评分PDF和评标PPT均有本地原图与机器可读转写。整卷是否达到“已验收”只看总清单和独立复核回执，不能由文件存在自行推断。

## 卷首说明（供AI读取）

- 试卷：北京市西城区2025—2026学年度第一学期期末试卷，高三思想政治；`exam_id=BJ-2026-XC-QIMO`。
- 物理PDF共12页：p001—p009是原卷题面；p010—p012是同一物理PDF中嵌入的参考答案。原卷实际结构为15道选择题（15×3分=45分）+6道非选择题（55分）=21题、100分。
- 卷首与页脚原样关系：卷首印有“本试卷共8页，100分。考试时长90分钟。考生务必将答案答在答题卡上，在试卷上作答无效。考试结束后，将本试卷和答题卡一并交回。”；但题面实际延续到物理p009，且各题面页脚印作“第N页（共9页）”。这是原载体内部页数矛盾，必须两者并存，不能把卷首“8页”静默改成9页。
- 题面阅读顺序：先读每题MD中的“原卷题面”，再读其E0页图；不要把答案、细则或评标PPT文字混入题面。
- 证据分层硬规则：`Sefbc5507a38d` p001—p009 = **E0原卷题面**；`Sefbc5507a38d` p010—p012 = **E3嵌入参考答案**；同SHA路径副本不是独立答案，也不是E1。`S54715a1e650d`细则PDF为Q16—Q21的E1正式评分来源。`S9aecfff2e370`是具名正式评标载体，但须按内容单元分层：明确评分规则为E1，答案示例/方向提示为E3，Q19 slides 6—9知识图与备注为E2候选；未标分知识词不被臆拆为固定评分槽。
- 学生层：原始资料中未发现学生答题卡、学生示例、教师批注或逐题实得分；所有题统一标记 `N/A_with_basis`，不填充、不推定。
- 版式和特殊符号：Q18的三个黑菱形与横向虚线是原页分隔标记，文字化注记在Q18的“原页版式标记”中，不能当作题干或评分点。

## 完整来源覆盖表

| source_id | SHA-256 | 物理载体 | 覆盖范围 | 证据层 | 独立性与限制 |
|---|---|---|---|---|---|
| `Sefbc5507a38d` | `efbc5507a38dbd4f41a57acd1dfe4877df191813555b2318d451a1b3a855f230` | 教师版原卷PDF p001—p012 | p001—p009原卷题面；p010—p012嵌入参考答案 | p001—p009=E0；p010—p012=E3 | 同一物理文件同时出现“教师版”与“参考答案”路径；不能计作两个独立源，整份不作E1 |
| `Sefbc5507a38d` | `efbc5507a38dbd4f41a57acd1dfe4877df191813555b2318d451a1b3a855f230` | `高三思想政治参考答案.pdf`路径副本 | 与上一行完全同SHA、同页内容 | E3（p010—p012） | 路径名不改变物理身份；不是独立答案证据 |
| `S54715a1e650d` | `54715a1e650d940e1470d8348f9c4cfaaa4a92cb983965a022b2fae5049ca1a4` | 正式评分PDF p001—p005 | Q16 p001—p002；Q17 p002—p003；Q18 p003；Q19 p003—p004；Q20 p004—p005；Q21 p005 | E1 | 题级正式评分依据；不从E3答案反推评分槽 |
| `S9aecfff2e370` | `9aecfff2e370dc980e0ceb4805b28f66ebfbbeffa7ccdbd4b909dc96b01a3cbe` | 评标PPTX slides 1—12及原始备注/形状文字 | Q16 slides 1—3；Q17 slide 4；Q18 slide 5；Q19 slides 6—10；Q20 slide 11；Q21 slide 12 | 混合E1/E2/E3 | E1：slide 1蓝字、2、4、5、10、11、12蓝字；E3：slide 1黑字、3、12黑字；E2候选：slides 6—9。按内容单元使用，不整份统一升降级 |

### 评标PPT视觉渲染资产覆盖（具名正式评标载体，内容级分层）

原生PPTX `sources/marking_slides.pptx` 和完整形状文字/备注提取 `sources/slides_extracted_text.txt` 均保持不变。以下为由同一PPTX转换所得的12张视觉页；其中本次补齐了第2张和第9张。`source_render/slides/` 与 `assets/slide_pages/` 中对应文件逐一同SHA，题级MD通过 `../assets/slide_pages/slide_pXXX.png` 访问。

| PPT页 | 题级/用途 | 题级可访问链接 | 视觉页SHA-256 |
|---:|---|---|---|
| 1 | Q16（1） | `assets/slide_pages/slide_p001.png` | `75ccbc5329dc0623bd91270f2356bf279bd0dd44dec4f14c5fbec451d72e065d` |
| 2 | Q16（2）等级描述（本次补齐） | `assets/slide_pages/slide_p002.png` | `af83e00e2deee6873e49c24d533677b73d652c02b079e3dd543f0cb43ac21e79` |
| 3 | Q16（2）示例 | `assets/slide_pages/slide_p003.png` | `a55d5bf9e1688cb25402abf46bf9623c98b756fc1111e5c29ba8769b7876c636` |
| 4 | Q17 | `assets/slide_pages/slide_p004.png` | `7aa7a882966887d602c1003b6df02b3135d60f8a1c3b20a18a795400d76b11eb` |
| 5 | Q18 | `assets/slide_pages/slide_p005.png` | `2dd4a49a2f91c5568ddd5aa704ab900b94979f33487fe6c365ef4ea87879aa3f` |
| 6 | Q19（1）框架 | `assets/slide_pages/slide_p006.png` | `359bf1fcd5f49293557f8b7fd0baa89b5089794cfe3616603a42de680a58cd21` |
| 7 | Q19（1）双循环结构图 | `assets/slide_pages/slide_p007.png` | `4ae55bc2ce7a4c7350a70287bb35c3ffd049f301ae4854cc897b4c45b0ec1ede` |
| 8 | Q19（1）国内循环四环节 | `assets/slide_pages/slide_p008.png` | `899fcc2f6cd0827b8e2fb7867ef0b38af23cfd4c5df3c58070f3ee089830d576` |
| 9 | Q19（1）逐环节映射（本次补齐） | `assets/slide_pages/slide_p009.png` | `226292e4d2c6bdf6f3892deaa09752402a8bb5708210ad732b796e2e699ad165` |
| 10 | Q19（2） | `assets/slide_pages/slide_p010.png` | `cd7e6f6f8b96490cd6f8b34195b845fd02f30b2c6caa918407ce17a8a5f4f2e4` |
| 11 | Q20 | `assets/slide_pages/slide_p011.png` | `58e7fd4233bc2edebed7bf4d58f19b1134a9c2740759d6b6b78fe08ec33de37d` |
| 12 | Q21 | `assets/slide_pages/slide_p012.png` | `fb00b40550da6b00687c7cacebcdc9c99006adda92f67863bf3aabb25567839b` |

### 逐题页码与评标PPT映射

| 题号 | E0原卷页 | E3答案页 | E1细则PDF | 评标PPT内容级角色 |
|---:|---:|---:|---:|---:|
| 1—15 | p001—p005（按题级MD） | p010 | 无题级E1 | 无题级映射 |
| 16 | p006 | p010 | p001—p002 | slide 1蓝字与slide 2为E1；slide 1黑字与slide 3为E3 |
| 17 | p006 | p011 | p002—p003 | slide 4 |
| 18 | p007 | p011 | p003 | slide 5 |
| 19 | p007—p008 | p011 | p003—p004 | slides 6—9为E2候选；slide 10为E1 |
| 20 | p008 | p012 | p004—p005 | slide 11 |
| 21 | p009 | p012 | p005 | slide 12黑字为E3、蓝字细则为E1 |

其中Q20保留E0原卷“风电、太阳能”与E3答案“电、太阳能”的字面差异；Q21保留E0原卷“开门问策”与E3答案“开问策”的字面差异。

## 文件入口

- 逐题文件：`BJ-2026-XC-QIMO-Q1.md` 至 `Q21.md`。
- 审计和复核回执保存在流水线 `receipts/`；本目录保存可直接供AI读取的题级与来源级内容。
- 完整原始源副本：`sources/`；原卷、答案、评分页和PPT可视资产（slide 1—12，含本次补齐的2、9）：`assets/`；正式PDF完整逐页转写：`sources/formal_rubric_full.md`；PPT完整逐张视觉转写：`sources/marking_slides_full.md`；PPT形状文字及备注的全量提取：`sources/slides_extracted_text.txt`。
- 物化与合并SHA记录见流水线回执；本页来源表保留原始载体SHA。
