# 完整性归属表 v1 —— 第一阶段（零模型token脚本部分）

`rule_version: 2026-09-24-attribution-v1` / `identity版本: 2026-09-24-identity-v1`

本目录是"完整性调查_20260924"任务的第一阶段交付：只做脚本能确定性完成的部分（身份层、归属初值表、逐书差集、模型批次的队列与token估算、裁定日志格式），**不跑任何模型判定**，全程只读书稿、题库、Codex记录与Skill，未修改任何书稿/题库/协作文件/Skill。

## 目录结构

```
归属表_v1/
  README.md                 本文件
  exam_identity.json        缺口1：卷身份/别名/重定向表
  attribution.csv           缺口2：题级/小问级九模块归属表（主表）
  attribution_options.csv   缺口2的题肢级辅助表（弱信号，见下方"已知限制"）
  diffs/
    <MOD>_missing_candidates.csv   每本书的漏收候选（MOD ∈ B2/B3/PH/CU/X1/X2/MI/RE）
    <MOD>_extra_candidates.csv     每本书的错收候选（疑似，需人工复核）
    summary.csv                    八本书的差集数量汇总
  model_batch/
    boundary_cards.md          缺口4：模块边界卡草案（只摘Skill/题库原文，标出处和空白）
    slice_estimate.json        缺口4：模型批次队列规模与调用次数/token估算（未执行）
  rulings.jsonl               缺口5：追加式裁定日志（当前为空，供主代理后续追加）
  rulings.example.jsonl       裁定日志格式示例（示例数据，不是真实裁定）
  scripts/
    build_exam_identity.py
    build_attribution.py
    build_diffs.py
    prep_model_batch.py
    apply_rulings.py
```

## 口径总述

- **分母**：题库 `indexes/questions.csv` 唯一 `question_id` 共 **1758** 题（与 coverage.py 历史复核数字一致）。
- **归属表粒度**：`attribution.csv` 共 **1932** 行，选择题按整题（1255题），主观题按小问拆分（已支持137题的小问级拆分，其余主观题小问未拆的整题一行，`grain`列标注"整题"/"小问"）。
- **归属判断复用**：直接复用 `原型脚本/classify.py` 在 `classified_prod.jsonl` 里已算好的九模块三态（IN/MAYBE/OUT）与证据（`ev`），以及 `coverage.py` 在 `matrix.csv` 里已算好的各书收录层级（S=正式收录/F=题库指纹匹配但无明确题源/M=仅全文提及）。本阶段脚本**不重新解析书稿**，只做合并、身份纠正、准入映射、差集和token估算。
- **归属列（每模块一列）**取值：
  - `COLLECTED`——matrix.csv 显示该书已收录（含S/F两层），即"已收待复核"，**不是"已定"**。
  - `IN`——脚本独立信号判定相关（设问点名/细则点名/词典与位置先验综合），但尚未被该书收录，是漏收候选中置信度较高的一类。
  - `OUT`——脚本判定非本模块；若该单元是**主观题且细则不可读**（`ev.rubric_readable=False`），本表已按三路调查blind_spot第124条的建议，把这种OUT**降级为MAYBE**并记入 `downgrade_notes` 列，不再机械判"非本模块"。
  - `MAYBE`——脚本无法确定，进入模型批次队列。
- **准入列**（`admission`）按用户2026-09-24裁定（已写入 `incremental-question-intake.md`"纳入范围"）：
  - 选择题一律"完整题-选择题照收"。
  - 主观题：有 `E1` 证据 → "完整题-有E1"；属于具名例外 → "收-具名例外"；只有 `E3`/缺细则 → "不收-无E1"；证据来源本身缺失/存疑 → "待裁决-证据未核实"。
- **证据列**（`evidence`）来自 `indexes/rubric_links.csv` 的 `material_kind`+`exam_rubric_status`聚合（正式评分材料且已匹配→E1；参考答案且已匹配→E3），叠加 `exam_identity.json` 里登记的具名例外。
- **每条判断都带 `rule_version` 戳**；规则改版后只需按戳重判受影响类别，不整表重跑。

## 缺口1：exam_identity.json 要点

- 卷总数 96（`exams.csv` 95行 + 1个只在汇编中出现、无独立登记行的卷自动补登）。
- **重复登记别名**：`BJ-2025-HD-QIZHONG` → 规范为 `BJ-2024-HD-QIZHONG`（共同题20道，2024侧已有E1批量验收记录）。
- **只在汇编中出现的卷**：`BJ-2024-FS-YIMO`（房山一模）标记 `compilation_only_pending_source`；`BJ-2024-MTG-YIMO`（门头沟一模）因为 `source-inventory.md` 第152行（选必二范围内撤销）与第136行（"汇编线索/继续检索，不是确认无细则"）两条记录口径不一致，标记为 `disputed_scope`，**留给主代理裁定撤销范围是全局还是仅限选必二**（必修三第52批仍引用其汇编题肢，见三路调查摘要第131行）。
- **学年字段疑似写错**：`BJ-2023-HD-QIZHONG` 的 `exams.csv` 登记学年为"2022-2023学年"，但原件文件名为《2023北京海淀高三（上）期中政治（教师版）.docx》（"高三上"对应2023秋季学期→2023-2024学年），本表按 `school_year_correction_pending_confirm` 状态记录建议值和依据，**未直接改题库**。
- **具名例外统一登记**：本表把分散在 `project-constitution.md`（special_override：2026北京高考整卷、2024石景山一模Q19(1)）与各书 `book-philosophy.md`/`book-culture.md`（书末E3例外：2024顺义二模、2026石景山期末）里的具名例外汇总到同一处，并且用 `exams.csv` 自身notes列的原话（"Q1-Q20按2026石景山期末具名无正式细则例外使用E3"等）做了交叉验证。

## 缺口2/3：attribution.csv 与逐书差集要点

`diffs/summary.csv`（本次运行结果）：

| 模块 | 漏收候选合计 | 其中IN(高置信) | 其中MAYBE(待模型) | 按裁定应收 | 按裁定应不收 | 错收候选(疑似) |
|---|---|---|---|---|---|---|
| 必修二 B2 | 1196 | 71 | 1125 | 1115 | 81 | 23 |
| 必修三 B3 | 1331 | 29 | 1302 | 1253 | 78 | 3 |
| 哲学 PH | 887 | 17 | 870 | 794 | 93 | 13 |
| 文化 CU | 977 | 13 | 964 | 875 | 102 | 17 |
| 选必一 X1 | 706 | 64 | 642 | 604 | 102 | 10 |
| 选必二 X2 | 839 | 45 | 794 | 718 | 121 | 0 |
| 思维 MI | 913 | 23 | 890 | 824 | 89 | 7 |
| 推理 RE | 1118 | 21 | 1097 | 1001 | 117 | 7 |

**重要提醒**：漏收候选"合计"里 MAYBE 占绝大多数（这是分类器本身"只能确定性判定约22%单元"的直接反映，见三路调查摘要 spot_check 第一条），**不能当成"漏收了这么多题"**，而是"这么多(单元,模块)组合还没被脚本确定，需要进入模型批次或人工复核"。真正可以不经模型、直接按脚本高置信信号处理的，是"IN"这一列（71/29/17/13/64/45/23/21，共**283条(单元,模块)组合**）；"错收候选"是脚本独立信号与书稿收录冲突的疑似错收，同样需要人工复核，不是自动认定错收（共**100条**，去重后75个独立单元，见下）。

`attribution_options.csv`（题肢级辅助表）：4713条选择题题肢词典命中记录，**仅供参考，不构成准入依据**（词典精度约0.66—0.88，见三路调查摘要 blind_spot 第126条）；本册是否能独立判断整个题肢、官方正误，仍需模型/人工阶段核定。

## 缺口4：模型批次准备（未执行）

`model_batch/slice_estimate.json`：
- 队列规模：**1743个独立题**需要模型至少判定一个模块（1742个来自"至少一模块MAYBE"，另加1个只因"疑似错收"进队列但本身MAYBE为0的题）。
- 疑似错收（`conflict_script_out`非空）共 **75个独立单元、100条(单元,模块)冲突**，需要人工核实"书稿收对了没有"。
- 按假设批大小（选择题25题/次、主观题10题/次，因细则不截断体量更大）估算：约 **101次调用**，输入token约 **112万—145万**，输出token约 **21万**，合计约 **133万—166万token**。这些批大小、开销假设都是可调参数（见 `prep_model_batch.py` 的命令行参数），**建议先用10—20题的小样本实测校准，再乘队列规模**，本估算只定量级，不是最终值。
- `model_batch/boundary_cards.md`：五张边界卡草案（必修一剔除、政府归属、哲学与文化、思维与推理、旧教材映射），**只摘 Skill/题库现有原文并标出处**；其中"必修一剔除清单"和"政府归属"两张在现有 Skill 正文里没有找到明确边界表述，已如实标注"需主代理补充"，没有代为杜撰。

## 缺口5：rulings.jsonl 格式

见 `rulings.example.jsonl`（示例数据）与 `scripts/apply_rulings.py` 顶部docstring。核心设计：裁定只追加、不改 `attribution.csv` 本身；`apply_rulings.py` 读日志叠加生成 `attribution_ruled.csv` + 变更记录，重跑成本是"重新读一遍日志"而不是"重新判定一遍"。

## 重跑命令

```bash
cd 归属表_v1
/usr/bin/python3 scripts/build_exam_identity.py --out exam_identity.json
/usr/bin/python3 scripts/build_attribution.py --identity exam_identity.json --out attribution.csv --options-out attribution_options.csv
/usr/bin/python3 scripts/build_diffs.py --attribution attribution.csv --out-dir diffs
/usr/bin/python3 scripts/prep_model_batch.py --attribution attribution.csv --out model_batch/slice_estimate.json
/usr/bin/python3 scripts/apply_rulings.py --attribution attribution.csv --rulings rulings.jsonl --out attribution_ruled.csv   # 有真实裁定后再跑
```
全部脚本 `/usr/bin/python3`（3.9.6）验证通过；脚本开头均设置 `sys.dont_write_bytecode = True`；只读书稿/题库/Codex记录/Skill，未运行 `collab.py`，未改动任何书稿或Skill文件（含scripts/、profiles/）。

## 已知限制（未在本阶段解决，留给主代理/后续阶段）

1. **granularity 仍不完整**：选择题题肢目前只有词典命中的弱信号表（`attribution_options.csv`），没有"本册能否独立判断整个题肢"和"官方正误"这两层——这两层需要读原题选项+官方答案键，本阶段判定为需要模型或人工介入，未强行用脚本拍板。
2. **证据判定依赖 `rubric_links.csv` 覆盖率**：该表只有3065行，不是每道主观题都在其中；不在表里的题被归为"缺细则"，但这可能是"该题还没跑过rubric_links匹配"而不是"确认没有E1"——按用户裁定，缺证据先按"不收"处理，但**不能因此从候选队列里删除**，本表已确保这类题仍出现在归属列和差集里，只是准入列显示"不收-无E1"。
3. **必修一剔除清单、政府归属两张边界卡在现有Skill文本中找不到明确原文**，已如实标注空白，不代为拟定规则。
4. **`BJ-2024-MTG-YIMO` 的撤销范围（全局 vs 仅选必二）没有在本阶段裁定**，因为这需要主代理对比必修三第52批的实际引用情况才能定，本表只是把冲突记录到了同一处、不再让两册各查一遍。
5. **token/调用次数估算的批大小、每题输出token等参数是本脚本的假设值**，不是实测值；建议正式执行模型批次前先用小样本校准。
6. **旧教材（2020—2022高考）的模块归属**按 `incremental-question-intake.md` 现有裁定必须逐题查原件判断，本表里这些题即便脚本给出IN，也已在 boundary_cards.md 第5节明确提示"不能因为脚本给了IN就跳过人工复核"。
