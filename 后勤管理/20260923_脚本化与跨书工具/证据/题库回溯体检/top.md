# 回溯体检 TOP 差异（machine_diff，须人工看原页裁定）

> 证据等级：脚本比对差异，不是已核实错误；“已验收”也不等于主代理已核原页。
> 名次口径：按优先级排序后，同卷同题同一对（题库字→原件字）只保留一条，记“去重后第 N”；“未去重第 N”是去重前的位置。
> 题库文件行号为 1 起、指向差异所在的那一行；上下文里的〔前略〕〔后略〕表示窗口截断。

## 1. BJ-2026-FT-YIMO-Q16 漏字（e1｜正式评分细则层（E1；PPT slides 3–5））
- 名次：去重后第 1（未去重第 1）；题库：`∅` → 原件：`者`（评分材料 第3页，pptx_text，层级 native，行比 1.00，优先级 11.25）
- 题库上下文：或进一步阐述：坚持两点论与〔后略，全文见 questions/BJ-2026-FT-YIMO/BJ-2026-FT-YIMO-Q16.md:76〕
- 原件上下文：〔前略〕又要正视其带来的挑战。或者进一步阐述：坚持两点论与〔后略，全文见 2026模拟题/2026各区一模/2026丰台一模/细则/细则.pptx 第3页〕
- 题库文件行：questions/BJ-2026-FT-YIMO/BJ-2026-FT-YIMO-Q16.md:76；读取依据 heuristic_title；标记 cjk_short

## 2. BJ-2026-FT-YIMO-Q21 漏字（e1｜正式评分细则层（E1；PPT slides 61–64））
- 名次：去重后第 2（未去重第 2）；题库：`∅` → 原件：`试`（评分材料 第63页，pptx_text，层级 native，行比 1.00，优先级 11.25）
- 题库上下文：〔前略〕分：应答与试题无关，重复题内容，摘抄材料，空白卷〔后略，全文见 questions/BJ-2026-FT-YIMO/BJ-2026-FT-YIMO-Q21.md:109〕
- 原件上下文：〔前略〕分:应答与试题无关，重复试题内容，摘抄材料，空白卷〔后略，全文见 2026模拟题/2026各区一模/2026丰台一模/细则/细则.pptx 第63页〕
- 题库文件行：questions/BJ-2026-FT-YIMO/BJ-2026-FT-YIMO-Q21.md:109；读取依据 heuristic_title；标记 cjk_short

## 3. BJ-2025-BJ-GAOKAO-Q18 错字（stem｜E0教师版有界题面（不含答案/解析））
- 名次：去重后第 3（未去重第 3）；题库：`接` → 原件：`换`（教师版 第6页，text_plus_figure，层级 native，行比 0.99，优先级 11.17）
- 题库上下文：〔前略〕前，在医疗健康领域，脑机接口为神经系统疾病患者带来〔后略，全文见 questions/BJ-2025-BJ-GAOKAO/BJ-2025-BJ-GAOKAO-Q18.md:26〕
- 原件上下文：〔前略〕前，在医疗健康领域，脑机换口为神经系统疾病患者带来〔后略，全文见 历年高考题及细则/2025北京高考真题政治（教师版）.pdf 第6页〕
- 题库文件行：questions/BJ-2025-BJ-GAOKAO/BJ-2025-BJ-GAOKAO-Q18.md:26；读取依据 heuristic_no_default_stem；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-BJ-GAOKAO-Q18_p006_44c259.png

## 4. BJ-2025-FT-ERMO-Q16 错字（stem｜题目原文（原卷·native，修复候选））
- 名次：去重后第 4（未去重第 4）；题库：`锔` → 原件：`铜`（原卷 第5页，text_reliable，层级 native，行比 0.99，优先级 11.16）
- 题库上下文：〔前略〕丝路驼铃。设专项资金，令锔瓷点金、面花塑彩等古艺重〔后略，全文见 questions/BJ-2025-FT-ERMO/BJ-2025-FT-ERMO-Q16.md:18〕
- 原件上下文：〔前略〕丝路驼铃。设专项资金，令铜瓷点金、面花塑彩等古艺重〔后略，全文见 2025模拟题/2025各区二模/2025丰台二模/试卷/试卷.pdf 第5页〕
- 题库文件行：questions/BJ-2025-FT-ERMO/BJ-2025-FT-ERMO-Q16.md:18；读取依据 bank_default；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-FT-ERMO-Q16_p005_06b8d4.png

## 5. BJ-2020-BJ-GAOKAO-Q16 错字（stem｜题面（教师版混合载体 p1-p7 的原卷区，已逐页视觉核对））
- 名次：去重后第 5（未去重第 5）；题库：`千` → 原件：`干`（教师版 第5页，text_plus_figure，层级 native，行比 0.98，优先级 11.03）
- 题库上下文：〔前略〕青黑色，松柏“黛色参天二千尺”，远山“遥看黛色知何
- 原件上下文：〔前略〕青黑色，松柏“黛色参天二干尺”，远山“遥看黛色知何〔后略，全文见 历年高考题及细则/2020北京高考真题政治（教师版）.pdf 第5页〕
- 题库文件行：questions/BJ-2020-BJ-GAOKAO/BJ-2020-BJ-GAOKAO-Q16.md:14；读取依据 heuristic_no_default_stem；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2020-BJ-GAOKAO-Q16_p005_1fd115.png

## 6. BJ-2025-DC-ERMO-Q17 错字（stem｜题目原文（原卷 p004；视觉复核，不静默规范化））
- 名次：去重后第 6（未去重第 6）；题库：`输` → 原件：`輸`（原卷 第4页，text_reliable，层级 native，行比 0.98，优先级 11.03）
- 题库上下文：〔前略〕个，将城区优质法治资源“输送”到偏远地区。
- 原件上下文：〔前略〕个，将城区优质法治资源“輸送”到仙远地区。点开上海〔后略，全文见 2025模拟题/2025各区二模/2025东城二模/试卷/试卷.pdf 第4页〕
- 题库文件行：questions/BJ-2025-DC-ERMO/BJ-2025-DC-ERMO-Q17.md:18；读取依据 bank_default；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-DC-ERMO-Q17_p004_dee169.png

## 7. BJ-2025-DC-ERMO-Q17 错字（stem｜题目原文（原卷 p004；视觉复核，不静默规范化））
- 名次：去重后第 7（未去重第 7）；题库：`偏` → 原件：`仙`（原卷 第4页，text_reliable，层级 native，行比 0.98，优先级 11.03）
- 题库上下文：〔前略〕区优质法治资源“输送”到偏远地区。
- 原件上下文：〔前略〕区优质法治资源“輸送”到仙远地区。点开上海"随中办〔后略，全文见 2025模拟题/2025各区二模/2025东城二模/试卷/试卷.pdf 第4页〕
- 题库文件行：questions/BJ-2025-DC-ERMO/BJ-2025-DC-ERMO-Q17.md:18；读取依据 bank_default；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-DC-ERMO-Q17_p004_0d7717.png

## 8. BJ-2025-DC-QIMO-Q4 错字（stem｜题目原文（原卷·逐页对照））
- 名次：去重后第 8（未去重第 8）；题库：`摹` → 原件：`蔡`（原卷 第1页，text_reliable，层级 native，行比 0.98，优先级 11.00）
- 题库上下文：〔前略〕云，亦可繁复多画，耐心描摹，笔画的主次、长短、布局〔后略，全文见 questions/BJ-2025-DC-QIMO/BJ-2025-DC-QIMO-Q4.md:27〕
- 原件上下文：〔前略〕云，亦可繁复多画，耐心描蔡，笔画的主次、长短、布局〔后略，全文见 2025模拟题/2025各区期末/2025东城期末/试卷/试卷.pdf 第1页〕
- 题库文件行：questions/BJ-2025-DC-QIMO/BJ-2025-DC-QIMO-Q4.md:27；读取依据 heuristic_no_default_stem；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-DC-QIMO-Q4_p001_c2b9ac.png

## 9. BJ-2025-DC-ERMO-Q18 错字（e1｜正式评分材料原文（rubric:p002–p003；完整重配…〔截断〕）
- 名次：去重后第 9（未去重第 9）；题库：`地` → 原件：`的`（评分材料 第3页，text_reliable，层级 native，行比 0.98，优先级 10.99）
- 题库上下文：1.引导学生有意识地全面辨析、评价某一观点，〔后略，全文见 questions/BJ-2025-DC-ERMO/BJ-2025-DC-ERMO-Q18.md:127〕
- 原件上下文：〔前略〕学启示1.引导学生有意识的全面辨析、评价某一观点，〔后略，全文见 2025模拟题/2025各区二模/2025东城二模/细则/细则.pdf 第3页〕
- 题库文件行：questions/BJ-2025-DC-ERMO/BJ-2025-DC-ERMO-Q18.md:127；读取依据 heuristic_title；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-DC-ERMO-Q18_p003_d54032.png

## 10. BJ-2025-DC-QIMO-Q18 错字（stem｜题目原文（原卷·逐页对照））
- 名次：去重后第 10（未去重第 10）；题库：`载` → 原件：`裁`（原卷 第5页，text_reliable，层级 native，行比 0.98，优先级 10.98）
- 题库上下文：〔前略〕十足的细节，将为我国首次载人登月任务的顺利实施保驾〔后略，全文见 questions/BJ-2025-DC-QIMO/BJ-2025-DC-QIMO-Q18.md:37〕
- 原件上下文：〔前略〕十足的细节，将为我国首次裁人登月任务的顺利实施保驾〔后略，全文见 2025模拟题/2025各区期末/2025东城期末/试卷/试卷.pdf 第5页〕
- 题库文件行：questions/BJ-2025-DC-QIMO/BJ-2025-DC-QIMO-Q18.md:37；读取依据 heuristic_no_default_stem；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-DC-QIMO-Q18_p005_830d46.png

## 11. BJ-2026-BJ-GAOKAO-Q10 错字（stem｜题面（Luna/max独立复核通过，verified））
- 名次：去重后第 11（未去重第 11）；题库：`获` → 原件：`取`（原卷 第4页，text_reliable，层级 native，行比 0.97，优先级 10.96）
- 题库上下文：〔前略〕的未成年人，应保障劳动者获得劳动报酬和休息休假权利
- 原件上下文：〔前略〕的未成年人，应保障劳动者取得劳动报酬和休息休假权利〔后略，全文见 历年高考题及细则/2026年普通高中学业水平等级性考试（思想政治）试题.pdf 第4页〕
- 题库文件行：questions/BJ-2026-BJ-GAOKAO/BJ-2026-BJ-GAOKAO-Q10.md:37；读取依据 bank_default；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2026-BJ-GAOKAO-Q10_p004_71403d.png

## 12. BJ-2025-DC-ERMO-Q17 错字（stem｜题目原文（原卷 p004；视觉复核，不静默规范化））
- 名次：去重后第 12（未去重第 12）；题库：`申` → 原件：`中`（原卷 第4页，text_reliable，层级 native，行比 0.97，优先级 10.86）
- 题库上下文：点开上海“随申办”平台，当事人就可以获〔后略，全文见 questions/BJ-2025-DC-ERMO/BJ-2025-DC-ERMO-Q17.md:20〕
- 原件上下文：〔前略〕到仙远地区。点开上海"随中办”平台，当事人就可以获〔后略，全文见 2025模拟题/2025各区二模/2025东城二模/试卷/试卷.pdf 第4页〕
- 题库文件行：questions/BJ-2025-DC-ERMO/BJ-2025-DC-ERMO-Q17.md:20；读取依据 bank_default；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-DC-ERMO-Q17_p004_04de7d.png

## 13. BJ-2025-DC-ERMO-Q17 错字（stem｜题目原文（原卷 p004；视觉复核，不静默规范化））
- 名次：去重后第 13（未去重第 13）；题库：`讼` → 原件：`让`（原卷 第4页，text_reliable，层级 native，行比 0.97，优先级 10.86）
- 题库上下文：〔前略〕平台，当事人就可以获得诉讼指引、案例参考、风险评估〔后略，全文见 questions/BJ-2025-DC-ERMO/BJ-2025-DC-ERMO-Q17.md:20〕
- 原件上下文：〔前略〕平台，当事人就可以获得诉让指引、案例参考、风险评估〔后略，全文见 2025模拟题/2025各区二模/2025东城二模/试卷/试卷.pdf 第4页〕
- 题库文件行：questions/BJ-2025-DC-ERMO/BJ-2025-DC-ERMO-Q17.md:20；读取依据 bank_default；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-DC-ERMO-Q17_p004_b900e1.png

## 14. BJ-2025-DC-ERMO-Q17 错字（stem｜题目原文（原卷 p004；视觉复核，不静默规范化））
- 名次：去重后第 14（未去重第 14）；题库：`案` → 原件：`電`（原卷 第4页，text_reliable，层级 native，行比 0.97，优先级 10.86）
- 题库上下文：〔前略〕院在2024年开展网上立案41.94万件，网上开庭〔后略，全文见 questions/BJ-2025-DC-ERMO/BJ-2025-DC-ERMO-Q17.md:20〕
- 原件上下文：〔前略〕院在2024年开展网上立電41.94万件，网上开庭〔后略，全文见 2025模拟题/2025各区二模/2025东城二模/试卷/试卷.pdf 第4页〕
- 题库文件行：questions/BJ-2025-DC-ERMO/BJ-2025-DC-ERMO-Q17.md:20；读取依据 bank_default；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-DC-ERMO-Q17_p004_1588bf.png

## 15. BJ-2025-DC-QIMO-Q19 错字（stem｜题目原文（原卷·逐页对照））
- 名次：去重后第 15（未去重第 15）；题库：`棚` → 原件：`栩`（原卷 第6页，text_reliable，层级 native，行比 0.96，优先级 10.83）
- 题库上下文：〔前略〕：我没有电动自行车，建车棚会占用绿地，影响我遛弯了〔后略，全文见 questions/BJ-2025-DC-QIMO/BJ-2025-DC-QIMO-Q19.md:33〕
- 原件上下文：〔前略〕：我没有电动自行车，建车栩会占用绿地，影响我遛弯了〔后略，全文见 2025模拟题/2025各区期末/2025东城期末/试卷/试卷.pdf 第6页〕
- 题库文件行：questions/BJ-2025-DC-QIMO/BJ-2025-DC-QIMO-Q19.md:33；读取依据 heuristic_no_default_stem；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-DC-QIMO-Q19_p006_b79721.png

## 16. BJ-2025-FT-QIMO-Q3 错字（stem｜题目原文（原卷·native，补足缺失的原卷角色））
- 名次：去重后第 16（未去重第 16）；题库：`治` → 原件：`洽`（原卷 第2页，text_plus_figure，层级 native，行比 0.96，优先级 10.82）
- 题库上下文：③“一平台”以基层自治为主导，保障老年群体的基〔后略，全文见 questions/BJ-2025-FT-QIMO/BJ-2025-FT-QIMO-Q3.md:17〕
- 原件上下文：〔前略〕需求③“一平台”以基层自洽为主导，保障老年群体的基〔后略，全文见 2025模拟题/2025各区期末/2025丰台期末/试卷/试卷.pdf 第2页〕
- 题库文件行：questions/BJ-2025-FT-QIMO/BJ-2025-FT-QIMO-Q3.md:17；读取依据 heuristic_no_default_stem；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-FT-QIMO-Q3_p002_944aa8.png

## 17. BJ-2026-FT-YIMO-Q21 漏字（e1｜正式评分细则层（E1；PPT slides 61–64））
- 名次：去重后第 17（未去重第 17）；题库：`∅` → 原件：`的`（评分材料 第63页，pptx_text，层级 native，行比 0.93，优先级 10.45）
- 题库上下文：〔前略〕分为论述逻辑清晰，有明显结构，能从识变、应变、求〔后略，全文见 questions/BJ-2026-FT-YIMO/BJ-2026-FT-YIMO-Q21.md:115〕
- 原件上下文：〔前略〕分:论述逻辑清晰，有明显的结构。能从识变、应变、求〔后略，全文见 2026模拟题/2026各区一模/2026丰台一模/细则/细则.pptx 第63页〕
- 题库文件行：questions/BJ-2026-FT-YIMO/BJ-2026-FT-YIMO-Q21.md:115；读取依据 heuristic_title；标记 cjk_short

## 18. BJ-2026-FT-YIMO-Q21 漏字（e1｜正式评分细则层（E1；PPT slides 61–64））
- 名次：去重后第 18（未去重第 18）；题库：`∅` → 原件：`论述`（评分材料 第63页，pptx_text，层级 native，行比 0.93，优先级 10.45）
- 题库上下文：〔前略〕什么、怎么做”等角度展开；8–9分为观点明确，运〔后略，全文见 questions/BJ-2026-FT-YIMO/BJ-2026-FT-YIMO-Q21.md:115〕
- 原件上下文：〔前略〕为什么、怎么做等角度展开论述；8-9分:观点明确，运〔后略，全文见 2026模拟题/2026各区一模/2026丰台一模/细则/细则.pptx 第63页〕
- 题库文件行：questions/BJ-2026-FT-YIMO/BJ-2026-FT-YIMO-Q21.md:115；读取依据 heuristic_title；标记 cjk_short

## 19. BJ-2023-XC-ERMO-Q19 漏字（e1｜正式评分材料原文（E1））
- 名次：去重后第 19（未去重第 19）；题库：`∅` → 原件：`亦可`（评分材料 第2页，docx，层级 native，行比 0.91，优先级 10.23）
- 题库上下文：其他合理回答酌情给分。
- 原件上下文：〔前略〕挑战，2分（其他合理回答亦可酌情给分）19.（9分）〔后略，全文见 2023模拟题/2023各区模拟题(1)/各区二模/√西城/细则-高三政治二模5-10(2).docx 第2页〕
- 题库文件行：questions/BJ-2023-XC-ERMO/BJ-2023-XC-ERMO-Q19.md:46；读取依据 bank_role_alias；标记 cjk_short

## 20. BJ-2025-DC-ERMO-Q16 漏字（e3｜原卷嵌入式参考答案（非独立答案源））
- 名次：去重后第 20（未去重第 20）；题库：`∅` → 原件：`仍`（原卷 第7页，text_reliable，层级 native，行比 1.00，优先级 9.38）
- 题库上下文：〔前略〕不可阻挡。虽有挑战，我们要积极拥抱人工智能的到来〔后略，全文见 questions/BJ-2025-DC-ERMO/BJ-2025-DC-ERMO-Q16.md:97〕
- 原件上下文：〔前略〕不可阻挡。虽有挑战，我们仍要积极拥抱人工智能的到来〔后略，全文见 2025模拟题/2025各区二模/2025东城二模/试卷/试卷.pdf 第7页〕
- 题库文件行：questions/BJ-2025-DC-ERMO/BJ-2025-DC-ERMO-Q16.md:97；读取依据 heuristic_title；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-DC-ERMO-Q16_p007_3583f4.png

## 21. BJ-2026-YQ-YIMO-Q20 漏字（e3｜参考答案原文）
- 名次：去重后第 21（未去重第 21）；题库：`∅` → 原件：`色`（评分材料 第1页，docx，层级 native，行比 1.00，优先级 9.38）
- 题库上下文：可从习近平新时代中国特社会主义思想、中国式现代〔后略，全文见 questions/BJ-2026-YQ-YIMO/BJ-2026-YQ-YIMO-Q20.md:87〕
- 原件上下文：〔前略〕）可从习近平新时代中国特色社会主义思想、中国式现代〔后略，全文见 2026模拟题/2026各区一模/2026延庆一模/细则/细则.docx 第1页〕
- 题库文件行：questions/BJ-2026-YQ-YIMO/BJ-2026-YQ-YIMO-Q20.md:87；读取依据 bank_role_alias；标记 cjk_short

## 22. BJ-2024-BJ-GAOKAO-Q11 错字（e3｜教师版参考解析（E3））
- 名次：去重后第 22（未去重第 22）；题库：`载` → 原件：`裁`（教师版 第10页，text_reliable，层级 native，行比 0.99，优先级 9.33）
- 题库上下文：11．C合同、侵权合同载明“游客需自担风险和责任〔后略，全文见 questions/BJ-2024-BJ-GAOKAO/BJ-2024-BJ-GAOKAO-Q11.md:98〕
- 原件上下文：〔前略〕。11．C合同、侵权合同裁明“游客需自担风险和责任〔后略，全文见 历年高考题及细则/2024北京高考真题政治（教师版）.pdf 第10页〕
- 题库文件行：questions/BJ-2024-BJ-GAOKAO/BJ-2024-BJ-GAOKAO-Q11.md:98；读取依据 heuristic_title；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2024-BJ-GAOKAO-Q11_p010_830d46.png

## 23. BJ-2024-BJ-GAOKAO-Q18 错字（e3｜教师版参考答案与讲解（E3，教师版页 12，第 18 题））
- 名次：去重后第 23（未去重第 23）；题库：`延` → 原件：`廷`（教师版 第12页，text_reliable，层级 native，行比 0.99，优先级 9.33）
- 题库上下文：〔前略〕进生产力作为中项，都不周延，违反了第②条规则，所以〔后略，全文见 questions/BJ-2024-BJ-GAOKAO/BJ-2024-BJ-GAOKAO-Q18.md:142〕
- 原件上下文：〔前略〕进生产力作为中项，都不周廷，违反了第②条规则，所以〔后略，全文见 历年高考题及细则/2024北京高考真题政治（教师版）.pdf 第12页〕
- 题库文件行：questions/BJ-2024-BJ-GAOKAO/BJ-2024-BJ-GAOKAO-Q18.md:142；读取依据 heuristic_title；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2024-BJ-GAOKAO-Q18_p012_c1e5aa.png

## 24. BJ-2024-BJ-GAOKAO-Q10 错字（e3｜教师版参考解析（E3））
- 名次：去重后第 24（未去重第 24）；题库：`仲` → 原件：`种`（教师版 第10页，text_reliable，层级 native，行比 0.99，优先级 9.33）
- 题库上下文：〔前略〕方式可以采用和解、调解、仲裁或诉讼等，④正确：行政〔后略，全文见 questions/BJ-2024-BJ-GAOKAO/BJ-2024-BJ-GAOKAO-Q10.md:73〕
- 原件上下文：〔前略〕方式可以采用和解、调解、种裁或诉讼等，④正确：行政〔后略，全文见 历年高考题及细则/2024北京高考真题政治（教师版）.pdf 第10页〕
- 题库文件行：questions/BJ-2024-BJ-GAOKAO/BJ-2024-BJ-GAOKAO-Q10.md:73；读取依据 heuristic_title；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2024-BJ-GAOKAO-Q10_p010_581785.png

## 25. BJ-2025-BJ-GAOKAO-Q17 错字（e3｜E3教师版参考答案（独立答案缺失））
- 名次：去重后第 25（未去重第 25）；题库：`求` → 原件：`讼`（教师版 第15页，text_reliable，层级 native，行比 0.99，优先级 9.33）
- 题库上下文：〔前略〕享和业务协同，方便群众诉求的表达，提高了政府部门处〔后略，全文见 questions/BJ-2025-BJ-GAOKAO/BJ-2025-BJ-GAOKAO-Q17.md:51〕
- 原件上下文：〔前略〕享和业务协同，方便群众诉讼的表达，提高了政府部门处〔后略，全文见 历年高考题及细则/2025北京高考真题政治（教师版）.pdf 第15页〕
- 题库文件行：questions/BJ-2025-BJ-GAOKAO/BJ-2025-BJ-GAOKAO-Q17.md:51；读取依据 heuristic_title；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-BJ-GAOKAO-Q17_p015_401468.png

## 26. BJ-2024-BJ-GAOKAO-Q16 错字（e3｜教师版参考答案与讲解（E3，教师版页 11，第 16 题））
- 名次：去重后第 26（未去重第 27）；题库：`因` → 原件：`国`（教师版 第11页，text_reliable，层级 native，行比 0.99，优先级 9.32）
- 题库上下文：〔前略〕，联系教材知识可从"文明因交流而多彩，因互鉴而丰富〔后略，全文见 questions/BJ-2024-BJ-GAOKAO/BJ-2024-BJ-GAOKAO-Q16.md:185〕
- 原件上下文：〔前略〕，联系教材知识可从“文明国交流而多彩，因互鉴而丰富〔后略，全文见 历年高考题及细则/2024北京高考真题政治（教师版）.pdf 第11页〕
- 题库文件行：questions/BJ-2024-BJ-GAOKAO/BJ-2024-BJ-GAOKAO-Q16.md:185；读取依据 heuristic_title；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2024-BJ-GAOKAO-Q16_p011_a9edc0.png

## 27. BJ-2024-BJ-GAOKAO-Q16 错字（e3｜教师版参考答案与讲解（E3，教师版页 11，第 16 题））
- 名次：去重后第 27（未去重第 28）；题库：`翻` → 原件：`题`（教师版 第11页，text_reliable，层级 native，行比 0.99，优先级 9.30）
- 题库上下文：〔前略〕长补短，共同发展。③通过翻译，有利于推动中华文明走〔后略，全文见 questions/BJ-2024-BJ-GAOKAO/BJ-2024-BJ-GAOKAO-Q16.md:183〕
- 原件上下文：〔前略〕长补短，共同发展。③通过题译，有利于推动中华文明走〔后略，全文见 历年高考题及细则/2024北京高考真题政治（教师版）.pdf 第11页〕
- 题库文件行：questions/BJ-2024-BJ-GAOKAO/BJ-2024-BJ-GAOKAO-Q16.md:183；读取依据 heuristic_title；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2024-BJ-GAOKAO-Q16_p011_531af7.png

## 28. BJ-2024-BJ-GAOKAO-Q10 错字（e3｜教师版参考解析（E3））
- 名次：去重后第 28（未去重第 29）；题库：`组` → 原件：`维`（教师版 第10页，text_reliable，层级 native，行比 0.99，优先级 9.29）
- 题库上下文：〔前略〕象等方面的客观评判。任何组织或个人不得以侮辱、诽谤〔后略，全文见 questions/BJ-2024-BJ-GAOKAO/BJ-2024-BJ-GAOKAO-Q10.md:73〕
- 原件上下文：〔前略〕象等方面的客观评判。任何维织或个人不得以侮辱、诽谤〔后略，全文见 历年高考题及细则/2024北京高考真题政治（教师版）.pdf 第10页〕
- 题库文件行：questions/BJ-2024-BJ-GAOKAO/BJ-2024-BJ-GAOKAO-Q10.md:73；读取依据 heuristic_title；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2024-BJ-GAOKAO-Q10_p010_93ddb8.png

## 29. BJ-2024-HD-ERMO-Q16 错字（e1｜正式评分材料原文）
- 名次：去重后第 29（未去重第 30）；题库：`细则` → 原件：`答案`（评分材料 第1页，docx_with_image，层级 native，行比 0.82，优先级 9.21）
- 题库上下文：16.（6分）【细则】
- 原件上下文：〔前略〕55分。16.（6分）【答案】联系是普遍的，在人际关〔后略，全文见 2024模拟题/海淀二模/细则/细则.docx 第1页〕
- 题库文件行：questions/BJ-2024-HD-ERMO/BJ-2024-HD-ERMO-Q16.md:63；读取依据 bank_role_alias；标记 cjk_short

## 30. BJ-2024-HD-ERMO-Q19 错字（e1｜正式评分材料原文）
- 名次：去重后第 30（未去重第 31）；题库：`细则` → 原件：`答案`（评分材料 第3页，docx_with_image，层级 native，行比 0.82，优先级 9.21）
- 题库上下文：19.（6分）【细则】
- 原件上下文：〔前略〕给1分；19.（6分）【答案】在本案判决中，人民法院〔后略，全文见 2024模拟题/海淀二模/细则/细则.docx 第3页〕
- 题库文件行：questions/BJ-2024-HD-ERMO/BJ-2024-HD-ERMO-Q19.md:69；读取依据 bank_role_alias；标记 cjk_short

## 31. BJ-2024-HD-QIZHONG-Q16 漏字（e1｜答案层（与评分细则分层））
- 名次：去重后第 31（未去重第 32）；题库：`∅` → 原件：`的`（评分材料 第8页，text_reliable，层级 native，行比 0.81，优先级 9.11）
- 题库上下文：〔前略〕各1分）；形式表现给整体表达或逻辑分，书写上标序〔后略，全文见 questions/BJ-2024-HD-QIZHONG/BJ-2024-HD-QIZHONG-Q16.md:70〕
- 原件上下文：〔前略〕）（3）形式表现：给整体的表达或逻辑分（书写上，形〔后略，全文见 2024模拟题/2024海淀期中/细则/细则.pdf 第8页〕
- 题库文件行：questions/BJ-2024-HD-QIZHONG/BJ-2024-HD-QIZHONG-Q16.md:70；读取依据 heuristic_title；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2024-HD-QIZHONG-Q16_p008_a46641.png

## 32. BJ-2024-HD-QIZHONG-Q16 漏字（e1｜答案层（与评分细则分层））
- 名次：去重后第 32（未去重第 33）；题库：`∅` → 原件：`者`（评分材料 第8页，text_reliable，层级 native，行比 0.81，优先级 9.11）
- 题库上下文：〔前略〕或逻辑分，书写上标序号或分段、文字递进，没有扣1〔后略，全文见 questions/BJ-2024-HD-QIZHONG/BJ-2024-HD-QIZHONG-Q16.md:70〕
- 原件上下文：〔前略〕（书写上，形式上标序号或者分段，文字递进，没有就扣〔后略，全文见 2024模拟题/2024海淀期中/细则/细则.pdf 第8页〕
- 题库文件行：questions/BJ-2024-HD-QIZHONG/BJ-2024-HD-QIZHONG-Q16.md:70；读取依据 heuristic_title；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2024-HD-QIZHONG-Q16_p008_b595fc.png

## 33. BJ-2024-HD-QIZHONG-Q16 漏字（e1｜答案层（与评分细则分层））
- 名次：去重后第 33（未去重第 34）；题库：`∅` → 原件：`就`（评分材料 第8页，text_reliable，层级 native，行比 0.81，优先级 9.11）
- 题库上下文：〔前略〕号或分段、文字递进，没有扣1分。
- 原件上下文：〔前略〕或者分段，文字递进，没有就扣1分）参考答案：①需求〔后略，全文见 2024模拟题/2024海淀期中/细则/细则.pdf 第8页〕
- 题库文件行：questions/BJ-2024-HD-QIZHONG/BJ-2024-HD-QIZHONG-Q16.md:70；读取依据 heuristic_title；标记 cjk_short
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2024-HD-QIZHONG-Q16_p008_17ab7e.png

## 34. BJ-2023-DC-YIMO-Q18 漏字（e1｜参考答案及正式评分材料）
- 名次：去重后第 34（未去重第 35）；题库：`∅` → 原件：`地位：`（评分材料 第5页，pptx_text，层级 native，行比 0.97，优先级 8.78）
- 题库上下文：（1）实体经济是一国经济的立身〔后略，全文见 questions/BJ-2023-DC-YIMO/BJ-2023-DC-YIMO-Q18.md:55〕
- 原件上下文：〔前略〕放在实体经济上。（5分）地位：实体经济是一国经济的立身〔后略，全文见 2023模拟题/2023各区模拟题(1)/各区一模/东城/2023.3高三政治一模统阅-题组长（细则讨论）.pptx 第5页〕
- 题库文件行：questions/BJ-2023-DC-YIMO/BJ-2023-DC-YIMO-Q18.md:55；读取依据 heuristic_title；标记 无

## 35. BJ-2026-FT-YIMO-Q21 错字（e1｜正式评分细则层（E1；PPT slides 61–64））
- 名次：去重后第 35（未去重第 36）；题库：`为` → 原件：`:`（评分材料 第63页，pptx_text，层级 native，行比 0.96，优先级 8.68）
- 题库上下文：水平三4–6分：4分为有少量论述，能回应问题，〔后略，全文见 questions/BJ-2026-FT-YIMO/BJ-2026-FT-YIMO-Q21.md:113〕
- 原件上下文：〔前略〕分。水平三4-6分:4分:有少量论述，能回应问题，〔后略，全文见 2026模拟题/2026各区一模/2026丰台一模/细则/细则.pptx 第63页〕
- 题库文件行：questions/BJ-2026-FT-YIMO/BJ-2026-FT-YIMO-Q21.md:113；读取依据 heuristic_title；标记 无

## 36. BJ-2024-HD-QIZHONG-Q21 错字（e1｜答案层（与评分细则分层））
- 名次：去重后第 36（未去重第 38）；题库：`：` → 原件：`(2）`（评分材料 第64页，text_reliable，层级 native，行比 0.96，优先级 8.64）
- 题库上下文：〔前略〕评分课件第64页参考答案：新中国外交的时代背景不断〔后略，全文见 questions/BJ-2024-HD-QIZHONG/BJ-2024-HD-QIZHONG-Q21.md:72〕
- 原件上下文：〔前略〕不变"。(9分）参考答案(2）新中国外交的时代背景不断〔后略，全文见 2024模拟题/2024海淀期中/细则/细则.pdf 第64页〕
- 题库文件行：questions/BJ-2024-HD-QIZHONG/BJ-2024-HD-QIZHONG-Q21.md:72；读取依据 heuristic_title；标记 无
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2024-HD-QIZHONG-Q21_p064_b78223.png

## 37. BJ-2023-FT-YIMO-Q9 漏字（stem｜题面（不含内附答案、分析、详解））
- 名次：去重后第 37（未去重第 41）；题库：`∅` → 原件：`从`（教师版/转录题源 第1页，docx_with_image，层级 native，行比 0.75，优先级 8.44）
- 题库上下文：标题：2016—2022年全国〔后略，全文见 questions/BJ-2023-FT-YIMO/BJ-2023-FT-YIMO-Q9.md:23〕
- 原件上下文：〔前略〕【答案】B【详解】①④：从2016-2022年（R〔后略，全文见 2023模拟题/2023各区模拟题(1)/各区一模/丰台.docx 第1页〕
- 题库文件行：questions/BJ-2023-FT-YIMO/BJ-2023-FT-YIMO-Q9.md:23；读取依据 bank_default；标记 cjk_short

## 38. BJ-2023-DC-YIMO-Q18 错字（e1｜参考答案及正式评分材料）
- 名次：去重后第 38（未去重第 42）；题库：`7` → 原件：`2`（评分材料 第6页，pptx_text，层级 native，行比 0.94，优先级 8.43）
- 题库上下文：〔前略〕育实体经济增长新动能。（7分）（言之有理，可得分）
- 原件上下文：〔前略〕育实体经济增长新动能。（2分）（注意和技术创新的差〔后略，全文见 2023模拟题/2023各区模拟题(1)/各区一模/东城/2023.3高三政治一模统阅-题组长（细则讨论）.pptx 第6页〕
- 题库文件行：questions/BJ-2023-DC-YIMO/BJ-2023-DC-YIMO-Q18.md:58；读取依据 heuristic_title；标记 无

## 39. BJ-2025-DC-QIMO-Q21 漏字（stem｜题目原文（原卷·逐页对照））
- 名次：去重后第 39（未去重第 43）；题库：`∅` → 原件：`居世界第一。`（原卷 第7页，text_reliable，层级 native，行比 0.94，优先级 8.42）
- 题库上下文：〔前略〕，公共图书馆、博物馆等向社会免费开放。……
- 原件上下文：〔前略〕，公共图书馆、博物馆等向居世界第一。社会免费开放。截至202〔后略，全文见 2025模拟题/2025各区期末/2025东城期末/试卷/试卷.pdf 第7页〕
- 题库文件行：questions/BJ-2025-DC-QIMO/BJ-2025-DC-QIMO-Q21.md:37；读取依据 heuristic_no_default_stem；标记 无
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-DC-QIMO-Q21_p007_5c1022.png

## 40. BJ-2025-FT-QIMO-Q13 错字（stem｜题目原文（原卷·native，读取优先））
- 名次：去重后第 40（未去重第 44）；题库：`→` → 原件：`，`（原卷 第12页，text_reliable，层级 native，行比 0.93，优先级 8.37）
- 题库上下文：③实施更加积极的财政政策→合理安排政府投资规模→发〔后略，全文见 questions/BJ-2025-FT-QIMO/BJ-2025-FT-QIMO-Q13.md:36〕
- 原件上下文：〔前略〕：实施更加积极的财政政策，合理安排政府投资规模，发〔后略，全文见 2025模拟题/2025各区期末/2025丰台期末/试卷/试卷.pdf 第12页〕
- 题库文件行：questions/BJ-2025-FT-QIMO/BJ-2025-FT-QIMO-Q13.md:36；读取依据 bank_default；标记 无
- 裁图：/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/build/doc2md/fix/retro/crops/BJ-2025-FT-QIMO-Q13_p012_226c4c.png
