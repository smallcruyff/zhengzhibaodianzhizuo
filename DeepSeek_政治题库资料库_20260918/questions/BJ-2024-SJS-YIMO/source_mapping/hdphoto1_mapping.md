# hdphoto1.wdp 来源映射与对象级边界

## 结论

`hdphoto1.wdp` 已回源闭合：它不是孤立媒体，也不是第五幅题图，而是原卷 DOCX 中 Q7 图 `image2.png` 的 `a14:imgLayer` 增强层。`word/document.xml` 只有一条 `rId14` 引用，且该引用位于 `rId13` 的同一 `a:blip` 扩展层中。

因此本包将其标为 **mapped enhancement layer / object-level bounded**：保留 WDP 原字节和 SHA，完整记录关系及亮度/对比度效果；不把它当缺文件，也不凭 WDP 单独栅格化结果臆造新文字。Q7 的可见语义由 `image2.png` 承载并已逐项转写。

## 精确定位

| 字段 | 实值 |
|---|---|
| 题号 | Q7 `BJ-2024-SJS-YIMO-Q7` |
| 原卷逻辑页 | 第 2 页 |
| Word-10 主分页 | 第 2 页 |
| DOCX body child / paragraph | 38 |
| 前一段 | paragraph 37，Q7 题干 |
| 后一段 | paragraph 39，Q7 选项 |
| 基础图 | `word/media/image2.png`，`rId13` |
| WDP 层 | `word/media/hdphoto1.wdp`，`rId14` |
| 基础图 SHA | `102afb6f57c6d64ce62546aa4cfeaa995dee077e70fffaf745a46644fe5450cc` |
| WDP SHA | `5b5e0c0e7922f99f879cd1136b2ce31d796c095d1ba8967df1533c307a0071d0` |

## 机器拓扑

```text
word/document.xml
└── pic:blip r:embed=rId13
    ├── Relationship rId13 → word/media/image2.png (base image)
    └── a:extLst/a14:imgProps/a14:imgLayer r:embed=rId14
        ├── Relationship rId14 → word/media/hdphoto1.wdp (JPEG-XR enhancement layer)
        └── a14:brightnessContrast bright=40000 contrast=40000
```

`image2.png` 的 `docPr/cNvPr` 均为 `435995270`，内联显示尺寸为 `4762500×1081720` EMU，像素尺寸为 `1268×288`。四个图 panel 的圆、包含/相交/分割关系及未标区域见同目录机器 JSON。

## 资产与可读边界

- [image2.png](../assets/original_media/image2.png)：Q7 可见基础图，字节 SHA 与原卷 DOCX 一致。
- [hdphoto1.wdp](../assets/original_media/hdphoto1.wdp)：原始 JPEG-XR 层，字节 SHA 与原卷 DOCX 一致。
- [原卷 DOCX 副本（11 包）](../sources/试卷.docx)：用于复核 `document.xml` 与关系文件。
- [机器可读映射](hdphoto1_mapping.json)：包含题号/页码、对象属性、关系边、XML 证据、完整视觉转写和 guards。

本环境未另行解码 WDP 层；这只限制独立增强层的栅格化，不限制 Q7 基础图的语义读取。WDP 没有独立文字节点，故不产生额外题面文字；不得把该对象升级为整页 `conversion_unresolved`。
