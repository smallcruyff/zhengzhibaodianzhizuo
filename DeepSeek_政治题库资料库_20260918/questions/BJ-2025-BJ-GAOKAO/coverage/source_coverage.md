# BJ-2025-BJ-GAOKAO bounded candidate source coverage

"
"本包是 `bounded/blocked_on_source` 隔离候选，不是原卷闭环，也不是 `controller_ready`。

"
"## 角色边界

"
"- E0：仅教师版 S44 p1–p8 题面及同页视觉对象；答案/解析从E0切断。
"
"- E3：仅教师版 S44 p9–p21 参考答案层，独立答案文件缺失。
"
"- E1：Q1–Q15 为 `N/A_objective`；Q16–Q21 仅 `E1_candidate_pending`，不写正式E1、固定槽位或候选分值。
"
"- 分值：Q1–Q15 可保留教师版p1第一部分题头的每题3分；Q16–Q21 `N/A/uncertain`。Q19父稿1分不采，Q20候选8分不作原印分值。

"
"## 视觉重点

"
"Q1五列表、Q5三性质图、Q9意见结构图、Q12宏观指标图、Q14离岸贸易流程图、Q16插图、Q17六年时间线、Q19双轴柱线图、Q20五行表、Q21人物分栏表均保留原页图及逐题结构转写。

"
"## 只读快照

"
"题库父稿、questions.csv、rubric_links.csv、source_manifest.csv 均只读复制到本包，未修改共享路径。

## r2来源覆盖补充：34项活动页图像

以下链接逐项指向本候选包中的图像文件：S44教师版21张原页图、S132评分材料候选5张活动页图、以及S44题面8张图表/图像裁图。S132 p6仅为空白/页码页，不计入活动页。题号列表示该页/图像实际覆盖范围；角色列保留E0、E3和E1_candidate_pending边界。

| # | 可点击图像 | 来源页位 | 覆盖题号 | 来源角色 |
| ---: | --- | --- | --- | --- |
| 1 | [S44 p1原页图](../assets/source_pages/p001.png) | S44 PDF p1 | Q1, Q2, Q3 | S44教师版混合载体；E0教师版有界题面页 |
| 2 | [S44 p2原页图](../assets/source_pages/p002.png) | S44 PDF p2 | Q3, Q4, Q5, Q6, Q7 | S44教师版混合载体；E0教师版有界题面页 |
| 3 | [S44 p3原页图](../assets/source_pages/p003.png) | S44 PDF p3 | Q7, Q8, Q9, Q10 | S44教师版混合载体；E0教师版有界题面页 |
| 4 | [S44 p4原页图](../assets/source_pages/p004.png) | S44 PDF p4 | Q10, Q11, Q12, Q13, Q14 | S44教师版混合载体；E0教师版有界题面页 |
| 5 | [S44 p5原页图](../assets/source_pages/p005.png) | S44 PDF p5 | Q14, Q15, Q16 | S44教师版混合载体；E0教师版有界题面页 |
| 6 | [S44 p6原页图](../assets/source_pages/p006.png) | S44 PDF p6 | Q16, Q17, Q18 | S44教师版混合载体；E0教师版有界题面页 |
| 7 | [S44 p7原页图](../assets/source_pages/p007.png) | S44 PDF p7 | Q18, Q19, Q20 | S44教师版混合载体；E0教师版有界题面页 |
| 8 | [S44 p8原页图](../assets/source_pages/p008.png) | S44 PDF p8 | Q20, Q21 | S44教师版混合载体；E0教师版有界题面页 |
| 9 | [S44 p9原页图](../assets/source_pages/p009.png) | S44 PDF p9 | Q1, Q2, Q3 | S44教师版混合载体；E3参考答案/解析页 |
| 10 | [S44 p10原页图](../assets/source_pages/p010.png) | S44 PDF p10 | Q3, Q4, Q5, Q6 | S44教师版混合载体；E3参考答案/解析页 |
| 11 | [S44 p11原页图](../assets/source_pages/p011.png) | S44 PDF p11 | Q6, Q7, Q8, Q9 | S44教师版混合载体；E3参考答案/解析页 |
| 12 | [S44 p12原页图](../assets/source_pages/p012.png) | S44 PDF p12 | Q9, Q10, Q11, Q12 | S44教师版混合载体；E3参考答案/解析页 |
| 13 | [S44 p13原页图](../assets/source_pages/p013.png) | S44 PDF p13 | Q12, Q13, Q14 | S44教师版混合载体；E3参考答案/解析页 |
| 14 | [S44 p14原页图](../assets/source_pages/p014.png) | S44 PDF p14 | Q14, Q15, Q16 | S44教师版混合载体；E3参考答案/解析页 |
| 15 | [S44 p15原页图](../assets/source_pages/p015.png) | S44 PDF p15 | Q16, Q17 | S44教师版混合载体；E3参考答案/解析页 |
| 16 | [S44 p16原页图](../assets/source_pages/p016.png) | S44 PDF p16 | Q17, Q18 | S44教师版混合载体；E3参考答案/解析页 |
| 17 | [S44 p17原页图](../assets/source_pages/p017.png) | S44 PDF p17 | Q18 | S44教师版混合载体；E3参考答案/解析页 |
| 18 | [S44 p18原页图](../assets/source_pages/p018.png) | S44 PDF p18 | Q18, Q19 | S44教师版混合载体；E3参考答案/解析页 |
| 19 | [S44 p19原页图](../assets/source_pages/p019.png) | S44 PDF p19 | Q19, Q20 | S44教师版混合载体；E3参考答案/解析页 |
| 20 | [S44 p20原页图](../assets/source_pages/p020.png) | S44 PDF p20 | Q20, Q21 | S44教师版混合载体；E3参考答案/解析页 |
| 21 | [S44 p21原页图](../assets/source_pages/p021.png) | S44 PDF p21 | Q21 | S44教师版混合载体；E3参考答案/解析页 |
| 22 | [S132 p1页图](../assets/rubric_pages/p001.png) | S132 PDF p1 | Q16, Q17 | 评分材料候选；E1_candidate_pending，非正式E1 |
| 23 | [S132 p2页图](../assets/rubric_pages/p002.png) | S132 PDF p2 | Q17, Q18 | 评分材料候选；E1_candidate_pending，非正式E1 |
| 24 | [S132 p3页图](../assets/rubric_pages/p003.png) | S132 PDF p3 | Q18 | 评分材料候选；E1_candidate_pending，非正式E1 |
| 25 | [S132 p4页图](../assets/rubric_pages/p004.png) | S132 PDF p4 | Q18, Q19, Q20 | 评分材料候选；E1_candidate_pending，非正式E1 |
| 26 | [S132 p5页图](../assets/rubric_pages/p005.png) | S132 PDF p5 | Q20, Q21 | 评分材料候选；E1_candidate_pending，非正式E1 |
| 27 | [题面图像 Q1_five_column_table_source_p001.png](../assets/figures/Q1_five_column_table_source_p001.png) | S44 p1 | Q1 | E0五列表格图像 |
| 28 | [题面图像 Q5_three_property_diagram_source_p002.png](../assets/figures/Q5_three_property_diagram_source_p002.png) | S44 p2 | Q5 | E0三性质图像 |
| 29 | [题面图像 Q9_opinion_structure_source_p003.png](../assets/figures/Q9_opinion_structure_source_p003.png) | S44 p3 | Q9 | E0意见结构图像 |
| 30 | [题面图像 Q12_macro_indicators_source_p004.png](../assets/figures/Q12_macro_indicators_source_p004.png) | S44 p4 | Q12 | E0宏观指标图像 |
| 31 | [题面图像 Q14_offshore_trade_flow_source_p005.png](../assets/figures/Q14_offshore_trade_flow_source_p005.png) | S44 p5 | Q14 | E0离岸贸易流程图像 |
| 32 | [题面图像 Q16_Q17_source_p006.png](../assets/figures/Q16_Q17_source_p006.png) | S44 p6 | Q16, Q17 | E0兔儿爷插图/时间线图像 |
| 33 | [题面图像 Q19_Q20_source_p007.png](../assets/figures/Q19_Q20_source_p007.png) | S44 p7 | Q19, Q20 | E0图表/表格题面图像 |
| 34 | [题面图像 Q20_Q21_source_p008.png](../assets/figures/Q20_Q21_source_p008.png) | S44 p8 | Q20, Q21 | E0跨页表格/人物分栏题面图像 |

边界提示：S44是教师版混合载体，p1–p8为题面区，p9–p21为参考答案/解析区；它不是独立原卷。S132仍为评分材料候选，Q16–Q21的E1保持E1_candidate_pending。
