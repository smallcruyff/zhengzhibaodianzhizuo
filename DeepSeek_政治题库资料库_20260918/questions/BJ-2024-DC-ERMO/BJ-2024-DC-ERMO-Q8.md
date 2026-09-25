# BJ-2024-DC-ERMO-Q8

## 修复身份
- source_provenance: [provenance_registry.md](sources/provenance_registry.md)
- 历史状态已停用（原记录：本文件是 33 全卷修复候选，非旧父稿副本。）；当前状态以 conversion_manifest.json 与验收回执为准。
- parent_path: `DeepSeek_政治题库资料库_20260918/questions/BJ-2024-DC-ERMO/BJ-2024-DC-ERMO-Q8.md`
- parent_sha256: `a9ff00fd33e94c899b103ac6b85c20af5a85ff0436ff2c29afdaccbb5a27f9ed`
- repair_support: [support.json](sources/support_32_q1_q15/support.json)（Q08）
- repair_support_sha256: `c0ba997a2e26e4ff88b8c0c98f0a71bc02b0611d486113cf4426e9a399204837`
- 已验收修订范围: 原卷题面、题号/分值、图表/框线/拓扑已从 32 视觉支持补入；旧父稿仅保留为身份回溯，不作为题面。

## 来源角色：ORIGINAL_QUESTION（原卷视觉回源）
- source_pdf: [paper.pdf](sources/legacy_30_sources/originals/paper.pdf)；physical_page=P03；printed_score=3
- page_asset: [P03.png](assets/visual_support/q1_q15/pages/P03.png)
- crop_asset: [Q08.png](assets/visual_support/q1_q15/crops/Q08.png)
- crop_sha256: `838e485e07e4e3050834f70291ef199b0852930bc8f91ea4e68d65fa3e79d3ed`
- source_role_boundary: 仅用于题面；不含答案或正式评分推断。

### 原卷逐项转写

#### stem
某纸业有限公司在一支流河道埋设暗管，排放生产废水。经鉴定，该公司偷排废水期间，河道内水质指标远超基线水平，造成环境污染损害数额为1081余万元。该地人民检察院对该公司提起公诉，并提起刑事附带民事公益诉讼。下列说法正确的是

#### options
- **A**: 若对一审判决不服，双方当事人可于15日内上诉
- **B**: 该案提交的水质鉴定报告属于物证，影像资料属于电子数据
- **C**: 被告不在规定时间内提交答辩状，并不影响人民法院审理该案
- **D**: 刑事诉讼中，被告人若掌握罪证相关证据，则有义务向法庭提交

### 图表/框线/拓扑结构
- 单栏题面；四个字母选项纵向排列，无图表/表格。

### 视觉修正/未决
- 
- 原候选漏掉‘数额为’中的‘为’；B/C/D句首均有原卷标点空格，整合时保持正常中文排版即可。
- 以原卷转写替换题面；score=3；保留答案字段。

## 来源角色：ANSWER_KEY（保留的旧答案源）
- 该答案字段来自 30 包评分扫描视觉答案键，不来自 32 视觉支持；只作为答案角色保留，不升级为题面或评分槽。
- answer_key: `C`
- scoring_status: `choice_answer_key_only`; 每题分值由原卷首部统一确定为3，未由答案键拆分评分槽。

## 来源角色：STUDENT_LAYER
- 选择题支持包和原始题源未发现学生答卷/评分截图；本题 `N/A_with_basis`。

## 整合护栏
- 不修正答案、不把图中装饰微字臆补为题面、不扁平化地图/虚线框/图表/箭头结构。
