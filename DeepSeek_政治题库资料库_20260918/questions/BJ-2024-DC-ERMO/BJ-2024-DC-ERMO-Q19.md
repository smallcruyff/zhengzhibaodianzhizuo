# BJ-2024-DC-ERMO-Q19

## 修复身份
- source_provenance: [provenance_registry.md](sources/provenance_registry.md)
- 历史状态已停用（原记录：本文件为基于三套 32 支持包的新候选，内容不等同于旧父稿。）；当前状态以 conversion_manifest.json 与验收回执为准。
- parent_path: `DeepSeek_政治题库资料库_20260918/questions/BJ-2024-DC-ERMO/BJ-2024-DC-ERMO-Q19.md`
- parent_sha256: `51d9dc69c2491f3047574f05845b7be989cb0c9a5f602a28e5d6547b61230265`
- repair_sources: [support.md](sources/support_32_subjective/support.md), [native_pptx_extract.md](sources/support_32_subjective/native_pptx_extract.md), [student_layer.json](sources/support_42_student_layer/student_layer.json)
- printed_score: `9`
- printed_subquestion_scores: `{"1": 7, "2": 2}`
- source_boundary: 原卷、官方参考/等级、阅卷总结、native PPTX、学生答卷分别保留；学生内容不修正、不反推正式槽。

## 来源角色：ORIGINAL_QUESTION（原卷）
- source_pdf: [paper.pdf](sources/legacy_30_sources/originals/paper.pdf)；physical_page=P09
- page_asset: [p09.png](assets/legacy_30_assets/pages/p09.png)
- 原卷机器转写（逐页 raw OCR，保留 OCR 原状）：
```text
19.(9分)
甲公司从乙公司购入一批电视，约定2024年3月10日发货。乙公司如约发
货后，甲公司不便收货，双方约定货物由快递仓库代为储存至3月20日，仓储费用
由乙公司承担。3月19日，甲公司表示依然不便收货，需要延长仓储时间至3月
30日，乙公司回复“可以”。双方无其他磋商内容。
3月30日，甲公司收货并垫付全部仓储费用后，向乙公司要求“尾款扣除仓储
费用后支付”，乙公司表示拒绝承担3月21日及以后的仓储费用，甲公司因此拒绝
支付尾款。双方协商未果，欲通过诉讼解决争议。
(1)请你选择其中一方进行代理，并撰写起诉状。（7分)
民事起诉状
原告：
被告：
诉讼请求：
事实与理由：
望法院判如所请。
XXX
×年×月×日
(2分)
(2)为避免类似问题产生，我们应该
高三思想政治第9页(共11页)
```

## 规范化题面/版面支持
- 规范化来源：[support.md](sources/support_32_subjective/support.md)；原卷题号/分值由 source_matrix 与 original_score_lock 锁定。
- 原卷页视觉检查：[visual_check.md](sources/support_32_subjective/visual_check.md)；P09 图表/框线/表单结构已实际查看。
- Q19 总分9；(1)7分、(2)2分；民事起诉状框和填空结构保留。

## 来源角色：OFFICIAL_ANSWER_AND_SCORING
- 扫描参考答案/评分标准全文视觉转写：[official_scoring_supplement_visual_transcription.md](sources/transcriptions/official_scoring_supplement_visual_transcription.md)。
- 题级阅卷/native PPTX支持：[support.md](sources/support_32_subjective/support.md)、[native_pptx_extract.md](sources/support_32_subjective/native_pptx_extract.md)。
- 等级表、参考答案、阅卷总结和计分关系不混为一层；不从学生分数图反推固定评分槽。
- 原卷锁定 Q19=9，Q19(1)=7，Q19(2)=2。Q19(1)诉讼请求2分、事实2分、理由按阅卷来源1/2个分别2/3分；Q19(2)合同内容清晰明确2分，仅协商1分，诚信/全面履行单列不给分。

## 来源角色：STUDENT_LAYER
- 原始学生图逐图索引与转写：[student_layer.json](sources/support_42_student_layer/student_layer.json)；本题 4 项。
```json
[
  {
    "item_id": "SL014",
    "subquestion": "Q19(1)",
    "image_path": "assets/student_layer/images/SL014__q19_1_review__image1.png",
    "source_docx": "sources/legacy_30_sources/originals/q19_1_review.docx",
    "source_docx_markdown": "[q19_1_review.docx](sources/legacy_30_sources/originals/q19_1_review.docx)",
    "source_docx_sha256": "d682ecb2695e5e33707dce0cdd1b130fe562eee0beb49bd6a6062cb1e8565394",
    "media_sha256": "36aaff5f996d29362ec41809143fbdeb3688de541da418cd2253928b846bb68d",
    "student_original_transcription": "（1）（7分）原告：乙公司；被告：甲公司。\n诉讼请求：甲公司[付/支付，字形压线]尾款，[要求/扣除]仓储费用；[末尾‘赔偿损失’附近重叠，原字不能完全确认]。\n事实与理由：[甲/乙]公司在合同履行过程中于3月19日经双方协商一致更改合同内容，\n最终[仓储/合同]费用由乙公司承担。乙公司拒绝承担3月20日后的费用，是违背公平原则、\n[对合同/变更合同]的行为。乙公司不承担费用是没有按照合同要求、不履行合同义务的行为，\n有主观过错，因此[末尾因覆盖难辨]造成甲公司的损失，应当承担[末尾因覆盖难辨]。",
    "markings": [
      {
        "kind": "black_overwrite",
        "color": "black",
        "text": "诉讼请求末尾及事实理由第4–6行有覆盖/重笔",
        "bbox_xywh": [
          190,
          95,
          420,
          55
        ]
      },
      {
        "kind": "possible_teacher_annotation",
        "color": "black",
        "text": "图像底部中部有向上箭头及下方黑字，字形难辨，不猜读",
        "bbox_xywh": [
          380,
          260,
          150,
          58
        ]
      }
    ],
    "score": {
      "value": null,
      "display": null,
      "visible": false,
      "source": "not_visible"
    },
    "difficult_regions": [
      {
        "bbox_xywh": [
          400,
          35,
          220,
          55
        ],
        "description": "原告名称末笔与表单线重叠"
      },
      {
        "bbox_xywh": [
          190,
          95,
          420,
          55
        ],
        "description": "诉讼请求末尾覆盖/连写"
      },
      {
        "bbox_xywh": [
          0,
          190,
          636,
          120
        ],
        "description": "事实理由下半段接近原图边界"
      }
    ],
    "complete_placement": {
      "value": false,
      "basis": "原件为表单片段；题头、右侧评分栏及完整答案框不在图内"
    },
    "ink_summary": "图面标记见markings；不据答案补写",
    "active_body_sha256": "57d53ad8b5792baedededc5f93c83ceec83683b77898778ba356d6f80b15526d",
    "active_body_path": "sources/support_42_student_layer/active_transcriptions/SL014.md",
    "active_review_stage": "39/c2"
  },
  {
    "item_id": "SL015",
    "subquestion": "Q19(1)",
    "image_path": "assets/student_layer/images/SL015__q19_1_review__image2.jpeg",
    "source_docx": "sources/legacy_30_sources/originals/q19_1_review.docx",
    "source_docx_markdown": "[q19_1_review.docx](sources/legacy_30_sources/originals/q19_1_review.docx)",
    "source_docx_sha256": "d682ecb2695e5e33707dce0cdd1b130fe562eee0beb49bd6a6062cb1e8565394",
    "media_sha256": "ea6e44bcca90377118bad1ce82b7d268efd28c70fe4547b64fd5bb55dc0947fd",
    "student_original_transcription": "19.（9分）\n（1）（7分）原告：乙公司；被告：甲公司。\n诉讼请求：我方请求被告甲公司依法履行合同义务，向我方支付尾款，\n且我方拒绝承担仓储费用。\n事实与理由：甲公司在我方购入一批电视并签订合同。我方发货，并依照双方的约定，\n将货物储存在快递仓库，并承担了仓储费用。\n甲公司如约收货，我方已完成交付货物的合同义务，因此甲公司应当依法履行合同内容，\n向我方支付尾款。而3月20日至30日期间，\n我方已承担对储存货物费用的义务，且该货物是由甲公司购入，\n我方只具有提货物与运输的义务，因此合同并未涉及由我方支付\n仓储费的内容，因此我方拒绝承担仓储费用。",
    "markings": [
      {
        "kind": "black_underline",
        "color": "black",
        "text": "表单横线和手写下划线；未见明确红色评分/批注",
        "bbox_xywh": [
          0,
          80,
          1264,
          840
        ]
      },
      {
        "kind": "black_overwrite_or_insertion",
        "color": "black",
        "text": "中下段‘合同并未涉及’前后可见覆盖/回笔和上方补笔；不推断确定删除字",
        "bbox_xywh": [
          760,
          530,
          500,
          220
        ]
      }
    ],
    "score": {
      "value": null,
      "display": null,
      "visible": false,
      "source": "not_visible"
    },
    "difficult_regions": [
      {
        "bbox_xywh": [
          0,
          0,
          1264,
          120
        ],
        "description": "题头及左侧界面裁切"
      },
      {
        "bbox_xywh": [
          0,
          420,
          1264,
          260
        ],
        "description": "事实理由中下段与屏幕摩尔纹叠加"
      },
      {
        "bbox_xywh": [
          0,
          680,
          1264,
          267
        ],
        "description": "图片下沿截断，末句之后不可判断"
      }
    ],
    "complete_placement": {
      "value": false,
      "basis": "右侧评分栏、答案框下沿和后续作答不在图内"
    },
    "ink_summary": "图面标记见markings；不据答案补写",
    "active_body_sha256": "66dbf34fbcd0dce198c9eb37a9c12fef7186340f900e106600ab4aebb4c25ecd",
    "active_body_path": "sources/support_42_student_layer/active_transcriptions/SL015.md",
    "active_review_stage": "39/c2"
  },
  {
    "item_id": "SL016",
    "subquestion": "Q19(1)",
    "image_path": "assets/student_layer/images/SL016__q19_1_review__image3.jpeg",
    "source_docx": "sources/legacy_30_sources/originals/q19_1_review.docx",
    "source_docx_markdown": "[q19_1_review.docx](sources/legacy_30_sources/originals/q19_1_review.docx)",
    "source_docx_sha256": "d682ecb2695e5e33707dce0cdd1b130fe562eee0beb49bd6a6062cb1e8565394",
    "media_sha256": "911e41c6630e0de8ce09c12819897a2a34e5620901e1a60cf03f5aeb46ab6480",
    "student_original_transcription": "19.（9分）\n（1）（7分）原告：乙公司；被告：甲公司。\n诉讼请求：我方只愿意承担3月21日之前的仓储费用。\n事实与理由：在2024年3月10日，我方发货后，甲公司以不便\n收货为理由，约定由快递公司代为储存至3月20日，\n其间所有费用由我方承担。但3月19日甲公司仍表示\n收货不便，要求我方延长时间至3月30日，但此时\n我方并未承诺承担这期间的仓储费用。因此，\n希望法院严格审理此案。",
    "markings": [
      {
        "kind": "ui_moire",
        "color": "black/gray",
        "location": "题头及原告/被告行上方",
        "bbox_xywh": [
          0,
          0,
          867,
          115
        ],
        "transcription_effect": "bounded local uncertainty only"
      },
      {
        "kind": "score",
        "value": null,
        "display": null,
        "visible": false,
        "location": "score panel outside crop",
        "bbox_xywh": null
      },
      {
        "kind": "teacher_annotation",
        "visible": false,
        "location": "whole image",
        "text": null
      }
    ],
    "score": {
      "value": null,
      "display": null,
      "visible": false,
      "source": "not_visible"
    },
    "difficult_regions": [],
    "complete_placement": {
      "value": false,
      "basis": "middle/end crop of Q19(1); full answer frame and score panel are not visible"
    },
    "ink_summary": "black handwriting and form lines; no readable red teacher mark",
    "active_body_sha256": "53ffd2885ecb667db8c31d37b28892aff94f5cbfdabf8b6434e461fc00f52879",
    "active_body_path": "sources/support_42_student_layer/active_transcriptions/SL016.md",
    "active_review_stage": "39/review_d"
  },
  {
    "item_id": "SL017",
    "subquestion": "Q19(1)",
    "image_path": "assets/student_layer/images/SL017__q19_1_review__image4.jpeg",
    "source_docx": "sources/legacy_30_sources/originals/q19_1_review.docx",
    "source_docx_markdown": "[q19_1_review.docx](sources/legacy_30_sources/originals/q19_1_review.docx)",
    "source_docx_sha256": "d682ecb2695e5e33707dce0cdd1b130fe562eee0beb49bd6a6062cb1e8565394",
    "media_sha256": "3b2d89e24df12df3086253fe6edad50ea582b5355d29b150e9ac8e6e3dda4208",
    "student_original_transcription": "19.（9分）\n（1）（7分）原告：<del>甲公司</del>乙公司；被告：甲公司。\n诉讼请求：〔开头主语被多重黑色划改并圈住〕甲公司应将尾款扣除仓储费用后支付。\n乙公司不应承担3月20日以后的仓储费用。\n事实与理由：3月19日甲公司因不便收货，乙公司将仓储时间\n延长至3月30日，并未要求乙公司进行仓储费的支付。而先前两公司\n合同约定甲公司承担仓储费至3月20日，所以乙公司对3月20日以后的仓储费没有\n义务支付。\n〔Q19(2)溢出〕（2）（2分）我们应该：在合同中明确表达自己的真实意思，并双方达成妥协。",
    "markings": [
      {
        "id": "M1",
        "kind": "crossout_and_overwrite",
        "location": "原告栏",
        "bbox_xywh": [
          275,
          165,
          300,
          85
        ],
        "text": "原‘甲公司’可见并被重笔划去，现写‘乙公司’",
        "color": "black"
      },
      {
        "id": "M2",
        "kind": "crossout_circle_overwrite",
        "location": "诉讼请求第一行开头主语及中段",
        "bbox_xywh": [
          285,
          245,
          660,
          105
        ],
        "text": "多重横划、覆盖并圈住；只能稳定读出后段‘甲公司应将尾款扣除仓储费用后支付’",
        "color": "black"
      },
      {
        "id": "M3",
        "kind": "circle_or_rewrite",
        "location": "事实与理由第一行，‘甲公司’/‘乙公司’主体处",
        "bbox_xywh": [
          510,
          350,
          440,
          115
        ],
        "text": "主体词附近有圈划/重写；其下方另见同一主体词的黑色补写痕迹，不压平为正文",
        "color": "black"
      },
      {
        "id": "M4",
        "kind": "lexical_insertion_or_visible_word",
        "location": "事实与理由第二行，‘并未要求’",
        "bbox_xywh": [
          270,
          420,
          500,
          95
        ],
        "text": "图中可读‘并未要求’，‘未’不可省略为‘并要求’",
        "color": "black"
      },
      {
        "id": "M5",
        "kind": "score",
        "location": "右侧边缘",
        "bbox_xywh": [
          950,
          120,
          40,
          250
        ],
        "text": "红色分数区部分可见但数字裁切，value=null",
        "color": "red",
        "value": null
      },
      {
        "id": "M6",
        "kind": "spillover",
        "location": "底部",
        "bbox_xywh": [
          0,
          640,
          990,
          102
        ],
        "text": "Q19(2)开头及答案溢出，不并入Q19(1)",
        "color": "black"
      }
    ],
    "score": {
      "value": null,
      "display": null,
      "visible": false,
      "source": "partial_not_readable",
      "location": "right edge red score region clipped"
    },
    "difficult_regions": [],
    "complete_placement": {
      "value": false,
      "basis": "right red score value is clipped; bottom includes Q19(2) spillover and is not a complete Q19(1) page"
    },
    "ink_summary": "black handwriting with heavy crossouts/overwrites and black lower insertion; partial red score region at right edge",
    "active_body_sha256": "2619745d5895214e36941f31e87f7465bd65aa9cdbcfef7029bed3e6abfa36ee",
    "active_body_path": "sources/support_42_student_layer/active_transcriptions/SL017.md",
    "active_review_stage": "39/review_d"
  }
]
```

## bounded 边界
- 学生图中的涂改、批注、难辨字和得分原样保留；不可辨内容明确标记，不补写。
- Q18(2) 有一项 complete_placement=false；Q19(1) 四项 complete_placement=false；这些是原图边界，不删、不补齐。
