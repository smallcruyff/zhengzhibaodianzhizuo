# BJ-2025-CY-ERMO 当前共享来源入口

状态：canonical v2 的22题和现有来源转换已由主控验收；`accepted=true`。本状态只针对资料转换，来源角色与边界如下。

- 题稿：Q1–Q22；题级 flat SHA 与父题 SHA 见 `shared_conversion_state.json`。
- 本地来源索引：[sources/index.json](sources/index.json)。
- 三份来源：`sources/试卷.pdf`（10页）、`sources/补充材料_参考答案细则扫描.pdf`（6页）、`sources/细则.docx`（同SHA可读见证22页；Word原生12页另记）。
- DOCX支持：[support/README.md](support/README.md)；完整相对路径 SHA：[support/support_manifest.json](support/support_manifest.json)。

评分角色边界：主卷 p1–p7 为 E0；主卷 p8–p10 与 DOCX 左栏为 E3；DOCX 右栏与补充扫描为 E1，Q1–Q15 无题级 E1；学生层 N/A。Q19 结构化 9 对配对 delta 已由主审与独立复核通过，保留源字面“利用利用”。

现有来源转换已于 2026-09-22T18:23:21.344285+00:00 由主控 01a0c86a-d908-73d0-bdb7-6c3dc614589e 按 approval plan `cy2025-ermo-v2-live-20260922` 验收；源边界、页数和缺源说明见逐卷不可变验收回执。
