# BJ-2025-CY-ERMO DOCX 可读支持验证

状态：`support_generated_pending_independent_review`。本回执证明本地隔离渲染、原生结构抽取和页面查看已完成，不等于另一工位独立复核或共享合入。

## 身份与页数

- 原 DOCX fresh SHA：`73c36c3077dced724eb48b81aec7492e8e5ac59a7f72d7fb729d3581ea3fb5e8`；原始、组内 source、隔离副本三者相同。
- Word 原生记录：12 页；已保留 p10/p11 Q22 双页锚点。
- 默认 bundled 渲染基线：10 页，中文大面积缺字/错误字形；仅记为不可读基线。
- 私有字体渲染：22 页 PDF + 22 张 PNG，150 dpi，A4 横向；p1–p21 有内容，p22 为边框残留。

## 可读性

- 文字层字符数：12894；替换符=0，白方框=0，黑方块=0，问号=0。
- 22 张 PNG 已逐页高细节查看：中文、彩色强调、左右栏、表格边界、跨页续接均可读；未见裁切、重叠或缺字。
- 详细每页 SHA、尺寸与 marker 检查见 `verification.json`。

## 源结构与 delta

- OOXML：15 个空段落、7 个 1×2 表格；表格原文抽取见 `native_blocks.*`。
- Q19 表4右 E1：DOCX 927 字，native MD 57 字；完整差异见 `source_specific_delta.*`。
- 本轮不改题、不改候选、不改共享题库/index/manifest，不重做主卷10页、补充扫描6页或22题 metadata SHA。

## 独立复核入口

- 首先看 `README.md`、`page_block_map.md`；随后按 p001–p022 检查 PNG；重点复核 p09–p12（Q19 delta）和 Word p10/p11 双页锚点。
- 独立复核应确认 Q19 DOCX 表4右栏完整细则与现有 native MD 缺漏的差异，但不得在本支持任务中改题。
