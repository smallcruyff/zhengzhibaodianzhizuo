# BJ-2025-DC-ERMO source-support delta 独立复核

结论：**PASS**（仅针对本 source-support delta；不等于整卷题库已验收）。

复核范围：`source_support_delta_20260922/` 内的原 PDF、13 张页图、Q3 图、转写层、卷首说明、页/题映射、SHA 锁和回执链。复核只读；本回执仅写入本目录的 `review/`。

## 复核结果

1. **两原 PDF**：主卷与桌面原件 SHA 均为 `9b287871f660f23de9593be4c16952103c1c6873d6bd52d25ddd1a8d268`，575180 bytes、8 页；正式评分材料与桌面原件 SHA 均为 `606dbae1d5ce3e59c8daef227c8b797cfbda2b7f90b8c9e07f47654af13e1cc2`，327662 bytes、5 页。两份均通过 fresh SHA/页数核验。

2. **13 页图与实际视觉打开**：8 张主卷页图、5 张评分页图均为有效 PNG、可读，并与已核缓存 `receipts/repair_2025_dc_ermo/rendered/paper/`、`rendered/rubric/` 逐字节一致（13/13）。实际打开了全部 13 页及 Q3 独立图；其中卷首主卷 p001、Q3 图、主卷 p004/p007/p008、评分 p001/p003/p005 均已实际打开，未见裁切、缺页或不可读区域。

3. **卷首与印刷说明**：`transcriptions/frontmatter_and_printed_instructions.md` 与主卷 p001、p004 视觉锚点逐字对照通过，包括“2025 北京东城高三二模”、2025.5、8 页/100 分/90 分钟、答题卡说明、第一部分 15 题/45 分和第二部分 6 题/55 分。

4. **转写层**：主卷 native、cleaned、layout 均覆盖 8 页；评分 native、cleaned、layout 均覆盖 5 页。缓存原生层保留提取字面，cleaned 是按页完整清洗稿，layout 用于版面/跨页辅助；三者均明确**不是视觉真值**。最终视觉依据是原 PDF 与 13 张页图，未用转写层替代视觉核验。

5. **页/题映射与证据角色**：`source_index.json.page_role_map` 覆盖主卷 p001–p008 与评分 p001–p005，跨页题边界已登记。主卷 p007 是内嵌 E3 答案、p008 是内嵌 E3/等级材料，均明确不是独立答案、不是正式 E1；评分 p001–p005 保持 formal E1/aggregate report 角色。Q20/Q21 的 p008 等级材料未与评分 PDF 混淆。

6. **Q3 图**：`assets/figures/Q3_painting_caption.png` SHA 为 `062372bfc740b349808db71e222f939b7015d4c8c973155030f62a466dfa5008`，与既有父资产一致。视觉打开确认图下注名为“张京生　王元珍”，题名为《没有共产党就没有新中国》；仅作图字定位，不改 Q3 正文。

7. **Q17 分层**：p004 视觉读法与 native 异常并列保留：视觉“输送、偏远地区／随申办／诉讼指引／网上立案／一体化办案办公平台”，native 原样“輸送、仙远地区／随中办／诉让指引／网上立電／一体化办素办公平台”。“线上十远程”按原页保留。没有把 native 异常静默修成视觉层，也没有反向把视觉读法降为 native。

8. **当前共享题 SHA**：当前共享 `BJ-2025-DC-ERMO` 题文件 21/21 存在，逐题实际 SHA 与 `source_index.json.current_shared_question_sha256` 全部一致（21/21，无 mismatch）。Q18 当前 SHA 为 `9e1ef21c6736a43c20781080e82fc64fdb41b88349d21153f1ca4e96b16dd64b`，与 `new_controller_20260922/BJ-2025-DC-ERMO_Q18_current_metadata_acceptance.json` 接受回执一致；该回执明确是等价元数据措辞接受，不是本次改题，也未重跑旧 materialize。

9. **回执链**：5 条路径均存在，实际 SHA 与 `source_index.json.receipt_chain` 登记值一致：repair checkpoint、remaining completion、legacy materialize verification、current consolidated signoff、Q18 controller acceptance。路径与 SHA 均通过。

10. **学生层**：独立答案文件标为 `not_provided`；学生原答、错误/遗漏/涂改、教师批注、评分标记、逐生实得分均为 `source_not_provided`。评分材料中的聚合阅卷报告未被冒充为学生层；delta 内没有学生源件。

11. **写入边界与 materialize 守卫**：delta 内题目 MD 数量为 0；没有题目 MD、生产脚本或 materialize 产物写入本 delta。`source_index.json` 与 `validation.json` 均登记未修改共享题库、索引、manifest、原 PDF、旧 materialization；payload 27 项树 SHA 独立重算为 `8ee3d280f380b2441a330d0c7428df552400d9ebf42964a17531568bb64afda7`，与生产验证一致。

## 边界说明

本回执只证明 source-support delta 的来源、页图、转写层、映射、回执链和 SHA 守卫通过；不把独立答案源或学生层缺失改称通过。既有 consolidated signoff 对整卷仍记为 `UNCERTAIN_CONTROLLER_MANUAL_ADJUDICATION`，本回执不改变该整卷边界，也不宣称整卷已验收。

详细逐项指纹、页图清单、Q17 变体、21 题 SHA 和写入边界见同目录 [verification.json](verification.json)。
