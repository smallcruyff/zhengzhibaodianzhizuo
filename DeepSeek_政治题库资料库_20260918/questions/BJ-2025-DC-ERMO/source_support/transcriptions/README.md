# 完整源文转写入口与证据层级

本目录复用已有缓存，不重新 OCR，也不把缓存提取层冒充视觉真值。

## 主卷

- `cached_native/main_exam_raw.txt`：PDF 原生文字层缓存，完整保留提取字面和异常字符。
- `cached_cleaned/main_exam_full.md`：8页按页分隔的完整清洗稿；原始缓存 SHA 未改变。
- `layout/main_exam_layout.txt`：版面抽取全文，用于核对页内列、跨页与表格顺序。
- 最终视觉依据：`../assets/main_exam_pages/p001.png` 至 `p008.png` 和原 PDF。

## 正式评分材料

- `cached_native/formal_scoring_raw.txt`：PDF 原生文字层缓存。
- `cached_cleaned/formal_scoring_full.md`：5页按页分隔的完整清洗稿。
- `layout/formal_scoring_layout.txt`：版面抽取全文。
- 最终视觉依据：`../assets/formal_scoring_pages/p001.png` 至 `p005.png` 和原 PDF。

## 已核视觉差异

见 `visual_variants.md`。只列既有视觉检查已经确认的差异，其他字符不靠常识或答案推断。题级来源映射见上级 `source_index.json`。
