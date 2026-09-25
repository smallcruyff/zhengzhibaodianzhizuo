# BJ-2024-DC-ERMO-Q1

## 修复身份
- source_provenance: [provenance_registry.md](sources/provenance_registry.md)
- 历史状态已停用（原记录：本文件是 33 全卷修复候选，非旧父稿副本。）；当前状态以 conversion_manifest.json 与验收回执为准。
- parent_path: `DeepSeek_政治题库资料库_20260918/questions/BJ-2024-DC-ERMO/BJ-2024-DC-ERMO-Q1.md`
- parent_sha256: `3336234b62721f8c11f760344ab86dd171fb28de7750415fda67d5ebdcd73270`
- repair_support: [support.json](sources/support_32_q1_q15/support.json)（Q01）
- repair_support_sha256: `c0ba997a2e26e4ff88b8c0c98f0a71bc02b0611d486113cf4426e9a399204837`
- 已验收修订范围: 原卷题面、题号/分值、图表/框线/拓扑已从 32 视觉支持补入；旧父稿仅保留为身份回溯，不作为题面。

## 来源角色：ORIGINAL_QUESTION（原卷视觉回源）
- source_pdf: [paper.pdf](sources/legacy_30_sources/originals/paper.pdf)；physical_page=P01；printed_score=3
- page_asset: [P01.png](assets/visual_support/q1_q15/pages/P01.png)
- crop_asset: [Q01.png](assets/visual_support/q1_q15/crops/Q01.png)
- crop_sha256: `43b27270299533950d639335b4eaa3f5453918c6f9bcae3e27db9d9c4ce2c427`
- source_role_boundary: 仅用于题面；不含答案或正式评分推断。

### 原卷逐项转写

#### figure_caption
北京市“大思政课”实践教学基地数字地图

#### figure_text
- **quote_box**: “大思政课”我们要善用之，一定要跟现实结合起来。思政课不仅应该在课堂上讲，也应该在社会生活中来讲。把思政小课堂同社会大课堂结合起来。——习近平
- **slogan**:
  - 网页跳转，历史文化跃然眼前
  - 指尖轻点，思政奥妙纷至沓来
- **map_labels**:
  - 延庆区
  - 怀柔区
  - 密云区
  - 昌平区
  - 平谷区
  - 海淀区
  - 顺义区
  - 门头沟区
  - 石景山区
  - 东城区
  - 西城区
  - 朝阳区
  - 丰台区
  - 通州区
  - 房山区
  - 大兴区
- **feature_labels**:
  - 实践教学基地
  - 生动实践
  - 数字展馆
  - 虚拟展馆
  - 北京中轴线
  - 北大红楼
  - 中国抗日战争纪念馆
  - 香山革命纪念地
  - 八达岭长城
- **legend_and_counts**:
  - 16区
  - 200余个
  - 全市
  - 实践教学基地

#### material
前门议事厅、12345市民热线服务中心、北京国子监博物馆、北大红楼……目前，在北京市“大思政课”实践教学基地数字地图上，分布于全市16区的200余个实践教学基地已全部点亮。这一举措

#### statements
- ①联通过去与未来，丰富首都文化内涵
- ②实现数字赋能传统教育，提供差异化公共文化服务
- ③激活京华大地鲜活课堂，为“大思政课”注入源头活水
- ④强化实践资源供给，启智润心，引领学生成长与时代发展同频共振

#### options
- **A**: ①②
- **B**: ①③
- **C**: ②④
- **D**: ③④

### 图表/框线/拓扑结构
- 题号在图框左上外侧。
- 题面主体为虚线外框；左上为圆角引用框；右上为两行宣传语。
- 中央为北京市地图，标出16区和多个定位图钉；四周有实践教学基地/展馆/文化场所的引线气泡与装饰性图片。
- 底部有16区、200余个两个数量标签及全市/实践教学基地两个图例按钮；无坐标轴。

### 视觉修正/未决
- 左侧书封、网页缩略图及右下文化图片中的微小装饰文字在原始栅格图中不宜逐字采用；已保留原图裁切，题干有效标签已逐字回源。
- 
- 以本对象 transcription 全量替换题面；score=3；插入/保留 Q01_map_material 资产；答案字段不动。

## 来源角色：ANSWER_KEY（保留的旧答案源）
- 该答案字段来自 30 包评分扫描视觉答案键，不来自 32 视觉支持；只作为答案角色保留，不升级为题面或评分槽。
- answer_key: `D`
- scoring_status: `choice_answer_key_only`; 每题分值由原卷首部统一确定为3，未由答案键拆分评分槽。

## 来源角色：STUDENT_LAYER
- 选择题支持包和原始题源未发现学生答卷/评分截图；本题 `N/A_with_basis`。

## 整合护栏
- 不修正答案、不把图中装饰微字臆补为题面、不扁平化地图/虚线框/图表/箭头结构。
