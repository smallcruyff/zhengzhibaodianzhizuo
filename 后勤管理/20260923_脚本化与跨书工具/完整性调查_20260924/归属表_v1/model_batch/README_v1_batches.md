# 逐题模块归属判定 —— 模型批次/金标/合并脚本（2026-09-24）

本文件只说明 `model_batch/` 下新增的批次、金标与合并脚本产物；不改动、不重复
`归属表_v1/README.md`（那是 v3 归属表 CSV/diffs 本身的文档）。只读 attribution.csv、
题库（`bank.py get --with-rubric`）与 Skill（boundary_cards.md），未修改任何书稿/
题库/协作文件/Skill；未运行 `collab.py`；未启动子代理、未开新会话。

## 判定单元与分母

判定单元＝`attribution.csv` 中排除 `admission ∈ {身份未确认-不计入分母-待复核,
身份错误-不计入分母}` 后的全部 1947 行（1266 选择题 + 681 主观题，含 316 个
小问单元）。已收模块与未收模块**同一次**判完（原队列①②合并），即每个单元一次性
输出全部相关模块 + 对已收模块的复判结论，见下方判定结果格式的 `rel`/`chk`。

## 切片内容来源

**不用 `inputs_snapshot/units.jsonl`**（v3 README 与 `model_batch/slice_estimate.json`
已实测确认它对长 rubric 会截断，例如 6883 字截到 6000、9262 字截到 6000）。本轮
1773 个去重 qid 全部现取 `python3 scripts/bank.py get <qid> --with-rubric`
（cwd=题库/scripts，只取 stdout），逐题解析出题面/选项/答案键/评分细则，天然是
题库原文全文，不存在截断问题。

其中 **16 个 qid 题库无独立记录**（`bank.py get` 返回"未找到"）：门头沟/房山一模
的汇编候选片段（`BJ-2024-MTG-YIMO-Q4/Q6/Q7/Q8/Q10/Q11/Q12/Q18`、
`BJ-2024-FS-YIMO-Q2/Q12/Q13/Q14/Q15/Q17/Q18(2)/Q19`），questions.csv/assembly_blocks.csv
均无该题独立行（v3 README 已知限制同一批）。这些单元的题面/答案/细则字段为空，
`evidence_status` 里保留 attribution.csv 的 evidence_detail/downgrade_notes 原文
摘录（书稿 book-xuanbi-1.md 具名核实的唯一可得信息），**不代为回原卷杜撰题面**，
判定时对这些单元只能依据 evidence_status 里的摘录信息，请判定模型对这类单元的
`conf` 谨慎给"低"或"中"。

解析用一个通用分类器（`归属表_v1` 之外，脚本本身未纳入交付范围，逻辑见下）按
`## `/`###`/`####` 标题关键词把 bank.py 输出切成 题面/正式评分材料(E1)/评分材料
候选(未确认)/参考答案/内附答案/内附详解等桶，兼容了目前观测到的全部非标准标题
变体（含英文角色名如 `OFFICIAL_ANSWER_AND_SCORING`、嵌套在其它 H2 桶内的 H3 标题
如"S7答案与通用等级层"下的"### 正式评分材料（E1）"）。抽查已知残留误差（对
1947 个单元）：
- 52 个单元题面为空/极短（`bank.py` 自身报告"本题未取得可作题面的小节"，即
  题库这一层本来就没有可用原卷文本，不是本次解析的 bug；已在每条记录的
  `parser_note` 里标注，判定时须谨慎）；
- 1 个单元（`BJ-2024-DC-YIMO-Q4`）attribution.csv 标 E1 但本次解析未能从文本内
  找到"正式"/"确认"/E1 字样的显式信号，标成了"评分材料候选(未确认)"——细则
  全文本身仍完整保留，只是 `rubric.is_formal_E1` 这个便签可能偏保守，判定模型
  应以细则原文内容为准，不是只看这个便签；
- 138/1266 个选择题的 `options_text` 抽取为空（题面全文里选项仍然都在，只是没能
  单独抽出成独立字段），判定模型请从 `stem_full_text` 里读选项。

以上残留误差数量都很小（<3% 或已知的题库层面缺口），本轮时间内未继续追杀到零；
如需更高精度，可用 `attribution_run/parse_bank.py`（我的临时脚本，未纳入交付
范围）里的 `classify()`/`extract_options()` 继续加规则。

## 目录内容

```
model_batch/
  boundary_cards.md          沿用v3，未改动
  slice_estimate.json        沿用v3，未改动
  gold/
    gold_units.json          120个金标单元（70选择+50主观），含 gold_reasons 说明抽样依据
    gc01.json..gc04.json     金标选择题校准批次（与全量批次同格式同上限）
    gs01.json..gs05.json     金标主观题校准批次
  batches/
    c001.json..c060.json     全量选择题批次（排除金标单元），每批≤60单元且≤45000字符
    s001.json..s060.json     全量主观题批次（排除金标单元），每批≤25单元且≤45000字符
README_v1_batches.md          本文件
```

`scripts/compare_to_gold.py`、`scripts/merge_judgments.py` 是本轮新增的两个确定性
脚本（在 `归属表_v1/scripts/` 下，随 attribution 系列脚本一起交付）。

## 判定结果文件格式（供后续模型判定批次时遵循）

```json
{"batch_id": "c001", "judge": "<模型名>", "units": [
  {"unit_id": "...",
   "rel": {"B3": "主", "B2": "跨"},
   "opt": {"①": ["B3"], "②": ["B2","B3"], "③": [], "④": ["B1"]},
   "chk": {"B3": "维持", "PH": "错收"},
   "conf": "高|中|低",
   "why": "≤40字"}]}
```
模块代号：B1(仅用于剔除，无独立成书)、B2、B3、PH、CU、X1、X2、MI、RE。`chk` 只需
对本单元 `book_status` 里已标"已收整题"/"已收第N问"的模块给结论。

## 两个新脚本怎么用

1. 先跑金标批次（`gold/gc*.json`、`gold/gs*.json`）判定，人工/主代理核校后落地
   `gold/gold_final.json`（同一 `units` 格式，`rel`/`chk` 是终裁）。
2. 用 `compare_to_gold.py --gold gold/gold_final.json --judgments "gold/judgments/*.json"
   --out compare_report.json` 核验金标批次判定质量（分选择题/主观题、分模块的
   precision/recall/F1，chk 一致率，"错收"类单独的 precision/recall）。
3. 质量达标后再跑全量批次（`batches/c*.json`、`batches/s*.json`）判定，产物放
   `model_batch/judgments/`。
4. 用 `merge_judgments.py --judgments-dir model_batch/judgments --rulings rulings.jsonl
   --rule-version <戳> --escalation-out model_batch/escalation` 把判定结果并入
   `rulings.jsonl`（`ruler=model:<judge>:<batch>`，幂等、可重复跑不会重复追加），
   同时找出缺判/conf低/chk=错收的单元，按≤40单元一批切到 `model_batch/escalation/`。
5. 升级批次判完后，再跑一次 `merge_judgments.py`，加
   `--escalation-judgments-dir model_batch/escalation/judgments --final`，用升级结果
   覆盖原判后重建 `attribution_ruled.csv` 与 `book_lists/<MOD>_collected.csv`
   （8本书各自的"应收录"清单，供回传题库线/合稿参考；`rulings.jsonl` 里的候选值
   不直接等同书稿真的改了，书稿是否真的增删仍需人工/主代理确认）。

## 已知限制（如实标注）

1. 选项抽取（`options_text`）对约 11% 的选择题失败，需回 `stem_full_text` 读；
2. 52 个单元题面为空是题库本身的缺口，不是本次批次生成的 bug；
3. 1 个单元的 `rubric.is_formal_E1` 标签可能偏保守（细则原文本身完整）；
4. 16 个单元题库无独立记录，判定信息只有 attribution.csv 摘录的书稿具名核实原文；
5. 批大小按"json.dumps(unit, indent=1)"字符数打包，工作阈值取 39500（留出缩进/
   结构开销的安全边际），实测全部 129 个批次文件（120 全量 + 9 金标）均 ≤45000
   字符，最大 42908 字符；
6. `merge_judgments.py` 里 `rel=主/跨→value=IN`、`chk=错收→value=OUT` 等只是往
   `rulings.jsonl`/`attribution_ruled.csv` 写候选值，供人工判断，**不代表书稿已经
   被改动**——书稿增删仍按项目一贯规则由主代理/人工核定后另行执行。
