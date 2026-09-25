# BJ-2024-DC-ERMO-Q21

## 修复身份
- source_provenance: [provenance_registry.md](sources/provenance_registry.md)
- 历史状态已停用（原记录：本文件为基于三套 32 支持包的新候选，内容不等同于旧父稿。）；当前状态以 conversion_manifest.json 与验收回执为准。
- parent_path: `DeepSeek_政治题库资料库_20260918/questions/BJ-2024-DC-ERMO/BJ-2024-DC-ERMO-Q21.md`
- parent_sha256: `33d79d905544c8519a57d1655a55ef9e86a51ac24ed1f79ba57f412d0ea6faf5`
- repair_sources: [support.md](sources/support_32_subjective/support.md), [native_pptx_extract.md](sources/support_32_subjective/native_pptx_extract.md), [student_layer.json](sources/support_42_student_layer/student_layer.json)
- printed_score: `7`
- printed_subquestion_scores: `{}`
- source_boundary: 原卷、官方参考/等级、阅卷总结、native PPTX、学生答卷分别保留；学生内容不修正、不反推正式槽。

## 来源角色：ORIGINAL_QUESTION（原卷）
- source_pdf: [paper.pdf](sources/legacy_30_sources/originals/paper.pdf)；physical_page=P11
- page_asset: [p11.png](assets/legacy_30_assets/pages/p11.png)
- 原卷机器转写（逐页 raw OCR，保留 OCR 原状）：
```text
21.（7分）

实现中华民族伟大复兴，是近代以来中华民族最伟大的梦想。100多年来，中国共产党领导中国人民的一切奋斗，归根到底都是为了实现社会主义现代化和中华民族伟大复兴。

【虚线圆角框标题】我国发展的诸多战略性有利条件
【框内项目】
◆ 中国共产党的坚强领导
◆ 中国特色社会主义制度的显著优势
◆ 持续快速发展积累的坚实基础
◆ 长期稳定的社会环境
◆ 自信自强的精神力量

在新中国成立以来特别是改革开放以来长期探索和实践基础上，我国由一穷二白到全面小康，已踏上以中国式现代化全面推进强国建设、民族复兴的新征程。

当今世界变乱交织，百年变局加速演进，我国发展战略机遇和风险挑战并存。

时与势在我们一边，这是我们定力和底气所在，也是我们的决心和信心所在。

实现中华民族伟大复兴进入了不可逆转的历史进程。结合材料，综合运用所学，分析以上战略性有利条件在这一历史进程中是如何发挥作用的。

高三思想政治第11页（共11页）
```

## 规范化题面/版面支持
- 规范化来源：[support.md](sources/support_32_subjective/support.md)；原卷题号/分值由 source_matrix 与 original_score_lock 锁定。
- 原卷页视觉检查：[visual_check.md](sources/support_32_subjective/visual_check.md)；P11 图表/框线/表单结构已实际查看。
- Q21 虚线圆角战略条件框和五条条件保留；目标 PPTX slide1 图层见下。

## 来源角色：OFFICIAL_ANSWER_AND_SCORING
- 扫描参考答案/评分标准全文视觉转写：[official_scoring_supplement_visual_transcription.md](sources/transcriptions/official_scoring_supplement_visual_transcription.md)。
- 题级阅卷/native PPTX支持：[support.md](sources/support_32_subjective/support.md)、[native_pptx_extract.md](sources/support_32_subjective/native_pptx_extract.md)。
- 等级表、参考答案、阅卷总结和计分关系不混为一层；不从学生分数图反推固定评分槽。
- 目标 PPTX slide1为完整 Q21(7分)题图；slide2 native XML含党的领导、制度、经济、社会、文化示例及“至少3个点，2个点4分、3个点7分”。slide3—9隔离为非目标示例/外链，不并入本题。

## 来源角色：按证据单元分层（Q21 q21_scoring.pptx）

- 原件：[q21_scoring.pptx](sources/legacy_30_sources/originals/q21_scoring.pptx)；SHA-256：bdc183dc9541edf3ec26e517b9b69ed5e59bc4ae2bb558bf66b766e5842e835d。
- **角色边界：**按证据单元分层：本页答案示例保持 E3；页末“细则：至少3个点，2个点4分，3个点7分”是阅卷总结载体中对应 Q21 的评分条件，登记为 E1。上方评分补充 PDF 及其视觉转写仍保留为另一项来源；实际学生原答仍在下方 STUDENT_LAYER。

### 幻灯片2｜E3参考作答与E1评分条件原文

- 原图：[幻灯片2](assets/legacy_30_assets/q21/slide-02.png)

#### 原生文字对象1

```text
可以从中国共产党的领导，中国特色社会主义制度优势，中华民族精神等角度回答。
```

#### 原生文字对象2

```text
示例：
党的领导：中国共产党始终发挥总揽全局、协调各方的领导核心作用，以人民为中心，团结带领中国人民接续奋斗，开辟伟大道路，建立伟大功业，是实现民主复兴的根本政治保证。
制度优势：中国特色社会主义制度和国家治理体系，发挥新型举国体制优势，将制度优势转化为治理效能，为实现中华民族伟大复兴提供可靠的制度保障。
经济：持续快速发展积累的坚实基础，我国坚持基本经济制度，经济稳步高质量发展，为实现中华民族伟大复兴提供坚实的物质保障。 ；
社会：主动把握新机遇，顺势而为，化解风险挑战，坚持总体国家安全观，加强社会治安综合治理，为实现中华民族伟大复兴提供稳定的社会条件和良好的内部环境。
文化：自信自强是中华民族的固有品格，中华民族自强不息的民族精神，增强了中国人民战胜风险挑战的志气、底气，为实现中华民族伟大复兴提供了强大精神动力。或坚定四个自信。
细则：至少3个点，2个点4分，3个点7分
```

## 来源角色：STUDENT_LAYER
- 原始学生图逐图索引与转写：[student_layer.json](sources/support_42_student_layer/student_layer.json)；本题 3 项。
```json
[
  {
    "item_id": "SL021",
    "subquestion": "Q21",
    "image_path": "assets/student_layer/images/SL021__q21_review__image1.jpeg",
    "source_docx": "sources/legacy_30_sources/originals/q21_review.docx",
    "source_docx_markdown": "[q21_review.docx](sources/legacy_30_sources/originals/q21_review.docx)",
    "source_docx_sha256": "9019906692e8a1e9fc0c653ac39c94544d0e02c717790f7fad5e84f79b68cd11",
    "media_sha256": "a8695ab0344354585f82189832ebd5c911c889cb48f58aa0f5a2d4e94cd487ac",
    "student_original_transcription": "①坚持中国共产党的领导，发挥总揽全局、协调各方作用，党的领导是中国特色社会主义制度的最大优势，为实现中华民族伟大复兴提供根本政治保证。\n②坚持中国特色社会主义制度，坚持公有制为主体、多种所有制经济共同发展，坚持中国特色社会主义制度自信，为实现中华民族伟大复兴提供制度保障。\n③自信自强的精神，弘扬社会主义核心价值观和民族精神、革命精神，凝聚中华民族共同体意识，在坚持文化自信中推进民族伟大复兴，为其提供精神动力与支撑。",
    "markings": [
      {
        "kind": "score",
        "text": "右侧红色总分7.0",
        "color": "red",
        "bbox_xywh": [
          1013,
          101,
          36,
          25
        ]
      },
      {
        "kind": "teacher_annotation",
        "present": false
      },
      {
        "kind": "crossout_or_circle",
        "present": false
      }
    ],
    "score": {
      "value": 7.0,
      "display": "7.0",
      "color": "red",
      "bbox_xywh": [
        1013,
        101,
        36,
        25
      ]
    },
    "difficult_regions": [],
    "complete_placement": {
      "value": true,
      "basis": "source image"
    },
    "ink_summary": "黑色手写；右侧红色7.0；无可确认红色文字批注。",
    "active_body_sha256": "664d7793566be9d32b793be052fad9c3f28b0ac4f0a8f0e4778308789b9243d0",
    "active_body_path": "sources/support_42_student_layer/active_transcriptions/SL021.md",
    "active_review_stage": "41/group_e"
  },
  {
    "item_id": "SL022",
    "subquestion": "Q21",
    "image_path": "assets/student_layer/images/SL022__q21_review__image2.jpeg",
    "source_docx": "sources/legacy_30_sources/originals/q21_review.docx",
    "source_docx_markdown": "[q21_review.docx](sources/legacy_30_sources/originals/q21_review.docx)",
    "source_docx_sha256": "9019906692e8a1e9fc0c653ac39c94544d0e02c717790f7fad5e84f79b68cd11",
    "media_sha256": "b86819db17943716db0f9851da5f2da7469cbc2abcfa3742a87a494cabf7ed15",
    "student_original_transcription": "①我国坚持中国共产党领导，〔中段局部难辨〕协调各方，〔后段局部难辨〕。\n②我国具有引领未来发展方向的制度优势，〔其后多处局部难辨，保留原图〕。\n③我国自信自强的精神力量，坚持以爱国主义为核心的中华民族精神，〔后段局部难辨〕。\n④我国实行社会主义市场经济体制，〔后段局部难辨〕。",
    "markings": [
      {
        "kind": "score",
        "text": "右侧红色总分7.0",
        "color": "red",
        "bbox_xywh": [
          795,
          50,
          80,
          70
        ]
      },
      {
        "kind": "teacher_annotation",
        "present": false
      },
      {
        "kind": "crossout_or_circle",
        "present": false
      },
      {
        "kind": "insertion_or_marginal_text",
        "text": "〔社会意义／社会稳定，局部难辨〕",
        "color": "black",
        "bbox_xywh": [
          235,
          378,
          105,
          30
        ],
        "location": "③ 段续行与 ④ 行之间的空白处",
        "attribution": "student_or_teacher_uncertain",
        "included_in_clean_transcription": false
      }
    ],
    "score": {
      "value": 7.0,
      "display": "7.0",
      "color": "red",
      "bbox_xywh": [
        795,
        50,
        80,
        70
      ]
    },
    "difficult_regions": [
      {
        "bbox_xywh": [
          20,
          115,
          740,
          325
        ],
        "description": "首句中段、首句后段及第②—④点多处正文受屏摄重笔遮挡；只保留本轮实图可辨片段。"
      },
      {
        "bbox_xywh": [
          235,
          378,
          105,
          30
        ],
        "description": "独立插入末两字局部难辨，读法在“意义／稳定”之间不确定；作者层不明，不并入正文。"
      }
    ],
    "complete_placement": {
      "value": true,
      "basis": "source image and root seven-line source decision"
    },
    "ink_summary": "黑色手写、首行补写、第二行重笔划改及③④间独立补写；右上红色总分7.0，输入框同值；无可确认教师文字点评，不凭字色判断插入/划改作者。",
    "active_body_sha256": "9f263d0b369e93f21d74e432f11792b61f850c5f7032c36e38cb5a458d1ff938",
    "active_body_path": "sources/support_42_student_layer/active_transcriptions/SL022.md",
    "active_review_stage": "46/root_source_decision_pending_independent_review",
    "active_source_decision": "sources/support_42_student_layer/decisions/forensic_transcription_decision.md#SL022"
  },
  {
    "item_id": "SL023",
    "subquestion": "Q21",
    "image_path": "assets/student_layer/images/SL023__q21_review__image3.jpeg",
    "source_docx": "sources/legacy_30_sources/originals/q21_review.docx",
    "source_docx_markdown": "[q21_review.docx](sources/legacy_30_sources/originals/q21_review.docx)",
    "source_docx_sha256": "9019906692e8a1e9fc0c653ac39c94544d0e02c717790f7fad5e84f79b68cd11",
    "media_sha256": "bc001308eac3cea5c3afe1b48e814910baf99475b0d11dda6f29244f68a0bcd4",
    "student_original_transcription": "坚持中国共产党的领导，坚持中国特色社会主义制度，实现社会主义现代化中矛盾的对立统一，我国发展战略机遇和风险挑战并存，坚持稳中求进。\n坚持高速发展积累的坚实基础，发挥中国特色社会主义显著优势，全面推进强国建设，用联系发展的眼光看问题，坚持系统优化法，全面践行社会主义核心价值观，贯彻新发展理念。",
    "markings": [
      {
        "kind": "score",
        "text": "右侧红色总分1.0",
        "color": "red",
        "bbox_xywh": [
          764,
          113,
          34,
          24
        ]
      },
      {
        "kind": "teacher_annotation",
        "present": false
      },
      {
        "kind": "crossout_or_circle",
        "present": false
      }
    ],
    "score": {
      "value": 1.0,
      "display": "1.0",
      "color": "red",
      "bbox_xywh": [
        764,
        113,
        34,
        24
      ]
    },
    "difficult_regions": [],
    "complete_placement": {
      "value": true,
      "basis": "source image"
    },
    "ink_summary": "黑色手写；右侧红色1.0；无可确认红色文字批注。",
    "active_body_sha256": "912c64536aeab03e96860829ee3af8213035467e608abfe8c5e8d098c964c65a",
    "active_body_path": "sources/support_42_student_layer/active_transcriptions/SL023.md",
    "active_review_stage": "41/group_e"
  }
]
```

## bounded 边界
- 学生图中的涂改、批注、难辨字和得分原样保留；不可辨内容明确标记，不补写。
- 本题学生图完整落位状态按 JSON 逐项保留。
