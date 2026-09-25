# BJ-2024-DC-ERMO-Q13

## 修复身份
- source_provenance: [provenance_registry.md](sources/provenance_registry.md)
- 历史状态已停用（原记录：本文件是 33 全卷修复候选，非旧父稿副本。）；当前状态以 conversion_manifest.json 与验收回执为准。
- parent_path: `DeepSeek_政治题库资料库_20260918/questions/BJ-2024-DC-ERMO/BJ-2024-DC-ERMO-Q13.md`
- parent_sha256: `30e18dbe719f6019017d98f38882f616b374d1e19fb1351e472fa739526688e3`
- repair_support: [support.json](sources/support_32_q1_q15/support.json)（Q13）
- repair_support_sha256: `c0ba997a2e26e4ff88b8c0c98f0a71bc02b0611d486113cf4426e9a399204837`
- 已验收修订范围: 原卷题面、题号/分值、图表/框线/拓扑已从 32 视觉支持补入；旧父稿仅保留为身份回溯，不作为题面。

## 来源角色：ORIGINAL_QUESTION（原卷视觉回源）
- source_pdf: [paper.pdf](sources/legacy_30_sources/originals/paper.pdf)；physical_page=P05；printed_score=3
- page_asset: [P05.png](assets/visual_support/q1_q15/pages/P05.png)
- crop_asset: [Q13.png](assets/visual_support/q1_q15/crops/Q13.png)
- crop_sha256: `ee9f3bab95476007eb2df0588deb8926f0670a98455a35666013a01321c49163`
- source_role_boundary: 仅用于题面；不含答案或正式评分推断。

### 原卷逐项转写

#### chart_title
2019—2023年中国常住人口城镇化率

#### chart
- **y_axis_label**: (%)
- **y_axis_ticks**:
  - 60
  - 62
  - 64
  - 66
  - 68
  - 70
- **x_axis_years**:
  - 2019
  - 2020
  - 2021
  - 2022
  - 2023
- **x_axis_suffix**: （年）
- **points**:
  - **2019**: 62.71
  - **2020**: 63.89
  - **2021**: 64.72
  - **2022**: 65.22
  - **2023**: 66.16
- **series**: 单条折线，五个空心圆点，逐年上升；无图例。

#### stem
读上图，以下推断合理的是

#### statements
- ①农业劳动生产率不断提高，城乡融合推动协调发展
- ②促进农业适度规模经营，确保农村土地归集体所有
- ③区域发展差距正在逐步缩小，助力和美乡村建设
- ④推进以人为核心的新型城镇化，要建立健全基本公共服务制度

#### options
- **A**: ①②
- **B**: ①④
- **C**: ②③
- **D**: ③④

### 图表/框线/拓扑结构
- 折线图置于题干上方；纵轴范围60-70、刻度间隔2，不是从0起；横轴为2019-2023并在右侧标‘（年）’。
- 五个数据标签均在空心圆点上方；无图例、无方向箭头。

### 视觉修正/未决
- 
- 原OCR中的数值‘6472’、‘6231’等应按图回源为64.72、62.71；④为‘以人为核心’，不可漏‘为’。
- 保留图表为独立图块；以 chart 数值和题干全量替换；score=3；插入 Q13_line_chart 资产；答案字段不动。

## 来源角色：ANSWER_KEY（保留的旧答案源）
- 该答案字段来自 30 包评分扫描视觉答案键，不来自 32 视觉支持；只作为答案角色保留，不升级为题面或评分槽。
- answer_key: `B`
- scoring_status: `choice_answer_key_only`; 每题分值由原卷首部统一确定为3，未由答案键拆分评分槽。

## 来源角色：STUDENT_LAYER
- 选择题支持包和原始题源未发现学生答卷/评分截图；本题 `N/A_with_basis`。

## 整合护栏
- 不修正答案、不把图中装饰微字臆补为题面、不扁平化地图/虚线框/图表/箭头结构。
