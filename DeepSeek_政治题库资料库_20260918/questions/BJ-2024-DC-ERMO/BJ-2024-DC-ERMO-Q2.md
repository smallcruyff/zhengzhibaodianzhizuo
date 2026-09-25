# BJ-2024-DC-ERMO-Q2

## 修复身份
- source_provenance: [provenance_registry.md](sources/provenance_registry.md)
- 历史状态已停用（原记录：本文件是 33 全卷修复候选，非旧父稿副本。）；当前状态以 conversion_manifest.json 与验收回执为准。
- parent_path: `DeepSeek_政治题库资料库_20260918/questions/BJ-2024-DC-ERMO/BJ-2024-DC-ERMO-Q2.md`
- parent_sha256: `29591abfb71e2527777463839c0ad0778b5c4fe37be238622fd8c04410148408`
- repair_support: [support.json](sources/support_32_q1_q15/support.json)（Q02）
- repair_support_sha256: `c0ba997a2e26e4ff88b8c0c98f0a71bc02b0611d486113cf4426e9a399204837`
- 已验收修订范围: 原卷题面、题号/分值、图表/框线/拓扑已从 32 视觉支持补入；旧父稿仅保留为身份回溯，不作为题面。

## 来源角色：ORIGINAL_QUESTION（原卷视觉回源）
- source_pdf: [paper.pdf](sources/legacy_30_sources/originals/paper.pdf)；physical_page=P02；printed_score=3
- page_asset: [P02.png](assets/visual_support/q1_q15/pages/P02.png)
- crop_asset: [Q02.png](assets/visual_support/q1_q15/crops/Q02.png)
- crop_sha256: `5a9c874360ff9247d33c67a09b786394564c1d9bfcb788c0383ff1740e8bbe0b`
- source_role_boundary: 仅用于题面；不含答案或正式评分推断。

### 原卷逐项转写

#### stem
第十四届北京国际电影节展现不同国家的电影艺术，各美其美，《龙凤呈祥》《大闹天宫》等“京剧电影工程”经典影片大放异彩。中外影人齐聚一堂，探讨前沿话题，同时，招商展会、项目创投等活动随之展开，国内外电影产业深度融合。北京国际电影节

#### statements
- ①用电影语言讲述中国故事，展示中华文化独特魅力
- ②能够增强对不同文化的理解和认同，激发电影艺术创造活力
- ③将优秀文化产品转化为物质力量，助力文化产业发展
- ④荟萃电影精品，搭建文化互鉴桥梁，有利于世界文化繁荣

#### options
- **A**: ①②
- **B**: ①④
- **C**: ②③
- **D**: ③④

### 图表/框线/拓扑结构
- 单栏题面；题干后接四条圆圈序号陈述；A-D横向排布在同一行。

### 视觉修正/未决
- 
- 
- 以原卷转写替换题面；score=3；保留现有答案字段，不从本支持包推断答案。

## 来源角色：ANSWER_KEY（保留的旧答案源）
- 该答案字段来自 30 包评分扫描视觉答案键，不来自 32 视觉支持；只作为答案角色保留，不升级为题面或评分槽。
- answer_key: `B`
- scoring_status: `choice_answer_key_only`; 每题分值由原卷首部统一确定为3，未由答案键拆分评分槽。

## 来源角色：STUDENT_LAYER
- 选择题支持包和原始题源未发现学生答卷/评分截图；本题 `N/A_with_basis`。

## 整合护栏
- 不修正答案、不把图中装饰微字臆补为题面、不扁平化地图/虚线框/图表/箭头结构。
