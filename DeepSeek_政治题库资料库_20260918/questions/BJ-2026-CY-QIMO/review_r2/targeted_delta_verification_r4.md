# BJ-2026-CY-QIMO 冻结批次定点增量复核 r4

## 结论

本轮只回源核对指定的原卷 p4/p5/p8、细则 p2/p4，以及当前隔离候选 Q16/Q18/Q21；没有重扫其他题，也没有改动候选或 `controller_ready`。

**conversion_complete：true。** 四项定点内容均达到本轮要求，当前 `candidates/` 可交总控重新物化。

**merge_ready：true（有条件）。** 只能用本次重建后的隔离候选重新打包；现有 `controller_ready/` 是旧物化包，不能直接复用。

## 定点回源结果

- **Q16：pass。** 实际打开原卷 `evidence/paper_pages/p004.png` 与 `p005.png`：p4 含 Q16 全部题干、配图和设问，题目在 p4 收束；p5 从 Q17 开始。当前 Q16 候选声明原卷页 `[4]`，并明确写出 p5 不属于 Q16。候选 SHA-256：
  `4c5a3e15f739e3d09acd4f92dbf677b722637e5ea9b7afc544a5d083493e6ed9`。

- **Q21 题面框线：pass。** 实际打开原卷 `evidence/paper_pages/p008.png` 及当前裁图：教师文字为单独的上方圆角框；甲、乙、丙、丁四段文字共用一个下方圆角框，且裁图保留丁的末行。候选明确记录该拓扑。裁图 SHA-256：
  `a53a083cad8708132c6559b7b52170fc18b41ac163a9834eaaa12e66793de4f3`；Q21 候选 SHA-256：
  `7ba079ce081396ec94037779f628ef7e0ba258761dd75e927a7b6b8bf0a682e2`。

- **Q18 细则 p2：pass（按本轮指定文字门槛）。** 实际打开 `evidence/rubric_pages/p002.png`。当前 E1 保留疑似原件错字片段“未按照未全面、诚信原则”，并保留“需结合材料”。Q18 候选 SHA-256：
  `96757979f4efaa29191473488e226fe5de102aa00e534ae26d8cf36fd56db6c7`。

  版面注意：原页视觉上将“需结合材料”置于该评分块相邻的第4点括注；当前候选也保留该短语，但其重建文本将短语放进第3点括号、而第4点保留“结合材料”。本轮按父任务明确的“疑似错字＋含需结合材料”门槛通过；若总控要求逐行位置完全照录，应在重打包前另作取舍。

- **Q21 细则 p4：pass。** 实际打开 `evidence/rubric_pages/p004.png`：制度优势三段属于同一合并角度，下含三条可选分析路径，并非可平铺为 6 分；右侧合并单元格完整保留“任一角度2分”和“纯经济角度最高6分”。当前 Q21 E1 已显式写成一个合并角度、三路不得展开成 6 分，并保留整表上限。

## 当前 SHA 与 `output_sha256.json`

当前隔离候选的关键实物 SHA 与根目录 `output_sha256.json` 对应项一致：

- Q16：`4c5a3e15f739e3d09acd4f92dbf677b722637e5ea9b7afc544a5d083493e6ed9`
- Q18：`96757979f4efaa29191473488e226fe5de102aa00e534ae26d8cf36fd56db6c7`
- Q21：`7ba079ce081396ec94037779f628ef7e0ba258761dd75e927a7b6b8bf0a682e2`
- `complete_candidate.json`：`67e69a86792555b1c6b1386b4d092b99f8d6005698cd1926035b9ce061618de6`
- `self_check.json`：`c6bd2019d7c9e573e889905f80a4d54a228439622797bb4e8333fa460da7e4d8`

对当前 `output_sha256.json` 的 161 个条目做机械实物核对：缺失 0、SHA 不匹配 0。该“全表一致”包含旧 `controller_ready` 文件自身的旧哈希，不表示旧包与新候选相同。

## prior R3 旧哈希状态

R3 修复回执中的 Q11、Q19、Q21 裁图哈希仍与当前实物一致，但重建后完整候选与自检哈希已经失效：

- `complete_candidate.json`：旧 `4b305945c909432d18ad86f2f98a181a6688126c908de5519ebd47e27f59b48b` → 当前 `67e69a86792555b1c6b1386b4d092b99f8d6005698cd1926035b9ce061618de6`
- `self_check.json`：旧 `109c1073fa4adf96d82e4934d77291cbe9d7cce64f2530352d5b81e47c7a59f9` → 当前 `c6bd2019d7c9e573e889905f80a4d54a228439622797bb4e8333fa460da7e4d8`
- 现有 `controller_ready` 的 Q16/Q18/Q21 也分别仍是旧物化 SHA，与当前候选不同。

因此：**prior R3 不能作为新候选的完整哈希证明；新候选可以交总控，但必须重新运行物化/重打包。**

## 来源限制与真实未决

无独立答案键/参考作答源；无学生原答、样卷、教师批注、评分标记或实得分。这些按有依据的 N/A/source limitation 保留，不因缺源补造答案，也不阻断本轮 conversion completeness。Q1–Q15 的 E1“不适用（选择题）”沿用已通过的 R3 状态，本轮没有重扫其他题。

## 写入范围

本轮只写入本文件及同目录 `targeted_delta_verification_r4.json`；未改 `build_candidate.py`、候选文件、`controller_ready/`、共享题库、index/manifest、源 PDF 或页图。
