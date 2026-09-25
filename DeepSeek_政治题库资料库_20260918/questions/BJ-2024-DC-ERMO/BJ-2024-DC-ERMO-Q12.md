# BJ-2024-DC-ERMO-Q12

## 修复身份
- source_provenance: [provenance_registry.md](sources/provenance_registry.md)
- 历史状态已停用（原记录：本文件是 33 全卷修复候选，非旧父稿副本。）；当前状态以 conversion_manifest.json 与验收回执为准。
- parent_path: `DeepSeek_政治题库资料库_20260918/questions/BJ-2024-DC-ERMO/BJ-2024-DC-ERMO-Q12.md`
- parent_sha256: `e3590a8b85df1cb8e80d4896cf2f6cb730300873bce6c4b682423d2ccf16c2d9`
- repair_support: [support.json](sources/support_32_q1_q15/support.json)（Q12）
- repair_support_sha256: `c0ba997a2e26e4ff88b8c0c98f0a71bc02b0611d486113cf4426e9a399204837`
- 已验收修订范围: 原卷题面、题号/分值、图表/框线/拓扑已从 32 视觉支持补入；旧父稿仅保留为身份回溯，不作为题面。

## 来源角色：ORIGINAL_QUESTION（原卷视觉回源）
- source_pdf: [paper.pdf](sources/legacy_30_sources/originals/paper.pdf)；physical_page=P04；printed_score=3
- page_asset: [P04.png](assets/visual_support/q1_q15/pages/P04.png)
- crop_asset: [Q12.png](assets/visual_support/q1_q15/crops/Q12.png)
- crop_sha256: `3413eaf170227eb67d8888d94c5eaaf9aff875ef4adaaa754ab4f401be61ebeb`
- source_role_boundary: 仅用于题面；不含答案或正式评分推断。

### 原卷逐项转写

#### stem
无人机穿行在高楼大厦间送外卖，“空中的士”成为出行新选择，农业无人机春耕显身手……当前，“低空经济”应用场景不断扩展。

#### diagram_title
中国“低空经济”产业链

#### diagram
- **columns**:
  - {'heading': '上游', 'items': ['钢材、工程塑料、碳纤维、复合材料', '芯片、电池、电机、陀螺', '……']}
  - {'heading': '中游', 'items': ['无人机、传感器、航空器', '高端设备、数据处理、指挥系统', '……']}
  - {'heading': '下游', 'items': ['低空＋物流', '低空＋农业', '低空＋旅游', '低空＋应急', '……']}
- **topology**: 上游 → 中游 → 下游；两个实心右箭头位于相邻框之间。

#### stem_question
促进“低空经济”发展，下列说法正确的是

#### statements
- ①推动中游相关配套设施建设，以降低中游企业生产成本
- ②政府完善相关政策法规，优化“低空经济”服务
- ③强化产学研深度融合，以创新提升价值链
- ④推广“低空＋”应用场景，进而在上游占领“低空经济”产业链高地

#### options
- **A**: ①②
- **B**: ①④
- **C**: ②③
- **D**: ③④

### 图表/框线/拓扑结构
- 标题居中；三列等高矩形框横向并列，框顶有独立表头横线；列间为向右实心箭头。
- 每列为项目符号列表并保留省略号；上游/中游项目有行内换行；下游含4个‘低空＋’场景。
- 图下接题干、四条圆圈序号陈述和A-D横向选项；不能把图表内容并入题干普通段落。

### 视觉修正/未决
- 
- OCR中的‘低空十’应按图回源为全角加号‘低空＋’；‘航空器’、‘碳纤维’、‘指挥系统’须完整保留。
- 保留三栏表格和两个右向箭头；以 diagram + stem/stements 全量替换；score=3；插入 Q12_industry_chain 资产；答案字段不动。

## 来源角色：ANSWER_KEY（保留的旧答案源）
- 该答案字段来自 30 包评分扫描视觉答案键，不来自 32 视觉支持；只作为答案角色保留，不升级为题面或评分槽。
- answer_key: `C`
- scoring_status: `choice_answer_key_only`; 每题分值由原卷首部统一确定为3，未由答案键拆分评分槽。

## 来源角色：STUDENT_LAYER
- 选择题支持包和原始题源未发现学生答卷/评分截图；本题 `N/A_with_basis`。

## 整合护栏
- 不修正答案、不把图中装饰微字臆补为题面、不扁平化地图/虚线框/图表/箭头结构。
