# BJ-2024-DC-ERMO-Q10

## 修复身份
- source_provenance: [provenance_registry.md](sources/provenance_registry.md)
- 历史状态已停用（原记录：本文件是 33 全卷修复候选，非旧父稿副本。）；当前状态以 conversion_manifest.json 与验收回执为准。
- parent_path: `DeepSeek_政治题库资料库_20260918/questions/BJ-2024-DC-ERMO/BJ-2024-DC-ERMO-Q10.md`
- parent_sha256: `56e0fa93cdcdc82353f6993dfa0aba96ed4195a6a0232ffffdca1ed022d10dc8`
- repair_support: [support.json](sources/support_32_q1_q15/support.json)（Q10）
- repair_support_sha256: `c0ba997a2e26e4ff88b8c0c98f0a71bc02b0611d486113cf4426e9a399204837`
- 已验收修订范围: 原卷题面、题号/分值、图表/框线/拓扑已从 32 视觉支持补入；旧父稿仅保留为身份回溯，不作为题面。

## 来源角色：ORIGINAL_QUESTION（原卷视觉回源）
- source_pdf: [paper.pdf](sources/legacy_30_sources/originals/paper.pdf)；physical_page=P04；printed_score=3
- page_asset: [P04.png](assets/visual_support/q1_q15/pages/P04.png)
- crop_asset: [Q10.png](assets/visual_support/q1_q15/crops/Q10.png)
- crop_sha256: `eb69796a5205ee2e54fe1cbf7566044bf0b399b2689812292e52d530ac944a5b`
- source_role_boundary: 仅用于题面；不含答案或正式评分推断。

### 原卷逐项转写

#### material_box
- ✧在几何学中，“点”没有大小，“线”没有宽度，“面”没有厚度。
- ✧在流体力学中，“理想液体”既不可压缩又没有黏滞性。
- ✧在分子物理学中，“理想气体”对分子本身的体积与分子之间的作用力是忽略不计的。

#### stem
上述材料说明

#### options
- **A**: 简略化是对认识结果进行简要化处理的思维抽象环节
- **B**: 思维抽象具有概括性，从多样性统一的事物中抽取本质和规律
- **C**: 思维抽象具有主观能动性，通过实践把抽象的事物转化成现实的事物
- **D**: 理想化使得认识对象在思维中能够按照思维主体所希望的那样存在

### 图表/框线/拓扑结构
- 题号10在左侧；材料为单个虚线矩形框，内含3行菱形/四角星项目符号；框外紧接‘上述材料说明’和纵向A-D选项。
- 材料框内第三条在‘忽略’处换行，不能误读为新条目。

### 视觉修正/未决
- 
- 
- 保留材料框的虚线边框和3条项目符号结构；以原卷转写替换文字；score=3；保留答案字段。

## 来源角色：ANSWER_KEY（保留的旧答案源）
- 该答案字段来自 30 包评分扫描视觉答案键，不来自 32 视觉支持；只作为答案角色保留，不升级为题面或评分槽。
- answer_key: `D`
- scoring_status: `choice_answer_key_only`; 每题分值由原卷首部统一确定为3，未由答案键拆分评分槽。

## 来源角色：STUDENT_LAYER
- 选择题支持包和原始题源未发现学生答卷/评分截图；本题 `N/A_with_basis`。

## 整合护栏
- 不修正答案、不把图中装饰微字臆补为题面、不扁平化地图/虚线框/图表/箭头结构。
