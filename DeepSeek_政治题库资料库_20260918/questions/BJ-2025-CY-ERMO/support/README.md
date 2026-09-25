# BJ-2025-CY-ERMO 细则 DOCX 全页可读支持

本目录是只读源 DOCX 的隔离字体渲染见证包，不改源 DOCX、题目、共享题库、索引、manifest 或 22 题 metadata SHA。

## 结论

- 原 DOCX fresh SHA-256：`73c36c3077dced724eb48b81aec7492e8e5ac59a7f72d7fb729d3581ea3fb5e8`；隔离副本同 SHA。
- 原生 Word 记录：12 页；已保存且可回看双页锚点为 Word p10/p11（Q22 表 7 左 E3、右 E1）。
- 私有字体替代渲染：`renders/docx_readable.pdf`，22 页；PNG `p001`–`p022` 全部存在并已逐页高细节查看。
- 可读性：文字层替换符 0、白方框 0、黑方块 0；p1–p21 有中文内容，p22 为表格边框残留续页。
- 状态：本包已完成本地生成与页面查看，等待另一工位独立复核；不据此晋升共享题库。

## 输入与保护范围

- 输入为 `/00_共同资料/原材料/.../细则.docx` 的字节副本，另与组内 `sources/细则.docx` 做 SHA 等同性核验。
- 渲染链：隔离 DOCX → bundled LibreOffice → PDF → Poppler 150 dpi PNG；私有 FONTCONFIG 只在本目录内，未改系统字体或系统配置。
- 现有主卷 10 页、补充扫描 6 页和 22 题 metadata SHA 只登记既有身份，不重做、不重渲染、不改动。

## 原生结构与表格抽取

- `native_blocks.json` / `native_blocks.md`：完整 `word/document.xml` body blocks；15 个空段落、7 个 1×2 表格；每栏保留原文与 SHA。
- 表格左栏为 E3“阅卷前制定的参考答案”，右栏为 E1“评分细则与答案变通说明”，Q16–Q22 一一对应。

## 源特异 delta

- 发现 1 项、仅限 Q19 表 4 右栏 E1：DOCX 927 字；现有 `S73c36c3077dc.clean.md`/候选右栏仅 57 字提示句。
- DOCX 中缺失于现有 native MD 的内容是 Q19 三个方面的完整建议/理由评分细则；完整对照与 DOCX 原文保存在 `source_specific_delta.json` / `.md`。
- 这只是转写证据 delta；没有改 Q19 题文件、候选 SHA、题号或评分结论。

## 分页映射

- 完整 body block→派生页映射见 `page_block_map.json` / `.md`。逻辑表格页段为：Q16 p1–4；Q17 p4–5；Q18 p6–9；Q19 p9–12；Q20 p12–14；Q21 p14–17；Q22 p17–22。
- Word p10/p11 双页锚点映射到派生 p17–p21 的 Q21 尾部/Q22 全部内容；Word p12 未在既有复核中单独打开，派生 p22 明确标为边框残留，不冒称同页视觉等价。
- 原生 Word p1–p9 的精确分页没有写入 OOXML，也没有在现有回执中保留逐页截图；本包只提供表/题逻辑锚点，不虚构页号。

## 文件索引

- `support_manifest.json`：本包文件清单与 SHA（不自指）。
- `source_sha256.json`：原 DOCX、隔离副本、字体、PDF/PNG 身份。
- `verification.json` / `.md`：可读性、源结构、delta、分页与保护边界。
- `native_word_anchors/`：已有 Word p10/p11 Q22 原生截图副本，仅作双页锚点。

## Shared local entry

本支持树已随本卷复制到共享目录；完整本地文件 SHA 见 [support_manifest.json](support_manifest.json)。
