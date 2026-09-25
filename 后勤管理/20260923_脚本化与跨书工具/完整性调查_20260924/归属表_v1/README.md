# 完整性归属表 v4 —— 修复4个major并合并最终判定、生成各书清单

`rule_version: 2026-09-24-attribution-v4`（清单合并戳 `2026-09-24-attribution-v4-final`）

**本版（v4）在v3基础上新增/变更**：详见 `返修回执_v4.json`（逐条对照 `确认意见_v3.json` 的4个
major + `各书清单_v4/终审意见.json` 的小问级展开blocker）与 `各书清单_v4/00_汇总.md`（各书数字、
建议优先级、自检结果、已知限制，大白话版）。核心变更：①孪生题配对改按题面(2024↔2025的
Q16↔Q16、Q18↔Q18)，Q25标记切分错误排除分母；②exams.csv小问级E1限定(朝阳一模Q18(2))补进
skill_overrides.json；③门头沟/房山必修三待复核区块(1/3/7/9/10/21题)全部纳入，书稿已引用的4题
标COLLECTED；④matrix.csv的`S[1/2]`类方括号小问标注不再被整题展开吞掉(`cell_collects_subq()`)，
这一项修复后，"已收但模型判错收"的假阳性从326处降到0（各书清单里的错收候选是在此基础上再
叠加模型chk信号得到的，量级降到个位数到十几条）。v3产物已原样归档到 `v3_存档/`（因归档时机在
本轮追加rulings.jsonl记录之后，其中的rulings.jsonl快照并非纯v3切片，见返修回执_v4.json说明；
其余文件均为v3原样）。新增 `各书清单_v4/` 目录：`<代号>_漏收候选.csv`/`_错收候选.csv`/
`_题肢候选.csv`（B2/B3/PH/CU/X1/X2/MI/RE，B2冻结仅记录）+ `00_汇总.md`。
`attribution.csv`/`exam_identity.json`/`skill_overrides.json`/`attribution_ruled.csv` 已更新为v4
内容；`scripts/build_attribution_v4.py`、`scripts/merge_and_lists_v4.py`、
`scripts/build_book_lists_v4.py` 是本轮新脚本（v3脚本保留在 `v3_存档/scripts/` 供比对）。
`diffs/` 目录保留v3产物作为历史参照，本轮未重新生成（各书清单_v4已用新方法替代其职责）。

---

## 以下为 v3 README 原文（历史记录，未删改，供比对）

本目录是"完整性调查_20260924"任务归属表的第三版：针对 `确认意见_v2.json`（Opus 对抗复核，
verdict=FAIL，1 blocker / 4 major）逐条返修。v2 产物已原样归档到 `v2_存档/`（含 v2 README、v2 脚本与
全部CSV/JSON），本版不覆盖删除，只新增/替换主目录内容。v1 产物仍在 `v1_存档/` 未动。
详细返修清单、每条问题的处理方式和验证证据见 `返修回执_v3.json`。

全程只读书稿、题库、Codex/Skill 记录，未修改任何书稿/题库/协作文件/Skill；未运行 `collab.py`；
未启动子代理、未开新会话。

## 相对 v2 的核心变化

### 1.【blocker】重复登记别名合并收口到 identity 层的 qid 等价类表，不再自己读 dup_covered_by 猜

v2 的 `build_attribution_v2.py` 直接信 `matrix.csv` 的 `dup_covered_by` 列非空就合并收录状态——但
`matrix.csv` 这一列对**跨卷复用/串题**（`bank_duplicate_exams.csv` 标 `shared_or_reused_questions`
的那些行，例如 2022/2024 高考 Q8、Q13，2024 高考 Q18 与 2026 海淀期中 Q8）也会填值，v2 没有区分，
把串题也当孪生题合并，产生了 20 组（单元,模块）假收录，同时因为 M 值不产生 `dup_covered_by`，
真正的重复登记别名（BJ-2024/2025-HD-QIZHONG）反而漏合并（Q2/Q15/Q19/Q21/Q25 等仍被判漏收）。

v3 的修复分两层：

- **身份层**（`build_exam_identity_v3.py`）新增 `dup_alias_qid_pairs`：只对 `status=
  duplicate_registration_alias` 的卷（本轮唯一一对：`BJ-2024-HD-QIZHONG` ↔ `BJ-2025-HD-QIZHONG`，
  按 `bank_duplicate_exams.csv` 的 `kind=duplicate_registration` 过滤，串题/复用的 `kind=
  shared_or_reused_questions` 天然不会进这张表）用 `matrix.csv` 的 `dup_of` 生成逐题
  `(canonical_qid, alias_qid)` 表，本次共 **20** 对。
- **归属层**（`build_attribution_v3.py`）只信这张表做 COLLECTED 合并：孪生题任一侧的 matrix.csv
  模块列本身非空（S/F/M 均算，不再只看 `dup_covered_by` 字符串）就判 COLLECTED；跨卷复用/串题
  只在 `downgrade_notes` 标"关联但不合并"，不改收录状态。
- 新增 `canonical_qid` 列：别名侧 qid 指向其孪生正式 qid；`build_diffs_v3.py` 按
  `(canonical_qid, subq)` 去重，避免同一等价类在漏收/OUT 差集里被两侧各列一行重复计数（本轮
  8 本书合计去重 **76** 行漏收候选、**39** 行 OUT 候选）。
- `build_diffs_v3.py` 把 `admission` 以"身份"开头的行（伪 Q18 切分错误、汇编待复核未定年份两类，
  共 3 行）整体排除出全部差集，不再进入任何模块的分母。
- 书稿标签重定向（确认意见示例"2025朝阳期中"→BJ-2026-CY-QIZHONG）：已用 grep 遍历全部
  `book-*.md`/`source-inventory.md`/`user-requirements-ledger.md`，未找到可引用原文，找不到出处
  不代为猜测，明确列为 **deferred**（见 `exam_identity.json` 的 `unresolved_notes`）。

### 2.【major】逐题 E1 结论从 exams.csv notes 与 book-xuanbi-*.md 系统补齐进 skill_overrides.json

`skill_overrides.json` 新增 **14** 条覆盖（原 5 条不变，本版共 19 条），每条都带原文出处：

- `eval_rubric_rows()` 修复核心 bug：rubric_links.csv 里"一行都没有"（未核实，不是已确认无）的
  主观题，v2 和"有明确负例记录"（已核实无）一起被机械判"不收-无E1"；v3 拆开，前者落
  "待裁决-证据未核实"，只有后者才判"不收-无E1"。
- 用 `grep -n "E1"` 逐行核对 `exams.csv`（全表仅 18 行含 E1/E3 逐题限定）与
  `book-xuanbi-1.md`/`book-xuanbi-3.md` 的多轮独立核验记录，找出与 `rubric_links.csv` 自动匹配结果
  冲突或缺失的题，逐条覆盖：
  - **纠正误判为 E1**（rubric_links.csv 自动文本匹配命中但书稿多轮核验确认不能拆分为采分槽）：
    `BJ-2026-FT-YIMO-Q19`（book-xuanbi-1.md:43,205,400,418,392 五轮独立核验一致确认"只有答案方向和
    整题样卷总分"）。
  - **补齐已闭环但 rubric_links.csv 没有行/自动匹配错的 E1**：`BJ-2024-FT-YIMO-Q20`、
    `BJ-2026-FS-YIMO-Q19`、`BJ-2026-HD-QIZHONG-Q22(1)`（book-xuanbi-1.md:307"本轮主观E1新闭环7题"）、
    `BJ-2026-HD-ERMO-Q18(1)`（book-xuanbi-3.md:86"分析与综合细则错配…而E1及答案均为'市场调研'"）。
  - **补齐已核实的确认负例**（不落"待裁决"而是"不收-无E1"）：`BJ-2024-FT-YIMO-Q21`、
    `BJ-2024-SJS-YIMO-Q19(2)`、`BJ-2026-FT-ERMO-Q20`、`BJ-2024-MTG-YIMO-Q18`。
  - `BJ-2024-SJS-YIMO-Q19(3)` 未见任何可引用具体结论，不代为裁定，仍按通用规则落待裁决。
- **冲突处理**：本轮抽查未发现 exams.csv notes 与 book-xuanbi-*.md 结论互相矛盾的情况（两个来源
  对同一题给出的结论一致时才写入覆盖表）；如后续发现冲突，按规则应落"待裁决"而不是任选其一，
  当前 `not_included_pending_more_evidence` 列表沿用 v2 的 `BJ-2025-BJ-GAOKAO-Q18(1)/(2)` 一条。
- 全书 book-*.md 逐题 E1 结论的穷尽扫描（超出本轮时间的部分）未完成，见"已知限制"第 1 条。

### 3.【major】门头沟/房山汇编候选行：题型改按题号区间判，纳入待复核块，补齐书稿已收录的缺行

- **题型判定改用北京卷题号区间**（Q1-15选择题/Q16+主观题）替代原来的文本正则粗推。原正则
  `\(\d+分\)|（\d+分）` 只认单一全角/半角括号组合，`BJ-2024-FS-YIMO-Q17` 原文是全角开、半角闭的
  "（11分)"，两种正则都漏判，被误标"选择题"；`BJ-2024-FS-YIMO-Q13`（num=13）原是选择题却因
  `chars>500` 误判"主观题"。v3 按题号区间判定后两题都已改判正确。
- **纳入 assembly_blocks.csv 里 `status=待复核` 的门头沟/房山区块**（原 9 个"已解析"候选行之外，
  另有 5 个 `matched_exam_id` 为空的待复核块：门头沟8/11/14/20、房山15）：其中门头沟8/11、房山15
  能用 book-xuanbi-1.md:308 的官方答案键（D/C/D）反向核实年份为 2024 届，已并入
  `BJ-2024-MTG-YIMO`/`BJ-2024-FS-YIMO` 候选行；门头沟14/20 book-xuanbi-1.md 无可核实的具体结论，
  不代为裁定，标"身份未确认-不计入分母-待复核"单列。
- **补齐书稿已确认收录、但 assembly_blocks.csv/questions.csv 均无独立行的 4 题**（门头沟一模
  Q10/Q18、房山一模Q14/Q18(2)），来源标注为 book-xuanbi-1.md 具名核实（:307,308,401,51），不冒充
  分类器/汇编产物；已列入回传题库线要求题库负责人补登 questions.csv/matrix.csv。
- 结果：门头沟/房山两卷候选行从 v2 的 9 行增至 **18** 行；其中 8 题（门头沟Q8/Q10/Q11、房山
  Q14/Q15/Q18(2)）已按 book-xuanbi-1.md 的"正文9个实际题块与正式键9/9一致"直接标注 `归属_X1=
  COLLECTED`；门头沟Q18 按同一处审计记录明确"只修订审计状态，不改正文和正式槽"，本表**未**因此
  标 COLLECTED，只登记确认负例（不收-无E1）。
- 确认意见提到的"必修三收门头沟Q1、Q3、Q8和房山Q9、Q10"未能在 `book-bixiu-3.md`（必修三对应的
  Skill 记录文件）或其它可读到的 Skill 文本里找到可引用原文核实，本表不代为登记，列为 deferred。

### 4.【major】可复现性：脚本默认读交付目录快照，新增线上-快照对照校验脚本

- `build_attribution_v3.py`、`prep_model_batch_v3.py` 新增 `--inputs-dir`（默认 `inputs_snapshot`），
  不再硬编码指向另一次会话的 `/private/tmp/…/bf450d67…/scratchpad/completeness/classifier`；
  该目录一旦被系统清理，v2 的重跑命令会直接失败。`build_exam_identity_v3.py` 新增
  `--bank-dir`/`--review-dir`/`--matrix` 参数（默认仍指向线上题库，因为该脚本的职责就是核对线上
  最新状态）。
- 新增 `scripts/verify_live_inputs_v3.py`：重跑前先跑这个脚本，对照**当前线上题库文件**
  （`rubric_links.csv`、`exams.csv`、`assembly_blocks.csv`、`matrix.csv`、`bank_duplicate_exams.csv`）
  的实时 SHA-256 与 `inputs_snapshot/MANIFEST.sha256` 登记的快照哈希，不一致就报 `CHANGED` 并提示
  "需要用线上路径重新生成，不能只信旧快照"——取代 v2 README 里"自己对自己"的
  `cd inputs_snapshot && shasum -a 256 -c MANIFEST.sha256`（那条命令只能证明快照没被后续操作篡改，
  测不出题库是否已更新）。
- 补记 `questions.csv`（题库最上游源文件）当前哈希：`13116c9d0409bcb7a9ea025978b9d58f1c03b5635a8e1dc3a2ba314ecfad871d`
  （4398行，2026-09-24记录）。本表脚本不直接读 questions.csv（只读派生的 rubric_links.csv/
  exams.csv/assembly_blocks.csv），故不纳入 verify_live_inputs 的强校验，只留痕供人工判断题库是否
  整体重建过。
- 本次重新执行时，`inputs_snapshot/` 的 8 个快照文件与线上对应文件逐一核对，**全部 OK**（详见
  `verify_live_inputs_v3.py` 输出），说明自 v2 生成以来题库/矩阵未变，本版 attribution.csv 仍可
  信任离线快照复现。

## 目录结构

```
归属表_v1/                       （沿用原目录名，内容已是v3）
  README.md                      本文件
  exam_identity.json             缺口1 v3：新增 dup_alias_qid_pairs、assembly_pending_review、
                                  unresolved_notes（书稿标签重定向deferred说明）
  回传题库线_v3.json              新增2条：门头沟/房山4题补登questions.csv/matrix.csv、
                                  门头沟14/20年份待核实
  skill_overrides.json           19条具名核实覆盖（v2的5条+v3新增14条，均带原文出处）
  attribution.csv                总行数1950（v2的1941+9条新增门头沟/房山候选），新增canonical_qid列
  attribution_options.csv        题肢级辅助表（未变更逻辑）
  attribution_ruled.csv / .changelog.json   apply_rulings_v3.py产物（rulings.jsonl仍为空）
  diffs/
    <MOD>_missing_candidates.csv / _extra_candidates.csv / _out_lowprior_candidates.csv
                                  三层均已按canonical_qid+subq去重、排除身份错误/未确认行
    summary.csv                  八本书差集数量v3汇总（新增去重行数列）
  model_batch/
    boundary_cards.md            沿用v2（本轮未改动，不在本次4条问题范围内）
    slice_estimate.json          沿用v2逻辑，新增识别并排除身份错误/未确认行
  inputs_snapshot/                沿用v2快照（核对后与线上一致，未重新生成）
  rulings.jsonl / rulings.example.jsonl   裁定日志（未变，仍为空/示例）
  scripts/
    build_exam_identity_v3.py    新增 dup_alias_qid_pairs / assembly_pending_review 生成逻辑
    build_attribution_v3.py      blocker①③修复主体；--inputs-dir/--bank-dir参数化
    build_diffs_v3.py            canonical_qid去重、身份行排除
    prep_model_batch_v3.py       --inputs-dir参数化、身份行排除
    apply_rulings_v3.py          沿用v2逻辑，版本号更新
    verify_live_inputs_v3.py     【新增】major④修复：线上-快照哈希对照校验
    （v2脚本一并保留在 v2_存档/scripts/，v1脚本在 v1_存档/scripts/，供比对）
  v1_存档/ v2_存档/                历史版本原样保留
  返修回执_v3.json                逐条对照 确认意见_v2.json 的1 blocker+4 major，记录处理方式、证据、
                                  剩余限制
```

## 差集汇总（`diffs/summary.csv`，v3运行结果）

| 模块 | 漏收候选合计(去重后) | 其中IN | 按裁定可收 | 按裁定不收 | 错收候选(疑似) | OUT低先验 | 去重掉的行数(漏收/OUT/错收) |
|---|---|---|---|---|---|---|---|
| 必修二 B2 | 1192 | 63 | 1152 | 40 | 22 | 86 | 7/0/0 |
| 必修三 B3 | 1328 | 27 | 1298 | 30 | 3 | 150 | 11/0/0 |
| 哲学 PH | 892 | 17 | 857 | 35 | 12 | 628 | 11/5/0 |
| 文化 CU | 983 | 13 | 955 | 28 | 17 | 682 | 9/5/0 |
| 选必一 X1 | 704 | 61 | 668 | 36 | 10 | 989 | 5/8/0 |
| 选必二 X2 | 839 | 44 | 792 | 47 | 0 | 839 | 14/6/0 |
| 思维 MI | 925 | 23 | 898 | 27 | 6 | 854 | 4/11/0 |
| 推理 RE | 1119 | 21 | 1087 | 32 | 7 | 580 | 15/4/0 |

**读法提醒**：与 v2 相比，各book漏收候选合计只有个位数到十几的变化（去重+身份行排除的净效果），
不是大幅波动——这符合预期：v3 修的是"证据/准入/身份三层的判断准确性"，不是重跑分类器改变
IN/MAYBE/OUT三态本身。去重去掉的行数（合计76漏收+39 OUT）主要来自 BJ-2024/2025-HD-QIZHONG
20对孪生题×8模块里此前未被合并、现在按等价类去重的组合。

## attribution.csv 总量（v3）

- 总行数 **1950**（v2的1941 + 门头沟/房山净增9条候选行：18-9）。
- `admission` 分布：完整题-选择题照收 1251、完整题-有E1 378、待裁决-证据未核实 227、
  不收-无E1 52、收-具名例外 39、身份未确认-不计入分母-待复核 2、身份错误-不计入分母 1。
- 新增 `canonical_qid` 列：非别名题等于自身qid；`BJ-2025-HD-QIZHONG` 的20个孪生qid指向其
  `BJ-2024-HD-QIZHONG` 对应qid。

## 已知限制（本轮仍未解决，如实标注，不假装已修复）

1. **exams.csv notes/book-*.md 逐题E1结论的穷尽扫描未完成**：本轮系统性扫描了 exams.csv 全表（仅
   18行含E1/E3逐题限定，已逐条核对）与 book-xuanbi-1.md/book-xuanbi-3.md 里明确提到的具体题号，
   但未对全部 book-*.md（bixiu-2/3、culture、philosophy、reasoning等）做穷尽的"E1"关键词扫描核对
   每一处提及；已扫描部分优先处理了与 rubric_links.csv 自动判定冲突或缺失的题（即会改变归属表
   结果的题），未发现冲突但也未逐条记入override的题不受影响（因为其 rubric_links.csv 结果本身
   已经正确）。
2. **必修三收录门头沟Q1/Q3/Q8、房山Q9/Q10的claim未核实**：确认意见提到的这条在 book-bixiu-3.md
   中未找到对应原文，本表未代为登记，见 `exam_identity.json` 或 `回传题库线_v3.json`。
3. **书稿标签重定向"2025朝阳期中"→BJ-2026-CY-QIZHONG示例未核实**：全项目grep未命中，deferred。
4. **小问级E1证据仍不完整**：`rubric_links.csv` 的 `question_id` 粒度到题不到小问，
   `BJ-2025-BJ-GAOKAO-Q18(1)/(2)` 沿用v2的待裁决状态（见 skill_overrides.json 的
   `not_included_pending_more_evidence`）。
5. **选择题题肢级判断仍是弱信号**：`attribution_options.csv` 未变更逻辑（同v1/v2限制）。
6. **"哲学与文化边界""政府归必修二还是必修三"两张边界卡**：`boundary_cards.md` 本轮未改动（不在
   本次4条问题范围内），仍如实标"Skill 未规定，需主代理补充"。
7. **OUT-低先验层的真实精度仍未知**：需人工分层抽样验证（同v2限制，未在本轮解决）。
8. **token/调用次数估算的批大小等参数仍是假设值**：需正式执行前用小样本校准（同v2限制）。
9. **旧教材（2020—2022高考）的模块归属**：仍需逐题查原件判断，不能因脚本给IN就跳过人工复核
   （同v1/v2限制）。
10. **classify.py/classified_prod.jsonl/units.jsonl 没有独立于快照之外的"线上路径"**：
    `verify_live_inputs_v3.py` 只能校验5个题库派生文件（rubric_links/exams/assembly_blocks/matrix/
    bank_duplicate_exams），分类器本身是否被重跑过、以哪个版本的 classify.py 生成，需要人工确认
    快照里 `classify.py` 的内容与真正生产使用的版本一致（本轮未变，见inputs_snapshot/README.md）。

## 重跑命令

```bash
cd 归属表_v1
# 先校验线上题库文件是否已变（major④修复：不是自己对自己）
/usr/bin/python3 scripts/verify_live_inputs_v3.py
# 全部OK再重跑；出现CHANGED则先用 --bank-dir/--review-dir 指向线上重新生成
/usr/bin/python3 scripts/build_exam_identity_v3.py --out exam_identity.json --luna-out 回传题库线_v3.json
/usr/bin/python3 scripts/build_attribution_v3.py --identity exam_identity.json --overrides skill_overrides.json \
    --out attribution.csv --options-out attribution_options.csv --inputs-dir inputs_snapshot
/usr/bin/python3 scripts/build_diffs_v3.py --attribution attribution.csv --out-dir diffs
/usr/bin/python3 scripts/prep_model_batch_v3.py --attribution attribution.csv --out model_batch/slice_estimate.json --inputs-dir inputs_snapshot
/usr/bin/python3 scripts/apply_rulings_v3.py --attribution attribution.csv --rulings rulings.jsonl --out attribution_ruled.csv
```
全部脚本 `/usr/bin/python3`（3.9.6）验证通过，脚本开头均设置 `sys.dont_write_bytecode = True`；
两次独立重跑 `exam_identity.json`/`attribution.csv`/`attribution_options.csv`/`attribution_ruled.csv`/
`diffs/`/`model_batch/slice_estimate.json`/`回传题库线_v3.json` 逐字节一致（确定性未破坏，本轮在
scratchpad 与交付目录各验证一次，均通过）。
只读书稿/题库/Skill，未运行 `collab.py`，未改动任何书稿或Skill文件（含 scripts/、inputs_snapshot/）。
