# BJ-2024-DC-ERMO-Q20

## 修复身份
- source_provenance: [provenance_registry.md](sources/provenance_registry.md)
- 历史状态已停用（原记录：本文件为基于三套 32 支持包的新候选，内容不等同于旧父稿。）；当前状态以 conversion_manifest.json 与验收回执为准。
- parent_path: `DeepSeek_政治题库资料库_20260918/questions/BJ-2024-DC-ERMO/BJ-2024-DC-ERMO-Q20.md`
- parent_sha256: `0b66a56b6759a83c830bb0e5b393e29371e19cf7f19e6c224f838af8b57f2996`
- repair_sources: [support.md](sources/support_32_subjective/support.md), [native_pptx_extract.md](sources/support_32_subjective/native_pptx_extract.md), [student_layer.json](sources/support_42_student_layer/student_layer.json)
- printed_score: `7`
- printed_subquestion_scores: `{}`
- source_boundary: 原卷、官方参考/等级、阅卷总结、native PPTX、学生答卷分别保留；学生内容不修正、不反推正式槽。

## 来源角色：ORIGINAL_QUESTION（原卷）
- source_pdf: [paper.pdf](sources/legacy_30_sources/originals/paper.pdf)；physical_page=P10
- page_asset: [p10.png](assets/legacy_30_assets/pages/p10.png)
- 原卷机器转写（逐页 raw OCR，保留 OCR 原状）：
```text
20.（7分）

当今世界正经历百年未有之大变局，人类社会发展正处于十字路口。中国的“三大倡议”深刻回答“人类向何处去”的世界之问、历史之问、时代之问，为彷徨求索的世界点亮前行之路。

倡议｜背景｜行动

第1行｜全球发展倡议｜背景：全球发展面临诸多困难和挑战，经济复苏乏力，发展鸿沟加剧，国家间和各国内部发展不平衡、不充分问题日益突出。｜行动：截至2023年6月底，中国与150多个国家、30多个国际组织签署了200多份共建“一带一路”合作文件，形成一大批标志性项目和惠民生的“小而美”项目。设立多个合作发展基金，惠及亚洲、非洲、拉丁美洲等地区100多个国家……

第2行｜全球安全倡议｜背景：当今世界，局部动荡频繁发生，粮食安全、能源资源安全、网络安全、恐怖主义等全球性问题更加突出。｜行动：中国累计派出联合国维和人员5万余人次，在联合国安理会常任理事国中人数最多。倡导处理南海问题“双轨思路”……

第3行｜全球文明倡议｜背景：当今世界，百年未有之大变局加速演进，经济全球化、世界多极化、文化多样化深入发展，不同文明的交汇、碰撞甚至冲突日趋频繁。｜行动：2023年，召开中国共产党与世界政党高层对话会，面向世界首次提出全球文明倡议。开展形式多样的民间外交、公共外交活动，促进各国人民相知相亲……

结合材料，运用《当代国际政治与经济》知识，说明中国的“三大倡议”如何助力人类走向美好未来。

高三思想政治第10页（共11页）
```

## 规范化题面/版面支持
- 规范化来源：[support.md](sources/support_32_subjective/support.md)；原卷题号/分值由 source_matrix 与 original_score_lock 锁定。
- 原卷页视觉检查：[visual_check.md](sources/support_32_subjective/visual_check.md)；P10 图表/框线/表单结构已实际查看。
- Q20 三大倡议背景/行动三列表格保留，不扁平化。

## 来源角色：OFFICIAL_ANSWER_AND_SCORING
- 扫描参考答案/评分标准全文视觉转写：[official_scoring_supplement_visual_transcription.md](sources/transcriptions/official_scoring_supplement_visual_transcription.md)。
- 题级阅卷/native PPTX支持：[support.md](sources/support_32_subjective/support.md)、[native_pptx_extract.md](sources/support_32_subjective/native_pptx_extract.md)。
- 等级表、参考答案、阅卷总结和计分关系不混为一层；不从学生分数图反推固定评分槽。
- 三大倡议各路径1分+效果1分，总论1分，共7分。保留阅卷来源原文，不把学生答案当正式槽。

## 来源角色：STUDENT_LAYER
- 原始学生图逐图索引与转写：[student_layer.json](sources/support_42_student_layer/student_layer.json)；本题 3 项。
```json
[
  {
    "item_id": "SL018",
    "subquestion": "Q20",
    "image_path": "assets/student_layer/images/SL018__q20_review__image1.jpeg",
    "source_docx": "sources/legacy_30_sources/originals/q20_review.docx",
    "source_docx_markdown": "[q20_review.docx](sources/legacy_30_sources/originals/q20_review.docx)",
    "source_docx_sha256": "4c98484a2246ecdd9e1f7c2d58679a3fe54dbb2e95ea6d588c3220e6ea00bf13",
    "media_sha256": "8dda8970d53ffcd0d58da62a8b047e92f7e915994e3f24f2f60d6ea9c1856718",
    "student_original_transcription": "20.（7分）\n中国作为负责任大国，坚持独立自主的和平外交政策，维护世界和平与发展，助力构建人类命运共同体，\n走向美好未来。①全球发展倡议：面对世界发展不平衡、经济复苏乏力的问题，中国以发展倡议推动国与国之间的合作，\n互利共赢，推动开放包容、平等互惠、合作共赢的经济全球化发展，倡导共商共建共享的全球治理观，推动人类合作与发展。\n②全球安全倡议：中国支持联合国符合宪章精神的行动，维护世界和平，主张以协商化解矛盾冲突，促进人类和平与发展。\n③全球文明倡议：中国以平等协商、友好沟通推动意识形态对立缓和，积极倡导人类共同价值，推动世界文化繁荣，增进理解，促进交流。\n21.（7分）",
    "markings": [
      {
        "kind": "score",
        "location": "right scoring panel",
        "bbox_xywh": [
          930,
          270,
          80,
          70
        ],
        "text": "7.0",
        "color": "red",
        "value": 7.0
      },
      {
        "kind": "circled_enumeration",
        "location": "three initiative starts",
        "bbox_xywh": [
          360,
          175,
          620,
          350
        ],
        "text": "①②③ are student-written numbering, not teacher corrections",
        "color": "black"
      },
      {
        "kind": "teacher_annotation",
        "visible": false,
        "location": "whole answer",
        "text": null
      }
    ],
    "score": {
      "value": 7.0,
      "display": "7.0",
      "visible": true,
      "source": "red_score_panel",
      "location": "right scoring panel",
      "bbox_xywh": [
        930,
        270,
        80,
        70
      ]
    },
    "difficult_regions": [],
    "complete_placement": {
      "value": true,
      "basis": "Q20 title, all three initiative sections, answer-box bottom, and next-question title are visible"
    },
    "ink_summary": "black handwriting; red score 7.0; no red textual teacher comment",
    "active_body_sha256": "7ba9485fadbbff9241d2e4a72a8d6a0b8d34a6e8e3c1d97f47954020fadf8482",
    "active_body_path": "sources/support_42_student_layer/active_transcriptions/SL018.md",
    "active_review_stage": "39/review_d"
  },
  {
    "item_id": "SL019",
    "subquestion": "Q20",
    "image_path": "assets/student_layer/images/SL019__q20_review__image2.jpeg",
    "source_docx": "sources/legacy_30_sources/originals/q20_review.docx",
    "source_docx_markdown": "[q20_review.docx](sources/legacy_30_sources/originals/q20_review.docx)",
    "source_docx_sha256": "4c98484a2246ecdd9e1f7c2d58679a3fe54dbb2e95ea6d588c3220e6ea00bf13",
    "media_sha256": "bef2ebfcda3792fc992c7e709eb92168fa15daafd213123464b28b316500eda6",
    "student_original_transcription": "20.（7分）\n因为他们是从“发展”“安全”“文明”这几方面去〔“看/看待”处有重笔涂写〕进行推广倡议的，\n我们的明白这是全球所最需要所向往的方向。时代不同了，人们需要\n的也不同，但这些层面是不可缺少的，提高经济水平的发展，保障\n全球性问题安全的突出，世界多极化、文化多样性的不同层面\n去进行不同的发展，助力人类美好的未来。\n21.（7分）",
    "markings": [
      {
        "kind": "crossout_or_overwrite",
        "location": "first answer line after ‘这几方面去’",
        "bbox_xywh": [
          520,
          100,
          260,
          95
        ],
        "text": "重笔覆盖一/两个字，不能稳定判为‘看’或‘看待’",
        "color": "black"
      },
      {
        "kind": "score",
        "location": "right scoring panel",
        "bbox_xywh": [
          900,
          25,
          80,
          60
        ],
        "text": "1.0",
        "color": "red",
        "value": 1.0
      },
      {
        "kind": "teacher_annotation",
        "visible": false,
        "location": "whole answer",
        "text": null
      }
    ],
    "score": {
      "value": 1.0,
      "display": "1.0",
      "visible": true,
      "source": "red_score_panel",
      "location": "right scoring panel",
      "bbox_xywh": [
        900,
        25,
        80,
        60
      ]
    },
    "difficult_regions": [],
    "complete_placement": {
      "value": true,
      "basis": "Q20 answer box from title through bottom boundary is visible; next-question title is visible"
    },
    "ink_summary": "black handwriting; red score 1.0; no red textual teacher comment",
    "active_body_sha256": "3791ce6f6739890390402e657bd5b788bd15bf1e584b7f9a90f74fffeca740a9",
    "active_body_path": "sources/support_42_student_layer/active_transcriptions/SL019.md",
    "active_review_stage": "39/review_d"
  },
  {
    "item_id": "SL020",
    "subquestion": "Q20",
    "image_path": "assets/student_layer/images/SL020__q20_review__image3.jpeg",
    "source_docx": "sources/legacy_30_sources/originals/q20_review.docx",
    "source_docx_markdown": "[q20_review.docx](sources/legacy_30_sources/originals/q20_review.docx)",
    "source_docx_sha256": "4c98484a2246ecdd9e1f7c2d58679a3fe54dbb2e95ea6d588c3220e6ea00bf13",
    "media_sha256": "5a004cc4557cd7e44dbfd7cd12758e62720b605c4901f90c17cb537af6ca47de",
    "student_original_transcription": "当今世界经济全球化的深入发展，引起各国经济发展不平衡，……，为[局部难辨]，中国可以与其他\n国家之间的联系是通过一带一路，从而推动相关国家发展与社会进步。从而聚合了各国经济发展，促进世界经济稳定，这主要会给全球[局部难辨]提供[局部难辨]。\n坚持共同发展，加强合作，推动经济发展，推动各国共同参与全球治理；中国作为负责任大国，维护世界和平事业，南海问题上坚持“双轨思路”，\n以和平方式解决争端。文明交流互鉴，中国主张的第三大倡议全球文明倡议，推动各国文化交流，尊重文明多样性，促进交流互鉴，\n推动构建人类命运共同体，为人类美好未来发展作出贡献。",
    "markings": [
      {
        "kind": "score",
        "text": "右侧红色总分 2.0",
        "color": "red",
        "bbox_xywh": [
          938,
          176,
          35,
          22
        ]
      },
      {
        "kind": "teacher_annotation",
        "present": false,
        "note": "未见可可靠确认的教师文字批注"
      },
      {
        "kind": "crossout_or_circle",
        "present": false,
        "note": "未见可可靠确认的删除线、圈划或覆盖改写；打印答题横线不计"
      }
    ],
    "score": {
      "value": 2.0,
      "display": "2.0",
      "color": "red",
      "bbox_xywh": [
        938,
        176,
        35,
        22
      ]
    },
    "difficult_regions": [
      {
        "label": "L1_single_character",
        "bbox_xywh": [
          650,
          205,
          110,
          40
        ],
        "text": "为[局部难辨]，",
        "reason": "字符形态受摩尔纹和斜拍影响，禁止按语义补成‘为此’"
      },
      {
        "label": "L2_tail",
        "bbox_xywh": [
          780,
          245,
          258,
          45
        ],
        "text": "全球[局部难辨]提供[局部难辨]",
        "reason": "末段字迹与屏摄纹理粘连"
      }
    ],
    "complete_placement": {
      "value": true,
      "basis": "source image"
    },
    "ink_summary": "黑色手写；右侧红色2.0；无可确认红色文字批注。",
    "active_body_sha256": "a8853f8ca6748497ac8c998715490af6b8ba600d0c58e680d405c3fd8094c2b9",
    "active_body_path": "sources/support_42_student_layer/active_transcriptions/SL020.md",
    "active_review_stage": "41/group_e"
  }
]
```

## bounded 边界
- 学生图中的涂改、批注、难辨字和得分原样保留；不可辨内容明确标记，不补写。
- 本题学生图完整落位状态按 JSON 逐项保留。
