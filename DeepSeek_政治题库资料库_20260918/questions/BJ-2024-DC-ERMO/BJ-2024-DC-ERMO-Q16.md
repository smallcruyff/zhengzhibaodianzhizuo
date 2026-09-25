# BJ-2024-DC-ERMO-Q16

## 修复身份
- source_provenance: [provenance_registry.md](sources/provenance_registry.md)
- 历史状态已停用（原记录：本文件为基于三套 32 支持包的新候选，内容不等同于旧父稿。）；当前状态以 conversion_manifest.json 与验收回执为准。
- parent_path: `DeepSeek_政治题库资料库_20260918/questions/BJ-2024-DC-ERMO/BJ-2024-DC-ERMO-Q16.md`
- parent_sha256: `639c50417485ea635b515523f98459a4fe9809f90fa706c2f62f7bef67e28cd9`
- repair_sources: [support.md](sources/support_32_subjective/support.md), [native_pptx_extract.md](sources/support_32_subjective/native_pptx_extract.md), [student_layer.json](sources/support_42_student_layer/student_layer.json)
- printed_score: `7`
- printed_subquestion_scores: `{}`
- source_boundary: 原卷、官方参考/等级、阅卷总结、native PPTX、学生答卷分别保留；学生内容不修正、不反推正式槽。

## 来源角色：ORIGINAL_QUESTION（原卷）
- source_pdf: [paper.pdf](sources/legacy_30_sources/originals/paper.pdf)；physical_page=P06
- page_asset: [p06.png](assets/legacy_30_assets/pages/p06.png)
- 原卷机器转写（逐页 raw OCR，保留 OCR 原状）：
```text
第二部分非选择题
本部分共6题，共55分。
16.(7分)
桑基鱼塘的历史可上溯到距今约2500年
的春秋战国时期。其时，古太湖流域民众因地
制宜，将地势低洼处深挖为鱼塘，塘泥堆在鱼塘
四周形成塘基，时光推移，造就了种桑和养鱼相
辅相成、桑地和池塘相连相倚的典型的桑基鱼
塘生态农业景观，并形成了丰富多彩的蚕桑文化。
近年来，某地对原生态桑基鱼塘进行修复性保护和利用，将农业生态、文化、景
观保护以及生态产品开发、休闲农业发展等方面一并谋划；创造性开发了“果基鱼
塘”“菜基鱼塘”等新模式，为乡村振兴赋能；普及鱼桑文化，开发鱼桑文化研学系列
体验课程，孩子们捕鱼采桑、绘蚌壳画、烧鱼汤饭，感受鱼桑文化风情····
一方方鱼塘、一片片桑林穿越千年而来，造福当下，也构成了天地之间一幅流
光溢彩的画卷。
结合材料，运用《哲学与文化》知识，分析为何二千多岁的桑基鱼塘仍未老。
高三思想政治第6页(共11页)
```

## 规范化题面/版面支持
- 规范化来源：[support.md](sources/support_32_subjective/support.md)；原卷题号/分值由 source_matrix 与 original_score_lock 锁定。
- 原卷页视觉检查：[visual_check.md](sources/support_32_subjective/visual_check.md)；P06 图表/框线/表单结构已实际查看。
- Q16 桑基鱼塘照片与设问“为何二千多岁的桑基鱼塘仍未老”保留。

## 来源角色：OFFICIAL_ANSWER_AND_SCORING
- 扫描参考答案/评分标准全文视觉转写：[official_scoring_supplement_visual_transcription.md](sources/transcriptions/official_scoring_supplement_visual_transcription.md)。
- 题级阅卷/native PPTX支持：[support.md](sources/support_32_subjective/support.md)、[native_pptx_extract.md](sources/support_32_subjective/native_pptx_extract.md)。
- 等级表、参考答案、阅卷总结和计分关系不混为一层；不从学生分数图反推固定评分槽。
- 文化角度：文化是人类社会实践的产物，文化是经济政治的反映；中国优秀传统文化的创造性转化和创新性发展；优秀传统文化的当代价值；人民群众是文化创新的主体。
- 哲学角度：事物发展有其规律；事物是普遍联系的；人民是历史的创造者；科学的价值观符合社会发展规律和最广大人民的根本利益。
- PPTX native topology: 框1“桑基鱼塘立足实践、尊重规律、因地制宜” → 框2“保护利用、产业融合、乡村振兴、文化研学” → 框3“乡村振兴、塑造人、人民福祉”；两条横向有向箭头。

## 来源角色：按证据单元分层（Q16 q16_scoring.pptx）

- 原件：[q16_scoring.pptx](sources/legacy_30_sources/originals/q16_scoring.pptx)；SHA-256：896b0f378cbdeb1f970df2a3b24e3cd6fdcb261cfd3ad4cd94b167d6d0a98e08。
- **角色边界：**按证据单元分层：幻灯片2“参考答案”保持 E3；幻灯片4页标题“阅卷细则”，属于《16题评分细则.pptx》这一正式评分载体中对应 Q16 的评分内容，登记为 E1；上方正式评分补充 PDF 及其视觉转写仍保留为另一项来源。幻灯片5“学生问题”是教师归纳，不是本题学生原答；学生原答仍在下方 STUDENT_LAYER。

### 幻灯片2｜E3参考答案原生文字

- 原图：[幻灯片2](assets/legacy_30_assets/q16/slide-02.png)

#### 原生文字对象1

```text
参考答案
```

#### 原生文字对象2

```text
文化角度：
    文化是人类社会实践的产物，文化是经济政治的反映。桑基文化形成于中国人民的农业实践，是中华文化的组成部分，对当今的农业实践仍有指导意义。
    中国优秀传统文化的创造性转化和创新性发展。桑基鱼塘与时代发展相统一，实现桑蚕文化与产业相融合，在推进乡村振兴上发挥作用。
    优秀传统文化的当代价值。优秀文化具有引领风尚、教育人民、服务社会作用。鱼桑文化研学系列体验课程开发让孩子们感受鱼桑文化，促进人的全面发展（丰富人的精神世界，增强人的精神世界）
    人民群众是文化创新的主体，人民群众在实践基础上创造的精神财富不断转化为物质力量，推动乡村振兴。
```

#### 原生文字对象3

```text
哲学角度：
    事物发展有其规律。（坚持一切从实际出发/具体问题具体分析）桑基鱼塘穿越千年遵循了人与自然的发展规律，随时代发展并不断创新，实现了生态景观与产业融合，推动乡村振兴。
    事物是普遍联系的。桑基鱼塘各要素构成了相互联系的系统，体现了人与自然和谐共生。
    人民是历史的创造者，是社会的主体。桑基鱼塘千年未老，服务于人民，不断满足人民对美好生活的追求。
    科学的价值观符合社会发展规律和最广大人民的根本利益。桑基鱼塘是群众生产实践的产物，促进了经济和生态的发展，提高人民生活水平，穿越千年而未老。
```

### 幻灯片4｜E1正式阅卷细则原文（页标题：阅卷细则）

- 原图：[幻灯片4](assets/legacy_30_assets/q16/slide-04.png)

#### 原生文字对象1

```text
阅卷细则
```

#### 原生文字对象2

```text
1.用文化或哲学回答均可得7分，从哲学和文化两个方面回答，文化3分+哲学4分。
2.文化层面：
①从桑基鱼塘的产生：文化是人类社会实践的产物/文化是经济政治的反映。   
②传统文化的发展：中国优秀传统文化的创造性转化和创新性发展。
③优秀的文化功能，最后升华为群众文化创新的作用：优秀传统文化的当代价值、文化的作用。
（每一点结合材料2分，三点可得7分）
3.哲学层面：
①基于规律和实际（实践）证明桑基鱼塘的科学价值：尊重规律、一切从实际出发。
②基于辩证法说明桑基鱼塘的发展过程：坚持发展的观点、联系的观点、立足整体、系统优化、矛盾分析法。
③基于群众观点及价值观内容，体现科学价值观的标准和作用：人民主体地位、群众观点。
（每一点结合材料2分，三点可得7分）
```

### 幻灯片5｜教师反馈原文（页标题：学生问题）

- 原图：[幻灯片5](assets/legacy_30_assets/q16/slide-05.png)

#### 原生文字对象1

```text
学生问题
```

#### 原生文字对象2

```text
    1.知识方面：
    ① 知识定位有误，错答逻辑相关内容；
    ② 简单罗列知识，哲学的知识结构化不清晰。
    2.思维方面：
    本题考查“为何”设问逻辑，学生在哲学的论证思维能力上表现欠佳。
    3.情境方面：
    ① 简单罗列材料；
    ② 情境结构化不清晰，缺少价值层。
```

### 幻灯片6｜教学建议原文

- 原图：[幻灯片6](assets/legacy_30_assets/q16/slide-06.png)

#### 原生文字对象1

```text
教学建议
```

#### 原生文字对象2

```text
  1.试题训练继续注重注重设问结构化、知识结构化和情景结构化。
  2.哲学内容注重思维层次，用哲学思维进行解题。
  3.重视知识的精准表达，要回归教材的核心考点，以试题代教材进行复习。
```

## 来源角色：STUDENT_LAYER
- 原始学生图逐图索引与转写：[student_layer.json](sources/support_42_student_layer/student_layer.json)；本题 2 项。
```json
[
  {
    "item_id": "SL001",
    "subquestion": "Q16",
    "image_path": "assets/student_layer/images/SL001__q16_review__image1.jpeg",
    "source_docx": "sources/legacy_30_sources/originals/q16_review.docx",
    "source_docx_markdown": "[q16_review.docx](sources/legacy_30_sources/originals/q16_review.docx)",
    "source_docx_sha256": "3fe06deac367805d39bc33669269116e42be7e0e03a8f09f14961f5b37532691",
    "media_sha256": "3a3b50b466ea2c7b65216c9891bac04596340984b6e92b4953d580ed5229ea6a",
    "student_original_transcription": "首先要从一切从实际出发，实事求是。在古时，民众因地制宜，挖鱼塘成塘基，形成了符合\n自然和客观规律的桑基鱼塘，其〔局部难辨〕种桑和养鱼相互促进，符合农业发展的要求，具有\n强生命力。其次，桑基鱼塘承载了丰富的鱼桑、鱼桑文化，在今天，依靠桑基鱼塘展示\n中华优秀传统文化的独特魅力，普及鱼桑文化，发挥文化教化人的作用，丰富人们的精神世界，\n提高人们劳动意识及休闲娱乐生活质量〔句末标点局部难辨〕再次，桑基鱼塘在当下的发展是对辩证法\n否定观念。某地对其进行保护性传承和利用，保护其中农业生态、文化多样性，并创造性\n开发“桑基鱼塘”创新模式，实践扬弃，促进创新，为乡村振兴贡献。最后，掌握系统论\n的方法，把握全局〔“观念/观点”局部难辨〕，〔其后有改写/连写，局部难辨〕生态产品开发、休闲农业等方面一并考虑，激发桑基\n鱼塘的活力。",
    "markings": [
      {
        "id": "M1",
        "kind": "overwrite_or_heavy_stroke",
        "color": "black/gray",
        "location": "Q16答案第一视觉行开头‘首先要从’附近",
        "bbox_xywh": [
          137,
          180,
          300,
          85
        ],
        "text": "有覆盖/连写；稳定正文保留，覆盖层不猜读"
      },
      {
        "id": "M2",
        "kind": "visible_insert_or_annotation",
        "color": "gray/black",
        "location": "第3行左侧上方，箭头指向‘强生命力’附近",
        "bbox_xywh": [
          155,
          278,
          520,
          125
        ],
        "text": "可见‘大’及向下箭头；右侧上方补写字样局部难辨"
      },
      {
        "id": "M3",
        "kind": "local_uncertainty",
        "color": "black",
        "location": "第6行‘劳动意识及休闲娱乐生活质量’及句末标点",
        "bbox_xywh": [
          135,
          477,
          475,
          78
        ],
        "text": "劳动意识可读；句末标点局部难辨"
      },
      {
        "id": "M4",
        "kind": "visible_insert_or_annotation",
        "color": "black",
        "location": "第8/9行交界上方",
        "bbox_xywh": [
          760,
          665,
          100,
          70
        ],
        "text": "‘农业’及向下箭头；作为批注/补写保留，不并入清洁正文"
      },
      {
        "id": "M5",
        "kind": "overwrite_or_connected_strokes",
        "color": "black/gray",
        "location": "第9行‘把握全局’之后",
        "bbox_xywh": [
          360,
          688,
          320,
          78
        ],
        "text": "把握全局可读；后续局部有连写/改写，观念/观点及中段不强行定字"
      },
      {
        "id": "M6",
        "kind": "margin_annotation_with_check",
        "color": "black",
        "location": "第8/9行右侧边注区",
        "bbox_xywh": [
          1080,
          650,
          155,
          170
        ],
        "text": "可见边注/划线及勾形标记，具体字样局部难辨"
      },
      {
        "id": "M7",
        "kind": "score",
        "color": "red",
        "location": "right scoring panel",
        "bbox_xywh": [
          1320,
          112,
          150,
          100
        ],
        "text": "7.0",
        "value": 7.0
      }
    ],
    "score": {
      "value": 7.0,
      "display": "7.0",
      "visible": true,
      "source": "red_score_panel",
      "location": "right scoring panel",
      "bbox_xywh": [
        1320,
        112,
        150,
        100
      ]
    },
    "difficult_regions": [],
    "complete_placement": {
      "value": true,
      "basis": "Q16题头、答题框上下边线、全部手写行、右侧评分面板均在图内；底部17题题头为相邻题溢出。"
    },
    "ink_summary": "图面标记见markings；不据答案补写",
    "active_body_sha256": "016e771786c791caedc0802935da482ac9e0520add98e967bd3d82c2db562019",
    "active_body_path": "sources/support_42_student_layer/active_transcriptions/SL001.md",
    "active_review_stage": "41/sl001"
  },
  {
    "item_id": "SL002",
    "subquestion": "Q16",
    "image_path": "assets/student_layer/images/SL002__q16_review__image2.jpeg",
    "source_docx": "sources/legacy_30_sources/originals/q16_review.docx",
    "source_docx_markdown": "[q16_review.docx](sources/legacy_30_sources/originals/q16_review.docx)",
    "source_docx_sha256": "3fe06deac367805d39bc33669269116e42be7e0e03a8f09f14961f5b37532691",
    "media_sha256": "1b212a015f98a77524bb24634a094fd1ab5dc881b52de73f7ff1969a332f8b57",
    "student_original_transcription": "①物质决定意识，意识对物质具有能动作用。我国要建设桑基鱼塘，因地制宜一切\n从实际出发，实事求是，遵循客观事物发展的规律，造成了相辅相成相依连。\n②体系日益丰富着多姿多彩的鱼桑文化，优秀传统文化的创造性发展与创新性发展，\n对我国经济发展有促进作用。\n③联系具有普遍性，事物各要素相互联系，桑基鱼塘与农业、生态等一同进行系统优化，促进当地的\n经济发展，实现发展。\n④把握了保护与开发之间的关系，遵循矛盾的特殊性，对保护和发展基础上进行具体问题具体分析。",
    "markings": [
      {
        "kind": "black_score",
        "text": "6",
        "location": "right upper scoring input"
      },
      {
        "kind": "black_crossout",
        "text": "首行左侧及第二、三行多处重笔/涂改；覆盖字不回填",
        "location": "answer rows"
      },
      {
        "kind": "red_check",
        "text": "至少3处红色勾选",
        "location": "约第二、四、六行"
      }
    ],
    "score": {
      "display": "6",
      "value": 6.0,
      "visible": true,
      "location": "right scoring input field"
    },
    "difficult_regions": [
      {
        "bbox_xywh": [
          0,
          0,
          1490,
          180
        ],
        "description": "首行左半段黑色涂改与屏幕边缘重叠"
      },
      {
        "bbox_xywh": [
          0,
          180,
          1490,
          290
        ],
        "description": "第二、三点多处重笔覆盖；体系日益丰富着附近局部难辨"
      },
      {
        "bbox_xywh": [
          0,
          500,
          1490,
          186
        ],
        "description": "第四点末尾及右侧字迹受裁边/栅格干扰"
      }
    ],
    "complete_placement": {
      "value": true,
      "basis": "source image"
    },
    "ink_summary": "图面标记见markings；不据答案补写",
    "active_body_sha256": "19415ae21af3b9350bc9bdb70597a0d67f5c6461d4225f2d91f456c08611ebf0",
    "active_body_path": "sources/support_42_student_layer/active_transcriptions/SL002.md",
    "active_review_stage": "38 retained;39/a1 boundary"
  }
]
```

## bounded 边界
- 学生图中的涂改、批注、难辨字和得分原样保留；不可辨内容明确标记，不补写。
- 本题学生图完整落位状态按 JSON 逐项保留。
