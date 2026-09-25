# BJ-2026-CY-QIMO 独立增量复核 r3

## 结论

本轮只复核 r2 的四个缺陷点和修复回执，未重跑此前已通过的 19 题。

**conversion_complete：true。**  
**merge_ready：true（仅表示隔离候选达到合并条件；本工位未执行共享合并）。**

## 定点结果

- Q11：原卷 p003 和候选均为“受商标法保护”，pass。
- Q19：细则 p003 和候选均完整保留“政府履行经济职能（或宏观调控）”，pass。
- Q1–Q15：15/15 均为“不适用（选择题）”，没有“细则继续检索”，pass。
- Q21：新裁图尺寸为 1360×1130，完整包含同学丁末行“的教育体系，多层次人才队伍既能冲击科技前沿，又能落地先进设计”，pass。

## SHA 与回执核对

`review_r2/repair_receipt.json` 列出的五项 SHA 均与实物一致：

- Q11：`15c98fe0b10544fbf07ab70ae472c542768dd3a501b27a9e9c07a4390584b763`
- Q19：`e6b2db9082b95de2df156968c6d695b5733f69a4bd958c0bf0835d934722dca8`
- Q21 裁图：`a53a083cad8708132c6559b7b52170fc18b41ac163a9834eaaa12e66793de4f3`
- `complete_candidate.json`：`4b305945c909432d18ad86f2f98a181a6688126c908de5519ebd47e27f59b48b`
- `self_check.json`：`109c1073fa4adf96d82e4934d77291cbe9d7cce64f2530352d5b81e47c7a59f9`

Q21 候选副本与 evidence 裁图 SHA 相同；当前 `output_sha256.json` 列出的 70 个文件缺失 0、SHA 不匹配 0。

## Builder 重建回归检查

`build_candidate.py` 当前包含明确的重建后置守卫：

- Q11 强制替换为“商标法”；
- Q19 强制恢复“或宏观调控”；
- Q1–Q15 强制改为“不适用（选择题）”；
- `question_index` 和 `e1_rubric.json` 直接生成选择题不适用状态；
- Q21 裁图坐标已扩展至 `(80, 190, 1440, 1320)`，得到完整末行；
- 人类可读回执在结构化文件写入后再做标签规范化。

因此完整执行 builder 不会使四项修复回退。builder 基础模板仍保留旧字面量，但后置守卫在生成候选、完整 JSON、自检和输出 SHA 前执行。

补充：`roles/stem_fidelity.json` 的历史 `corrections_highlights` 仍出现“著作权法”字样；这不改变 Q11 候选题面、完整 JSON 或合并内容，属于非阻断的审计措辞残留。

## 来源限制

原卷仍未提供独立答案键/参考作答，且没有学生原答、样卷、批注、评分标记或实得分。这些保持有依据的 N/A/source limitation，不阻断 conversion_complete 或 merge_ready；不得据题干或细则补造。

## 写入范围

本轮只写入 `independent_verification_r3.md/json`，未修改候选、共享题库、index、manifest、原卷、细则或 `repair_receipt.*`。
