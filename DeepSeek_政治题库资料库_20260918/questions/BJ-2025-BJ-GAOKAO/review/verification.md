# BJ-2025-BJ-GAOKAO 有界候选独立复核 v2

## 结论

**有界隔离候选：PASS；整卷来源闭环：BLOCKED；controller_ready=false。**

本复核只裁决当前允许的有界角色，不把教师版冒充独立原卷，不把教师版答案冒充独立答案或正式 E1，不把 S132 候选分值回填原卷。Q1–Q21 均可作为有界候选保留；这不等于整卷原卷验收通过。

## 实际查看范围

- S44 教师版 p1–p21：全部实际打开。p1–p8 按 E0 题面核，p9–p21 按 E3 参考答案/解析核。
- S132 评分候选 p1–p6：全部实际打开。仅把 Q16–Q21 记为 E1_candidate_pending，不升格正式 E1。
- Q21 候选：实际核读 candidates/BJ-2025-BJ-GAOKAO-Q21.md，并打开 p8 原页图。
- 重点图文实际核对：Q1 五列表、Q5 三性质图、Q9 正文/附件结构图、Q12 五线折线图、Q14 离岸贸易流程图、Q16 插图、Q17 六年时间线、Q19 双轴柱线图、Q20 五行跨页表、Q21 人物分栏表。

## 有界规则裁决

| 范围 | E0 | E1 | 分值 | 结论 |
|---|---|---|---|---|
| Q1–Q15 | teacher_version_bounded_E0; independent_original_exam_missing | N/A_objective | 仅教师版 p1 第一部分题头每题 3 分 | PASS；可保留有界包 |
| Q16–Q21 | teacher_version_bounded_E0; independent_original_exam_missing | E1_candidate_pending，不得正式化 | N/A/uncertain | PASS；可保留有界包，不能原卷化 |
| Q19 | 同上 | candidate pending | 父稿“1分”排除；图首柱保留 10246.5 | PASS；不得用 1 分 |
| Q20 | 同上 | candidate pending | 候选“8分”排除 | PASS；不得用 8 分作原印分值 |

## 逐题状态

这里的 PASS 指“在上述有界角色下通过”，不表示独立原卷或正式细则来源已经闭合。

| 题 | 状态 | 有界包允许 | 复核要点 |
|---:|---|---|---|
| Q1 | PASS | 是 | 五列表头、人民地点、照片、边框和顺序一致；答案 B 留在 E3。 |
| Q2 | PASS | 是 | 题干、四判断、A–D 完整；E1 为 N/A_objective。 |
| Q3 | PASS | 是 | p1–p2 跨页题干与选项完整；答案 C 未进入 E0。 |
| Q4 | PASS | 是 | 题干和四选项完整；答案 D 仅作 E3。 |
| Q5 | PASS | 是 | “所有/有些”三性质图文字、鱼图、虚线框/气泡布局一致。 |
| Q6 | PASS | 是 | 题干、选项、E0/E3分栏正确。 |
| Q7 | PASS | 是 | 跨页题干和选项完整；未串入答案解析。 |
| Q8 | PASS | 是 | 民族团结材料、四判断和 A–D 完整。 |
| Q9 | PASS | 是 | 正文/附件分组、五正文项、三附件项及框线/箭头均按 p3 核对。 |
| Q10 | PASS | 是 | 法律材料、四选项和 E3 答案完整。 |
| Q11 | PASS | 是 | 遗嘱材料、四选项和 E3 答案完整。 |
| Q12 | PASS | 是 | 纵轴 0–14、横轴 2020–2023、五系列图例/标记、近似趋势和点位与 p4 一致；未冒称无标签点位为原印数值。 |
| Q13 | PASS | 是 | 商业航天材料、四判断、A–D 完整。 |
| Q14 | PASS | 是 | “输出中国货→整合全球货”、两框主体、货/资金流箭头、境内外边界、数字化平台和离岸贸易商标签一致。 |
| Q15 | PASS | 是 | 智慧农业出海材料、四判断、选项及第二部分分界完整。 |
| Q16 | PASS | 是 | 兔儿爷三段材料和 p6 插图完整；装饰图字未虚构为设问；评分仍 pending。 |
| Q17 | PASS | 是 | 时间线为 1954→1987→2007→2019→2021→2024，箭头左向右；上下框分组及六框文字完整。 |
| Q18 | PASS | 是 | 两则材料、两小问、跨页连续性完整；S132 不升格正式评分。 |
| Q19 | PASS | 是 | 双轴刻度、图例、方向及柱/线数值一致，首柱为 10246.5；父稿 1 分排除。 |
| Q20 | PASS | 是 | 团结、发展、文明、和平、民心五行及 p7→p8 设问接续完整；候选 8 分排除。 |
| Q21 | PASS | 是 | 教师/同学甲/同学乙三行、多列框线、人物标签、◇资料分组和设问与 p8 一致；候选 10 分不原印化。 |

## SHA 与链接

- S44 教师版候选副本、桌面原件和共同资料镜像均为：
  44eade2b04f87c55a788e0865e5457d884abfda002caf78f19626939aa29579d
- S132 评分候选副本和桌面原件均为：
  132a504a16fee0fa8febdbd4681c7e1c99e8d2c0260f7ac8b91cf41939e1ce7c
- source_boundary_v2 四文件逐字节匹配候选副本：
  inventory.json=67877bed…5831c8、inventory.md=838a0405…c5d31、production_recommendation.json=bc233e16…c0695、source_matrix.json=1286f2f9…d79e2。
- 候选树 SHA 均与 candidate_manifest 匹配：候选题文件、assets、sources、coverage 分别为
  b2574c1f…d8127、f0e70559…809e6、212f0f83…2c49、e1591bec…cd368b。
- 21/21 父题稿逐文件 SHA 与 source_boundary、source_matrix、question_layers 一致；21/21 候选题 SHA 一致；Markdown 本地链接 37/37 通过，断链 0。
- 历史 source_boundary 中记录的父树摘要为 f36d7785…fd005，按当前候选 rel_tree_sha 函数重算为 26f4e37f…4dfd1；但 21/21 单文件 SHA 全部一致，因此不将该不可复现的历史树摘要单独判为父稿内容漂移。

## 共享写入安全与未决

本轮只写入本目录的 verification.json 和 verification.md。未改 candidate、父稿、共享题库、indexes、conversion_manifest.json、原始 PDF 或 source_boundary。

questions.csv 与 rubric_links.csv 当前 SHA 相对 source_boundary 快照存在只读漂移；该差异被记录为 snapshot/concurrent drift，不能归因于本复核工位，也不据此改写共享文件。

由于独立原卷缺失、Q16–Q21 正式 E1 和原印分值未闭合，本包只能作为 bounded/blocked_on_source 隔离候选交总控；不得称整卷完成、不得晋升 controller_ready。
