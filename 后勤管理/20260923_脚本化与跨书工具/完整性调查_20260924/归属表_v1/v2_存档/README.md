# 完整性归属表 v2 —— 按对抗审查意见返修

`rule_version: 2026-09-24-attribution-v2` / `identity版本: 2026-09-24-identity-v2`

本目录是"完整性调查_20260924"任务归属表的第二版：针对 `审查意见.json`（Opus 对抗审查，3 blocker / 5 major / 2 minor）
逐条返修。v1 产物已原样归档到 `v1_存档/`（含原 README、脚本与全部CSV/JSON），本版不覆盖删除，只新增/替换主目录内容。
详细返修清单、每条问题的处理方式和验证证据见 `返修回执_v2.json`。

全程只读书稿、题库、Codex/Skill 记录，未修改任何书稿/题库/协作文件/Skill；未运行 `collab.py`。

## 相对 v1 的核心变化（对应 blocker①②③）

1. **证据/准入改为逐题逐小问判断，去掉卷级回退**（blocker①）：`build_attribution_v2.py` 只用
   `rubric_links.csv` 里该 `question_id` 自己的行（`pair_status` + `material_kind`）判定 E1/E3，
   不再"同卷任一题已匹配就整卷继承"。凡是该题的正式材料候选处于"存在候选/存在冲突"而没有确认匹配时，
   一律落 `待裁决-证据未核实`（不收也不丢，留在候选队列）——v1 这个分支永远走不到（输出0条），
   v2 现在有 **222** 条落在这里。同时叠加 `skill_overrides.json` 里 5 条带 Skill/宪法/exams.csv 原文出处
   的覆盖判断（具名例外按 scope 精确到题/小问执行，题库线缺口如实标注）。
2. **漏收差集不再直接剔除脚本判 OUT 的组合**（blocker②）：`build_diffs_v2.py` 新增
   `<MOD>_out_lowprior_candidates.csv`（"OUT-低先验"层），把原来直接消失的组合单列出来，
   在没有分层金标集测出漏收率≤1%之前不当"已确认非本模块"处理。
3. **身份层的题级等价类真正用到归属列**（blocker③核心机制）：`matrix.csv` 本身已经有逐题的
   `dup_covered_by` 列（例如 `BJ-2025-HD-QIZHONG-Q4` 的孪生题已被必修二收录），v1 生成 COLLECTED 列时
   没有读这一列，v2 已接入——`归属_<模块>` 的 COLLECTED 判断同时看该题自己的收录状态和
   `dup_covered_by` 里的等价类合并结果。另外新增 `BJ-2025-FT-YIMO-Q18` 的身份重定向标记
   （题库把 Q12 的 BMI 表尾部误切成一道伪选择题，真实的主观题"第18题"未被登记），不计入选择题分母，
   已列入回传题库线。身份层未能在本轮完全解决的部分（例如 2024/2025 高考的串题、2025 海淀/西城期末冲突）
   仍在 `已知限制` 里如实标注，未假装已修复。

## 目录结构

```
归属表_v1/                       （沿用原目录名，内容已是v2）
  README.md                      本文件
  exam_identity.json             缺口1 v2：卷身份/别名/重定向表（新增 qid_redirects、门头沟/房山收口、CY-QIZHONG学年）
  回传题库线_v2.json              不改题库文件，只登记题库侧待修条目（学年×2、Q18切分错误、2024高考rubric_links缺口）
  skill_overrides.json           逐题/逐小问级覆盖表：5条带Skill/宪法/exams.csv原文出处的具名例外与题库线缺口覆盖
  attribution.csv                缺口2 v2：题级/小问级九模块归属表（新增 evidence_detail、identity_redirect 列）
  attribution_options.csv        缺口2的题肢级辅助表（弱信号，未变更逻辑，见"已知限制"）
  attribution_ruled.csv / .changelog.json   apply_rulings_v2.py 产物（rulings.jsonl当前仍为空，逐行passthrough）
  diffs/
    <MOD>_missing_candidates.csv       每本书的漏收候选（不含OUT）
    <MOD>_extra_candidates.csv         每本书的错收候选（脚本独立信号判OUT但书稿COLLECTED，疑似，需人工复核）
    <MOD>_out_lowprior_candidates.csv  【新增】脚本判OUT但未被剔除的低先验候选，供分层抽样验证
    summary.csv                        八本书的差集数量v2汇总
  model_batch/
    boundary_cards.md              缺口4 v2：五张边界卡按Skill原文重摘，删推断，补正反回归样例
    slice_estimate.json            缺口4 v2：新增COLLECTED复判队列(major④)、长度未截断抽查、缓存/多轮开销提示
  inputs_snapshot/                【新增】major⑤：核心输入快照+SHA-256清单+生成命令，见其README.md
  rulings.jsonl / rulings.example.jsonl   裁定日志（未变，仍为空/示例）
  scripts/
    build_exam_identity_v2.py
    build_attribution_v2.py
    build_diffs_v2.py
    prep_model_batch_v2.py
    apply_rulings_v2.py
    （v1脚本一并保留在 v1_存档/scripts/，供比对）
  v1_存档/                        【新增】v1的README、全部CSV/JSON产物与脚本原样保留
  返修回执_v2.json                逐条对照 审查意见.json 的10条问题，记录处理方式、证据、剩余限制
```

## 口径总述（与 v1 一致的部分不再重复，只列变化点）

- 分母、粒度、九模块三态复用规则与 v1 相同（见 v1_存档/README.md）。
- **归属_<模块>** 取值语义不变（COLLECTED/IN/OUT/MAYBE），但 COLLECTED 的判定逻辑已按 blocker③ 修复（见上）。
- **证据列（`evidence`）** 语义已改（不是 v1 的四选一，是分场景多值，逐条见 `build_attribution_v2.py` 顶部 docstring）：
  `E1` / `E3` / `具名例外` / `缺细则`（未核实）/ `缺细则-已核实`（有明确负例记录）/ `缺答案键`（选择题版）/
  `缺答案键-已核实` / `答案键来源未核实(候选未确认)` / 身份层标记。新增 `evidence_detail` 列给出判定依据原句。
- **准入列（`admission`）** 增加 `身份错误-不计入分母`（目前唯一一条：BJ-2025-FT-YIMO-Q18），其余五类不变。

## 差集汇总（`diffs/summary.csv`，本次v2运行结果）

| 模块 | 漏收候选合计(不含OUT) | 其中IN | 其中MAYBE待模型 | 按裁定可收 | 按裁定不收 | 错收候选(疑似) | OUT低先验(新增,未剔除) |
|---|---|---|---|---|---|---|---|
| 必修二 B2 | 1196 | 69 | 1127 | 1153 | 43 | 23 | 85 |
| 必修三 B3 | 1327 | 27 | 1300 | 1292 | 35 | 3 | 151 |
| 哲学 PH | 895 | 17 | 878 | 857 | 38 | 13 | 633 |
| 文化 CU | 984 | 13 | 971 | 949 | 35 | 17 | 688 |
| 选必一 X1 | 707 | 61 | 646 | 668 | 39 | 10 | 998 |
| 选必二 X2 | 842 | 43 | 799 | 788 | 54 | 0 | 846 |
| 思维 MI | 922 | 23 | 899 | 888 | 34 | 7 | 864 |
| 推理 RE | 1124 | 21 | 1103 | 1085 | 39 | 7 | 585 |

**读法提醒（沿用v1但更强调一次）**：
- "漏收候选合计"和"IN/MAYBE"数字与v1几乎相同——这是预期结果，因为归属列(IN/MAYBE/OUT)的三态来自
  `classify.py` 的独立信号，本轮没有重跑分类器，只修了证据/准入/身份三层的判断错误；证据/准入层的修复
  体现在"按裁定可收/不收"这两列的准确性上，不体现在IN/MAYBE的绝对数量上。
- "错收候选(疑似)"数字也与v1相同（23/3/13/17/10/0/7/7，合计80对，v1 README误写"100条"，本版已更正）——
  这是因为 build_diffs 这一步的错收候选完全来自 `classify.py` 自带的 `conflict_script_out` 字段，
  这层本轮没有重新跑分类器，数字不会变；major④的真正修复在 `model_batch/slice_estimate.json` 的
  "COLLECTED复判队列"——已经把全部COLLECTED模块单元（不止这80对）排进了模型复判队列，
  真正的错收候选要等复判结果出来才能重新算，build_diffs这一层的80对只是"脚本已经发现的下限"，不是全部。
- "OUT低先验"是v2新增的一层，八本书合计 **4,850** 条（85+151+633+688+998+846+864+585），
  对应 blocker② 修复：这些不再被脚本直接判定"非本模块"而消失，而是留作候选，供以后用分层抽样验证
  脚本OUT的真实精度；抽样验证通过前，模型批次/人工复核应把这一层也纳入抽查范围，不能假设它是空的。

## attribution.csv 总量（v2）

- 总行数 **1941**（含1932条分类器题级/小问级行 + 9条新增的汇编候选行，对应 major①）。
- `admission` 分布：完整题-选择题照收 1246、完整题-有E1 374、待裁决-证据未核实 222、不收-无E1 59、
  收-具名例外 39、身份错误-不计入分母 1。
- `待裁决-证据未核实` 从 v1 的 0 条变为 **222** 条——这是 blocker①修复最直接的体现：v1 声称有这个分支
  但实际永远走不到，v2 已经能正确识别"存在候选/存在冲突、未确认匹配"的题，不再机械二选一地判成
  "已收"或"不收"。

## 已知限制（本轮仍未解决，如实标注，不假装已修复）

1. **小问级E1证据仍不完整**：`rubric_links.csv` 的 `question_id` 粒度到题，不到小问；已知的
   `BJ-2025-BJ-GAOKAO-Q18(1)/(2)` 小问级证据差异（source-inventory.md第167行"仅18(2)仍为RED_UNCLOSED"）
   本轮未能独立核实到"18(1)已闭合"的直接原文，未写入 `skill_overrides.json`，该题按逐题证据规则落在
   "待裁决-证据未核实"，比v1的判法更保守但仍未做到小问级拆分，见 `skill_overrides.json` 的
   `not_included_pending_more_evidence`。
2. **选择题题肢级判断仍是弱信号**：`attribution_options.csv` 的词典命中表未重做，本册能否独立判断
   整个题肢、官方正误仍需模型/人工阶段核定（与v1相同限制）。
3. **"哲学与文化边界""政府归必修二还是必修三"两张边界卡在现有Skill文本里仍未找到明确原文**，
   `boundary_cards.md` 已如实标"Skill 未规定，需主代理补充"，不代为杜撰。
4. **身份层仍有未逐一核实的疑点未完全登记**：审查意见提到的"2022/2024高考串题""2025海淀与西城期末
   身份冲突""2026丰台期末Q20错位"等，本轮时间与只读核验条件下未能逐条独立复现证据链，没有写入
   `exam_identity.json`（避免在未核实的情况下往身份层里加不确定的断言）；已在 `返修回执_v2.json`
   里列为"deferred"，建议主代理下一步逐条核实后补登。
5. **OUT-低先验层的真实精度仍未知**：v2只是不再剔除，没有能力在本轮生成分层金标集去测漏收率，
   这需要人工抽样（建议参照审查意见"抽查RE的5条错收候选"的方法，扩大到8本书分层抽样）。
6. **token/调用次数估算的批大小、每题输出token等参数仍是本脚本的假设值**，`slice_estimate.json`
   新增的"caching_and_multiturn_caveat"字段已提示：实际用量可能因缓存重读和多轮调用放大一个数量级，
   正式执行前必须先用小样本校准。
7. **旧教材（2020—2022高考）的模块归属**按 `incremental-question-intake.md` 现有裁定必须逐题查原件判断，
   本表里这些题即便脚本给出IN，也仍在 `boundary_cards.md` 第5节明确提示"不能因为脚本给了IN就跳过人工复核"。

## 重跑命令

```bash
cd 归属表_v1
/usr/bin/python3 scripts/build_exam_identity_v2.py --out exam_identity.json --luna-out 回传题库线_v2.json
/usr/bin/python3 scripts/build_attribution_v2.py --identity exam_identity.json --overrides skill_overrides.json \
    --out attribution.csv --options-out attribution_options.csv
/usr/bin/python3 scripts/build_diffs_v2.py --attribution attribution.csv --out-dir diffs
/usr/bin/python3 scripts/prep_model_batch_v2.py --attribution attribution.csv --out model_batch/slice_estimate.json
/usr/bin/python3 scripts/apply_rulings_v2.py --attribution attribution.csv --rulings rulings.jsonl --out attribution_ruled.csv
```
重跑前先校验输入未变：`cd inputs_snapshot && shasum -a 256 -c MANIFEST.sha256`。
全部脚本 `/usr/bin/python3`（3.9.6）验证通过，脚本开头均设置 `sys.dont_write_bytecode = True`；
两次独立重跑 `attribution.csv`/`exam_identity.json`/`attribution_options.csv` 逐字节一致（确定性未破坏）；
只读书稿/题库/Skill，未运行 `collab.py`，未改动任何书稿或Skill文件（含 scripts/、profiles/）。
