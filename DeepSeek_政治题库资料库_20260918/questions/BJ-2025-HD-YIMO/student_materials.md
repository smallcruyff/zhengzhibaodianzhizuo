# BJ-2025-HD-YIMO Q22 学生层实际载荷 v3（卷内物化副本）

> 本文件是供中央选择的完整学生材料候选正文。四组视觉载荷分别保存；学生连续手写、身份和实得分仍有未决，不能标为整题完整转换。
> 卷内物化副本：来源为 v3 `student_materials.md`（SHA-256 `aeebddb5a09d65b4ab0e569c1f8575145fc7eeee2861202cd49198e4cf5c2b5a`）、v3 `manifest.json`（`75e22a5bf8bd34097d1f30e3f997c53a02c2b6e83d182793f17af8a8827ec34e`）。本副本新增四个卷内相对图链，媒体说明行改为指向副本，并保留各自原始来源路径、源图 SHA、页位、可辨片段、标记和未决边界；连续手写、身份与实得分仍未解决。


## 状态与复用边界

- 状态：`reviewed_bounded_candidate`；学生层仍为 `conversion_unresolved`。v2 独立复核见 `../source_payload_repair_v2_q22_student_independent_review/verification.json`，结论为 `UNCERTAIN`。
- 已复用 v1 的 `PASS_BOUNDED_Q22_STUDENT_SOURCE_PAYLOAD_REVIEW`：来源、媒体 SHA、页位、image28=P075 注册和 E1 分层；本 v2 只新增生产者手工直读，不把 v1 bounded PASS 扩大为完整学生文字验收。
- 正式 E1：评分 PDF p5–p9，`PASS_unchanged`；p8/p10 的手写图和 DOCX image28/image29 不替代 E1。
- 未使用 OCR 作为正文；不裁身份、不改学生错误、不由局部 `√+1` 推总分。

## 四组结构化直读

### PDF p8 / p008_img2_student_q22.jpeg（`Q22-STUDENT-PDF-P008-IMG2`）

![PDF p8 原始嵌入图（Q22 header）](assets/student_q22/BJ-2025-HD-YIMO-Q22-p008-pdf-img2.jpeg)

- 来源身份：`not_source_labeled`；answer_like_handwritten_sample_under_Q22_scoring_table。
- 页位：{"source_pdf_page": 8, "printed_page_number": "8", "page_image_path": "后勤管理/MD全库流水线_20260921/receipts/group_2025_west/BJ-2025-HD-YIMO/assets/Sbe30611f2f07/pages/p008.png", "relative_position": "lower portion below the Q22 scoring table; embedded crop starts with printed 22.（10分） header", "embedded_index_label": "p008_img2_student_q22.jpeg"}
- 原图媒体（卷内原样副本）：[`assets/student_q22/BJ-2025-HD-YIMO-Q22-p008-pdf-img2.jpeg`](assets/student_q22/BJ-2025-HD-YIMO-Q22-p008-pdf-img2.jpeg)；原始来源路径：`后勤管理/MD全库流水线_20260921/receipts/group_2025_west/BJ-2025-HD-YIMO/assets/Sbe30611f2f07/embedded/p008_img2_student_q22.jpeg`；源图 SHA-256 `19e05b9982532908894c6ce564270cf058c1898316c45552499a0f828716add6`；卷内副本 SHA-256 `19e05b9982532908894c6ce564270cf058c1898316c45552499a0f828716add6`（字节一致）。
- 逐组手工直读（能辨原样写，不能辨的位置化保留）：

  - 行/位置 `1`（safe_fragments_with_local_gaps）：系统观念是……用联系观点看问题……掌握系统化方法。；未决位置：‘看问题’前后的连接语被红色标记遮挡；行末红色+1覆盖部分字迹
  - 行/位置 `2`（bounded_partial）：……系统观念也作为中国特色社会主义……部分，体现……传统美德。；未决位置：行首与‘中国特色社会主义’后的若干字难辨
  - 行/位置 `3`（safe_opening_bounded_ending）：例如在“全面依法治国是一个系统工程”论断中，运用系统观念，全面依法治……；未决位置：行末超出安全辨读范围
  - 行/位置 `4`（safe_fragments_with_local_gaps）：……建设中国特色社会主义法治体系、建设社会主义法治国家为总目标……；未决位置：行首和‘为总目标’前的连接语难辨
  - 行/位置 `5`（safe_fragments_with_red_overlay）：……法治国家、法治政府、法治社会……科学立法、严格执法……；未决位置：红色√+1覆盖句中词组
  - 行/位置 `6`（bounded_partial）：……公正司法、全民守法……将各方面……综合考虑……；未决位置：大部分连接语及行末难辨
  - 行/位置 `7`（safe_fragments_with_local_gaps）：系统的观点，提出方法……系统观念是具有基础性的思想和工作方法。；未决位置：‘提出方法’前后文字被红色标记压住
  - 行/位置 `下半部另起段`（topic_fragments_only）：系统观念……中国式现代化推进发展时……实现中华民族伟大复兴……；未决位置：统筹兼顾、重点/全局等连接句未闭合

- 可辨片段：`系统观念`、`联系观点看问题`、`掌握系统化方法`、`全面依法治国是一个系统工程`、`中国特色社会主义法治体系`、`法治国家、法治政府、法治社会`、`科学立法、严格执法、公正司法、全民守法`、`系统观念是具有基础性的思想和工作方法`、`中国式现代化`、`实现中华民族伟大复兴`
- 批注/得分边界：{"visible": true, "annotator_identity": "not_source_labeled", "marks": ["√", "+1"], "approximate_visible_clusters": 8, "cluster_locations": ["上段第1行两处（右侧一处部分出框）", "上段中部第4—7行多处", "下段中国式现代化片段两处以上"], "mapping_to_text_spans": "not_one_to_one_established", "mapping_to_formal_score_slots": "not_established", "question_maximum_score_visible": 10, "actual_score_visible": false, "cumulative_score_visible": false, "score_inference_forbidden": true}
- 关系边界：{"same_source_container_as": ["Q22-STUDENT-PDF-P010-IMG1"], "source_relation": "same supplement PDF, different source pages", "content_relation_observed": "both show Q22/system-concept answer-like handwriting and red √+1 marks", "continuation_assertion": "not established", "same_student_assertion": "not established", "same_answer_sheet_assertion": "not established", "cross_source_merge": "forbidden pending source-labeled evidence"}

### PDF p10 / p010_img1_student_q22.jpeg（`Q22-STUDENT-PDF-P010-IMG1`）

![PDF p10 原始嵌入图](assets/student_q22/BJ-2025-HD-YIMO-Q22-p010-pdf-img1.jpeg)

- 来源身份：`not_source_labeled`；answer_like_handwritten_or_scored_sample。
- 页位：{"source_pdf_page": 10, "printed_page_number": "10", "page_image_path": "后勤管理/MD全库流水线_20260921/receipts/group_2025_west/BJ-2025-HD-YIMO/assets/Sbe30611f2f07/pages/p010.png", "relative_position": "upper/middle page image; crop contains no printed Q22 header", "embedded_index_label": "p010_img1_student_q22.jpeg"}
- 原图媒体（卷内原样副本）：[`assets/student_q22/BJ-2025-HD-YIMO-Q22-p010-pdf-img1.jpeg`](assets/student_q22/BJ-2025-HD-YIMO-Q22-p010-pdf-img1.jpeg)；原始来源路径：`后勤管理/MD全库流水线_20260921/receipts/group_2025_west/BJ-2025-HD-YIMO/assets/Sbe30611f2f07/embedded/p010_img1_student_q22.jpeg`；源图 SHA-256 `c1126d41200fa8a2d1df6974b72c59829e46b4581b3d8a66af0f968e85b19181`；卷内副本 SHA-256 `c1126d41200fa8a2d1df6974b72c59829e46b4581b3d8a66af0f968e85b19181`（字节一致）。
- 逐组手工直读（能辨原样写，不能辨的位置化保留）：

  - 行/位置 `1`（topic_fragment_only）：[起首有涂改] ……主题/系统观点……；未决位置：起首涂改区及整句主体难辨
  - 行/位置 `2`（safe_opening_bounded_ending）：系统观念即正确处理好整体与部分的关系，整体与部分相互区别……；未决位置：‘相互区别’之后被红色标记覆盖
  - 行/位置 `3`（safe_fragments_with_local_gaps）：……与部分相互联系，部分影响……；坚持系统观念即立足整体，统筹推进部分发展，运用系统化……；未决位置：行首、红色√+1覆盖处和行末难辨
  - 行/位置 `4`（bounded_manual_read）：化的方法，使整体与部分相互协作，相得益彰。；未决位置：个别字形不稳
  - 行/位置 `5`（safe_fragments_with_local_gaps）：新发展理念作为一个整体作用于国家高质量发展……创新、协调、绿色、开放……；未决位置：‘其又/也是’等连接语难辨
  - 行/位置 `6`（topic_fragments_only）：共享的理念……贯彻新发展理念……落实……原则……；未决位置：句中多个词被红色标记压住
  - 行/位置 `7`（bounded_manual_read）：推动区域间协调发展，推动人与自然和谐共生，坚持‘绿水青山就是金山银山’。；未决位置：句首连接语不稳
  - 行/位置 `8`（safe_fragments_with_local_gaps）：推动高水平对外开放，建设相互尊重、……合作共赢……；推动……；未决位置：中后段被红色√+1覆盖
  - 行/位置 `9`（bounded_manual_read）：辩证思维要求我们用联系、发展、全面的观点认识事物……；未决位置：行末难辨
  - 行/位置 `10`（safe_fragments_with_local_gaps）：用辩证思维方法认识事物，将各种事物联系起来，以……全局……；未决位置：‘以’后的策略/结果表述难辨
  - 行/位置 `11`（safe_fragments_with_local_gaps）：新时代新征程，……在党的领导下，……贯彻新发展理念，从而推动国家高质量发展。；未决位置：主语和中间动词组难辨

- 可辨片段：`系统观念`、`正确处理好整体与部分的关系`、`整体与部分相互区别、相互联系（局部）`、`使整体与部分相互协作，相得益彰`、`新发展理念`、`创新、协调、绿色、开放、共享`、`推动人与自然和谐共生`、`绿水青山就是金山银山`、`推动高水平对外开放`、`辩证思维要求我们用联系、发展、全面的观点认识事物`、`党的领导`、`国家高质量发展`
- 批注/得分边界：{"visible": true, "annotator_identity": "not_source_labeled", "marks": ["√", "+1"], "approximate_visible_clusters": 8, "cluster_locations": ["上部整体/部分段两处以上", "新发展理念段中部三处以上", "辩证思维及末行附近多处"], "mapping_to_text_spans": "not_one_to_one_established", "mapping_to_formal_score_slots": "not_established", "question_maximum_score_visible": null, "actual_score_visible": false, "cumulative_score_visible": false, "score_inference_forbidden": true}
- 关系边界：{"same_source_container_as": ["Q22-STUDENT-PDF-P008-IMG2"], "source_relation": "same supplement PDF, different source pages", "content_relation_observed": "shared system-concept topic and red √+1 notation", "continuation_assertion": "not established", "same_student_assertion": "not established", "same_answer_sheet_assertion": "not established", "cross_source_merge": "forbidden pending source-labeled evidence"}

### DOCX P075 / image28.png（`Q22-STUDENT-DOCX-P075-IMAGE28`）

![DOCX P075 / image28 原始嵌入图](assets/student_q22/BJ-2025-HD-YIMO-Q22-docx-P075-image28.png)

- 来源身份：`not_source_labeled`；handwritten_explanatory_or_answer-planning_note_after_Q22_guidance; not_safe_to_promote_as_student_answer。
- 页位：{"source_docx_paragraph": "P075", "native_render_page": 11, "native_render_page_path": "后勤管理/MD全库流水线_20260921/receipts/group_2025_west/BJ-2025-HD-YIMO/evidence/visual_open/native_docx_render/pages/page-11.png", "relative_position": "full handwritten image after P074 Q22 guidance", "source_order": "P075 precedes P076"}
- 原图媒体（卷内原样副本）：[`assets/student_q22/BJ-2025-HD-YIMO-Q22-docx-P075-image28.png`](assets/student_q22/BJ-2025-HD-YIMO-Q22-docx-P075-image28.png)；原始来源路径：`后勤管理/MD全库流水线_20260921/receipts/group_2025_west/BJ-2025-HD-YIMO/assets/S506347bd4a70/embedded/image28.png`；源图 SHA-256 `1064f4ae06b543f3b75c1450b6c95580cf6c3a93276fd82b0c9d841d004246a3`；卷内副本 SHA-256 `1064f4ae06b543f3b75c1450b6c95580cf6c3a93276fd82b0c9d841d004246a3`（字节一致）。
- 逐组手工直读（能辨原样写，不能辨的位置化保留）：

  - 行/位置 `1`（safe_manual_read）：“全面依法治国是一个系统工程”的概念说明。
  - 行/位置 `2`（safe_topic_fragments_only）：系统观念……整体……整体与部分……；未决位置：系统观念定义的中段连续文字难辨
  - 行/位置 `3`（topic_fragments_only）：……相互联系、相互……，……内部……变化趋势……；未决位置：行首、连接语和行末不闭合
  - 行/位置 `4`（bounded_partial）：……统筹……联系……实现整体……；未决位置：大部分句子被压缩/重叠笔迹覆盖
  - 行/位置 `5`（safe_fragments_with_local_gaps）：……中华文化……重要观点……；未决位置：价值/作用判断句难辨
  - 行/位置 `6`（safe_fragments_with_local_gaps）：在全面依法治国时，从目标层面有法治国家、法治政府、法治社会三个方面……；未决位置：行末及后续说明难辨
  - 行/位置 `7`（safe_keyword_read）：……科学立法、严格执法、公正司法、全民守法……；未决位置：四项之前后的论证关系未闭合
  - 行/位置 `8`（topic_fragments_only）：……相互促进……全面依法治国……；未决位置：行内多处黑色批注/箭头遮挡
  - 行/位置 `9`（topic_fragments_only）：……法治建设……整体……；未决位置：连续原句不可安全闭合
  - 行/位置 `10`（safe_fragments_only）：……思想方法……全面依法治国……；未决位置：下部多行的主体和动词组难辨

- 可辨片段：`“全面依法治国是一个系统工程”的概念说明`、`系统观念`、`整体与部分`、`相互联系`、`中华文化`、`全面依法治国`、`法治国家、法治政府、法治社会`、`科学立法、严格执法、公正司法、全民守法`
- 批注/得分边界：{"visible": true, "annotator_identity": "not_source_labeled", "marks": ["黑色边注", "箭头", "下划线", "局部覆盖/改写"], "annotation_function": "unresolved", "mapping_to_text_spans": "local locations visible but semantics not established", "mapping_to_formal_score_slots": "not_applicable_not_visible", "question_maximum_score_visible": null, "actual_score_visible": false, "cumulative_score_visible": false, "score_inference_forbidden": true}
- 关系边界：{"same_source_container_as": ["Q22-STUDENT-DOCX-P076-IMAGE29"], "source_relation": "adjacent DOCX image-bearing paragraphs P075→P076", "content_relation_observed": "image28标题含‘全面依法治国是一个系统工程’，image29正文以同一短语开头；这只能证明主题/文字重合，不能证明同一学生、同一答卷或续写", "continuation_assertion": "not established", "same_student_assertion": "not established", "same_answer_sheet_assertion": "not established", "cross_source_merge": "forbidden pending source-labeled evidence"}

### DOCX P076 / image29.jpeg（`Q22-STUDENT-DOCX-P076-IMAGE29`）

![DOCX P076 / image29 原始嵌入图](assets/student_q22/BJ-2025-HD-YIMO-Q22-docx-P076-image29.jpeg)

- 来源身份：`not_source_labeled`；Q22 answer-like handwritten sample。
- 页位：{"source_docx_paragraph": "P076", "native_render_page": 12, "native_render_page_path": "后勤管理/MD全库流水线_20260921/receipts/group_2025_west/BJ-2025-HD-YIMO/evidence/visual_open/native_docx_render/pages/page-12.png", "relative_position": "full Q22 answer-like image; lower edge contains a cropped next visual area", "source_order": "P076 follows P075"}
- 原图媒体（卷内原样副本）：[`assets/student_q22/BJ-2025-HD-YIMO-Q22-docx-P076-image29.jpeg`](assets/student_q22/BJ-2025-HD-YIMO-Q22-docx-P076-image29.jpeg)；原始来源路径：`后勤管理/MD全库流水线_20260921/receipts/group_2025_west/BJ-2025-HD-YIMO/assets/S506347bd4a70/embedded/image29.jpeg`；源图 SHA-256 `ecc5cd687b6744acfb8c7013d37822580b3b65375ebf6438d1ca07740540b1c7`；卷内副本 SHA-256 `ecc5cd687b6744acfb8c7013d37822580b3b65375ebf6438d1ca07740540b1c7`（字节一致）。
- 逐组手工直读（能辨原样写，不能辨的位置化保留）：

  - 行/位置 `1`（safe_manual_read）：全面依法治国是一个系统工程，系统观念是具有基础性的思想和工作方法。①系统具有
  - 行/位置 `2`（safe_manual_read）：整体性、有序性和内部的优化趋向。坚持系统观念需要立足整体，从全局出发思考和处理；未决位置：‘内部’后是否缺写‘结构’不替学生补正
  - 行/位置 `3`（safe_manual_read）：问题。推进全面依法治国，从整体上看需要坚持党的领导，坚持人民的主体地位，坚持法
  - 行/位置 `4`（safe_manual_read）：律面前人人平等，坚持从中国实际出发，坚持法治与德治相结合。只有坚持了以上基本原则，
  - 行/位置 `5`（safe_manual_read）：才能在实践中明确方向。②坚持系统观念还要抓好部分，以各部门的发展推进整体的
  - 行/位置 `6`（bounded_manual_read）：发展，使整体效果大于[‘部分分效果’字样，按图保留，不校正]相加之和。；未决位置：‘部分分效果’中间重复字样的原意不判定
  - 行/位置 `7`（safe_manual_read）：在全面推进依法治国中，应当坚持科学立法、
  - 行/位置 `8`（safe_fragments_with_local_gaps）：严格执法、公正司法、全民守法；科学……立法，方能以良法实现善治；严格……规范；未决位置：‘科学’后的修饰语及‘严格’后的修饰语有字形交叠
  - 行/位置 `9`（safe_fragments_with_local_gaps）：执法，方能促进法律执行；……司法，方能维护法律权威，促进社会公平正义；；未决位置：中段司法修饰语和个别字不强行补全
  - 行/位置 `10`（safe_manual_read）：全民增强法治观念和意识，尊法学法守法用法，方能营造法治社会氛围，以各个部门的法
  - 行/位置 `11`（safe_manual_read）：律实践，多元主体的共同依法办事，才能建成法治政府、法治社会、法治国家，实现全
  - 行/位置 `12`（safe_manual_read）：面依法治国的整体系统工程目标。③中华优秀传统文化博大精深、源远流长，系统观念
  - 行/位置 `13`（safe_fragments_with_strike_through）：既是中华优秀传统文化的价值精华，又是中国社会主义革命文化和先进文化的重要组成；未决位置：‘传统文化’附近有黑色划改，不据此改写学生文字
  - 行/位置 `14`（safe_manual_read）：成部分，符合客观发展规律，是党治国理政实践中运用的重要思想和工作方法。
  - 行/位置 `15`（safe_manual_read）：应继续运用该基础性的思想方法，推动全面依法治国的系统工程。
  - 行/位置 `图像下沿`（source_boundary）：[下沿截入的下一视觉区域不归入本答卷正文]；未决位置：image29自身下部灰色截入区域

- 可辨片段：`全面依法治国是一个系统工程`、`系统观念是具有基础性的思想和工作方法`、`整体性、有序性和内部的优化趋向`、`党的领导、人民的主体地位、法律面前人人平等`、`从中国实际出发、法治与德治相结合`、`科学立法、严格执法、公正司法、全民守法`、`尊法学法守法用法`、`法治政府、法治社会、法治国家`、`中华优秀传统文化博大精深、源远流长`、`中国社会主义革命文化和先进文化`、`党治国理政实践中运用的重要思想和工作方法`
- 批注/得分边界：{"visible": true, "annotator_identity": "not_source_labeled", "marks": ["黑色划改/覆盖（局部）"], "red_score_marks_visible": false, "mapping_to_text_spans": "local strike-through visible near traditional-culture wording; function unresolved", "mapping_to_formal_score_slots": "not_established", "question_maximum_score_visible": 10, "actual_score_visible": false, "cumulative_score_visible": false, "score_inference_forbidden": true}
- 关系边界：{"same_source_container_as": ["Q22-STUDENT-DOCX-P075-IMAGE28"], "source_relation": "adjacent DOCX image-bearing paragraphs P075→P076", "content_relation_observed": "image29以‘全面依法治国是一个系统工程’开头，与image28标题同句；仅记录文字/主题重合，不把两图合并为同一答卷", "continuation_assertion": "not established", "same_student_assertion": "not established", "same_answer_sheet_assertion": "not established", "cross_source_merge": "forbidden pending source-labeled evidence"}

## 四组关系结论

- p8 与 p10：只确认同属 `Sbe30611f2f07` 补充评分 PDF 的不同页；都出现 Q22/系统观念语境和红色 `√+1`，但没有同一学生、同一答卷或续页标签。
- image28 与 image29：只确认同属 `S506347bd4a70` DOCX 且 P075→P076 相邻；image28 标题与 image29 开头共享“全面依法治国是一个系统工程”，这属于主题/文字重合，不足以证明同一答卷或续写。
- PDF 两图与 DOCX 两图之间：没有源文件提供的复制/对应标签，不合并。
- 四组都没有安全可核的实际总分；有局部 `√+1` 时只登记标记事实，不能相加或映射正式评分槽。

## 仍未决与异人入口

1. p8、p10、image28 连续手写仍有位置化难辨区；image29 图像下沿截入下一视觉区域，未归入正文。
2. 四组均没有学生姓名、考号或源标签；image28 的题目说明/答题规划角色尤其不能直接提升为学生答卷。
3. 批注者身份、局部标记与正式 E1 分值槽映射、任何累计分/总分均未建立。
4. 当前文件逐段继承已异人核过的 v2 正文，并登记 image28 与 image29 的真实原图措辞；中央移植前仍须保持 `conversion_unresolved`、身份/分值未知边界。
