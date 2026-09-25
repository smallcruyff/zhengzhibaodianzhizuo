# BJ-2024-DC-YIMO 学生样卷层独立视觉复核

## 结论

12 张学生/批改样本均已独立逐图查看。PPTX 的 slide→嵌入媒体关系、12 个学生原图副本、渲染页、空原生文字层、9 个原生 shape 副本和 45 条资产 SHA-256 均通过。

学生层可以并入最终候选，但只能以“原图权威＋有界转写”并入，不能宣称手写答案已逐字无歧义完成。Q19 的整张低分辨率答卷、Q16/Q18/Q21 的多处手写字，以及 Q17 的黑色插入批注仍需以原图作为最终证据；所有难辨区域均保留了 inventory 中的区域级坐标。

独立复核没有发现 `transcription.md` 把答案或细则静默填入学生原答的明确证据。可见分数核对结果如下：

| 样本 | 画面分数 | 复核结果 |
|---|---:|---|
| Q16-S1 / slide 28 | 7.0/7 | 通过；黑色手写、下划线保留 |
| Q16-S2 / slide 29 | 7.0/7 | 通过；黑色改写/下划线保留 |
| Q16-S3 / slide 30 | 0/7 | 通过；红色覆盖字为“没答哲学” |
| Q17-S1 / slide 35 | 7.0/7 | 通过；黑色插入批注字形仍有界不确定 |
| Q18-S1 / slide 42 | 8.0/8 | 通过；右侧 2 分、6 分输入框也保留 |
| Q18-S2 / slide 46 | 6.0/6 | 通过；下划线、圈写、改写保留 |
| Q18-S3 / slide 47 | 6.0/6 | 通过；删除/插入、黑色批改和绿色确认保留 |
| Q18-S4 / slide 52 | 6.0/6 | 通过；黑色覆盖/改写和“更改”界面保留 |
| Q19-S1 / slide 58 | 未显示 | 通过；不从答案推分 |
| Q20-S1 / slide 65 | 8.0/8 | 通过；左侧“8分”及 9 个红色“1”标记保留 |
| Q21-S1 / slide 73 | 未显示 | 通过；底部超出答题框提示与学生正文分开 |
| Q21-S2 / slide 74 | 未显示 | 通过；底部同类提示与学生正文分开 |

## 必须随合并修正的父候选文字

父候选 [BJ-2024-DC-YIMO-Q16.md](/Users/wanglifei/Desktop/gpt和claude共同的小窝/后勤管理/MD全库流水线_20260921/receipts/audit_2024_dc_yimo_full/candidates/BJ-2024-DC-YIMO/BJ-2024-DC-YIMO-Q16.md:100) 把 slide 30 的红色覆盖字写成“没答题”。图像和学生层转写均显示为“没答哲学”。合并时应修正这一处；学生答案本身是文化角度内容，不能依据该红色批注把它改写为哲学作答或空答。

## 有界不确定的处理

本次坐标是 `inventory.json` 给出的嵌入原图像素坐标，属于“区域级”框选，并非每个 `[uncertain]` token 一个单独框。这个粒度足以定位原图复核，但不能支持把模糊字强行还原成唯一汉字。原图、`transcription.md`、`inventory.json`、`review.json` 和 SHA 清单应作为一个学生层证据包共同保留。

## 交付回执

- 机器回执：[verification.json](/Users/wanglifei/Desktop/gpt和claude共同的小窝/后勤管理/MD全库流水线_20260921/receipts/verify_2024_dc_yimo_student_samples/verification.json)
- 原始学生层：[transcription.md](/Users/wanglifei/Desktop/gpt和claude共同的小窝/后勤管理/MD全库流水线_20260921/receipts/transcribe_2024_dc_yimo_student_samples/transcription.md)
- 坐标与样本清单：[inventory.json](/Users/wanglifei/Desktop/gpt和claude共同的小窝/后勤管理/MD全库流水线_20260921/receipts/transcribe_2024_dc_yimo_student_samples/inventory.json)
- 资产校验：[sha256sums.txt](/Users/wanglifei/Desktop/gpt和claude共同的小窝/后勤管理/MD全库流水线_20260921/receipts/transcribe_2024_dc_yimo_student_samples/assets/sha256sums.txt)

共享题库、索引、`conversion_manifest.json` 和原始 PPTX 均未修改。
