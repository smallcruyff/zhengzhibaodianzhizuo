# BJ-2026-CP-QIMO 独立增量复核 R2

## 结论

**Q16 定点缺陷已清零；本候选在既有 21 题独立复核基础上，`conversion_complete=true`，`merge_ready=true`。**

本次只复核上一回执中的 `FIG-Q16-IMG3-LABEL-DUP`，没有重跑整卷。上一回合已经实际打开教师版 10 页、评分材料 3 页和 4 张内嵌图；本回合对 Q16 的两张实物图、修复回执、生成脚本、Q16 候选和机器完整性记录作定点复核。

本文件是对历史 `independent_verification.md/json` 中唯一缺陷的增量结论；历史 `fail` 记录保留作审计，不代表修复后的当前合并判断。

## Q16 修复核验

| 对象 | 实物与当前条目 | 结果 |
| --- | --- | --- |
| `image2.png` | 实物为红色雕漆器物，下方可读标注“雕漆”；`figures.md/json` 与 Q16 候选的 image2 条目仅把该对象转录为“红色雕漆器物照片／雕漆”。 | pass |
| `image3.png` | 实物为红底彩色刺绣纹样，下方可读标注“京绣”；`figures.md/json` 与 Q16 候选的 image3 条目仅把该对象转录为“红底彩色刺绣纹样照片／京绣”，不再把 image2 的雕漆对象归入 image3。 | pass |
| 空间关系 | 两张图仍在教师版第 4 页题面表格左栏上下排列，分别对应右栏“雕漆”“京绣”说明；拓扑中的并列工艺名是表格关系，不是 image3 对象名误写。 | pass |
| 重建持久性 | `build_candidate.py` 的 `FIGURES["Q16"]["transcriptions"]` 按 `image2.png`、`image3.png` 分别保存转录；`figure_text()` 和 `figure_rows` 均按文件名取值，重建不会把旧的 image3 错配文本写回。 | pass |

当前两个实物文件均已实际查看：`image2.png` 为 544×584 RGBA，`image3.png` 为 541×579 RGBA；候选 `assets/teacher_media/` 副本与 evidence 实物逐一同 SHA。

## SHA 与机器记录

- `image2.png` evidence / candidate asset：`e2ee356dcb817c7fb2f10243686a198dda7c3ce1a136c3cd6099a2e08a1e5f57`。
- `image3.png` evidence / candidate asset：`6e49362e3814ea8f4ab84f580131234f3da66a51e50de862109812c11ad393bb`。
- `candidates/BJ-2026-CP-QIMO-Q16.md` 实物 SHA，且 `complete_candidate.json` 与 `self_check.json` 的 Q16 `candidate_sha256` 均为：`3eae218a503a1e8365dad4b55749a2e06bed203ef83b2ae16b2cb586a30c4b7d`。
- `figure_transcription/figures.md` 实物 SHA 与 `complete_candidate.json.figure_transcription.md_sha256`：`22d08befcceaa13761807d8b6d2f24fbae5a0ed7e50372d9815fab5e04f35737`。
- `figure_transcription/figures.json` 实物 SHA 与 `complete_candidate.json.figure_transcription.json_sha256`：`07c30ed895dfa963b55c6800b6370fbcdfb8bd3daa190ec88e40f281e30cd16c`。
- `self_check.json` 的 `result=PASS_machine_integrity_only`、`candidate_files_ok=true`、`image_links_ok=true`、`manifest_unchanged=true`、`shared_modified=false`；Q16 两个媒体链接的 SHA 与上述 evidence 实物一致。
- 修复回执 `review/q16_image3_repair.md/json` 的 `builder_persistence_fixed=true`，其记录的 Q16、图文回执 SHA 与当前实物一致。

Q16 分值仍保持 `null`：现有来源只明确第二部分合计 55 分，不能倒推 Q16 单题分值；本回合未把缺失分值补成推断值。

## 来源限制（不阻断本次 conversion_complete）

以下是来源边界，不是本次增量复核缺陷：

1. 未提供独立原卷文件；题面继续以教师版 DOCX 身份保留。
2. 未提供独立参考答案文件；教师版答案继续标为 E3，不升级为独立答案或 E1。
3. 未提供学生答卷、教师批注或实得分分页；学生层继续为有依据的 `N/A`，不宣称“没有学生材料”。

这些缺源已在候选与前一独立回执中显式登记，按本项目 conversion 范围不单独阻断 `conversion_complete`；仍须随候选保留，不能在合并时抹去。

## 合并判断

- 当前状态：`pass`（Q16 增量）；上一回合唯一缺陷 `FIG-Q16-IMG3-LABEL-DUP` 已修复并由当前实物、候选、图文转录和重建脚本共同验证。
- 未发现新的 Q16 图文错配、链接断裂、SHA 不一致或重建回退。
- `conversion_complete=true`；`merge_ready=true`。
- 本回执只写入本文件及同目录 `independent_verification_r2.json`，未改候选、共享题库、索引、manifest 或原始来源。
