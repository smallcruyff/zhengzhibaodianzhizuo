# BJ-2025-CY-ERMO DOCX body block 与分页映射

- 原生 Word 记录为 12 页；本包私有字体替代渲染为 22 页 A4 横向。
- 映射基准是 DOCX body block、派生 PDF/PNG 的实际可读页，以及现有 Word p10/p11 Q22 截图；不把不同渲染器的页号当作同页。

## 派生可读页

| 题表 | 派生页 | 页面内容 |
|---|---:|---|
| Q16 表1 | 1–4 | E3/E1 双栏，跨页 |
| Q17 表2 | 4–5 | E3/E1 双栏，跨页 |
| Q18 表3 | 6–9 | E3/E1 双栏，跨页 |
| Q19 表4 | 9–12 | E3/E1 双栏，含完整 DOCX 细则 |
| Q20 表5 | 12–14 | E3/E1 双栏，跨页 |
| Q21 表6 | 14–17 | E3/E1 双栏，跨页 |
| Q22 表7 | 17–22 | E3/E1 双栏；p22 为边框残留 |

## 原生 Word 双页锚点

| Word 页 | 保留证据 | 派生页逻辑锚点 |
|---:|---|---|
| 10 | `native_word_anchors/word_p10_q22_anchor.png`；Q21 尾部与 Q22 起始 | p17–p18 |
| 11 | `native_word_anchors/word_p11_q22_anchor.png`；Q22 继续内容 | p19–p21 |
| 12 | 既有 review 未单独打开；不作 Word 视觉 PASS 证据 | p22 边框残留（仅派生页观察） |

精确 body block 页数组与限制见 `page_block_map.json`。
