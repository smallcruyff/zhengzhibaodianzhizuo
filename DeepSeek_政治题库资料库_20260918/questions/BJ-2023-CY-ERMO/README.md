# BJ-2023-CY-ERMO 整卷读取入口

## 卷首与状态

- package_status: `accepted_for_all_available_sources; targeted visual-text repair independently reviewed; formal E1 and student samples not provided`
- question items: 21
- candidate manifest SHA-256: `d2dc956e19511c534bc42cbeab1ff3d1d6794fa2a1b538857e941165b1b44941`
- independent review: `verification/independent_review.json`
- shared bank modified: 2026-09-22按实物SHA合入共享库
- 印刷卷首文字：[exam_front_matter.md](exam_front_matter.md)

## 来源角色

- `S38162016129f`: 原卷题面
- `S96315fb88e87`: 参考答案/E3

原件、完整文本层转写和来源SHA见 [sources/index.json](sources/index.json)；页图与题图在 `assets/`。`[NO_NATIVE_TEXT_LAYER]`表示原件图像为权威。

## 题级导航

- [BJ-2023-CY-ERMO-Q1](BJ-2023-CY-ERMO-Q1.md)
- [BJ-2023-CY-ERMO-Q10](BJ-2023-CY-ERMO-Q10.md)
- [BJ-2023-CY-ERMO-Q11](BJ-2023-CY-ERMO-Q11.md)
- [BJ-2023-CY-ERMO-Q12](BJ-2023-CY-ERMO-Q12.md)
- [BJ-2023-CY-ERMO-Q13](BJ-2023-CY-ERMO-Q13.md)
- [BJ-2023-CY-ERMO-Q14](BJ-2023-CY-ERMO-Q14.md)
- [BJ-2023-CY-ERMO-Q15](BJ-2023-CY-ERMO-Q15.md)
- [BJ-2023-CY-ERMO-Q16](BJ-2023-CY-ERMO-Q16.md)
- [BJ-2023-CY-ERMO-Q17](BJ-2023-CY-ERMO-Q17.md)
- [BJ-2023-CY-ERMO-Q18](BJ-2023-CY-ERMO-Q18.md)
- [BJ-2023-CY-ERMO-Q19](BJ-2023-CY-ERMO-Q19.md)
- [BJ-2023-CY-ERMO-Q2](BJ-2023-CY-ERMO-Q2.md)
- [BJ-2023-CY-ERMO-Q20](BJ-2023-CY-ERMO-Q20.md)
- [BJ-2023-CY-ERMO-Q21](BJ-2023-CY-ERMO-Q21.md)
- [BJ-2023-CY-ERMO-Q3](BJ-2023-CY-ERMO-Q3.md)
- [BJ-2023-CY-ERMO-Q4](BJ-2023-CY-ERMO-Q4.md)
- [BJ-2023-CY-ERMO-Q5](BJ-2023-CY-ERMO-Q5.md)
- [BJ-2023-CY-ERMO-Q6](BJ-2023-CY-ERMO-Q6.md)
- [BJ-2023-CY-ERMO-Q7](BJ-2023-CY-ERMO-Q7.md)
- [BJ-2023-CY-ERMO-Q8](BJ-2023-CY-ERMO-Q8.md)
- [BJ-2023-CY-ERMO-Q9](BJ-2023-CY-ERMO-Q9.md)

## 包结构

本目录只含一份当前MD版本及自包含`assets/`、`sources/`。题稿链接已归一为本目录内`assets/`。


## 当前共享状态

21题、100分；原卷7页与E3答案2页完整保留。Q8包含/交叉/分割关系、Q10哭泣曲线、Q19数值表和汇合箭头结构已独立核验；Q19左侧两支共用一根下箭头，原图下方两框之间的几何关系按原样保留。

[当前共享状态、题目SHA及可携带页图路径](shared_conversion_state.json)。题稿前半部旧质量标记中的assets/S…、evidence/S…与旧候选阶段字样仅为形成记录；当前图片采用各题Markdown实际链接和本状态的source_page_map，完整来源采用sources/index.json。参考答案不能当作正式细则。

现有来源转换已验收；正式细则与个人学生载体缺源，不据此补造。完整题稿和整卷来源可直接读取；新标题与完整段落的筛选读取兼容修复已随共享R2补丁合入，实际共享CLI测试22/22通过（共享bank.py SHA-256：`af0a6a9863fe5c60278b11189849215af15bf7bdaae0ec281c6cac2518781cf5`）；`get --all`仍可读取整份题稿。
