> **2026-09-22完整段落读取修复已验证：** `--with-rubric`与任务包保留未分类原始段落及原有标题层级，不自动提升为题面、E1、E3或学生层；重复命中的同一段只输出一次。新题面别名和题级E1边界已独立复核，部署后的实际读取器22项测试通过。完整题稿仍可用 `get <题键> --all` 读取。见[本次合入回执](../后勤管理/MD全库流水线_20260921/receipts/new_controller_20260922/reader_complete_sections_r2_shared_application.json)。

# README_FOR_AI.md — 北京高考政治题源资料库（DeepSeek 独立成果区）

> **2026-09-22 全库转换接续（18:50 PDT 更新）：** Claude 题库线会话已停止并交出写权，由 Codex GPT-6 Luna 接手（登记见 `后勤管理/MD全库流水线_20260921/controller_transition_20260922/state.json`）。逐卷状态以转换主清单为准；每卷 `shared_conversion_state.json` 记录题级 SHA、来源页、缺源与有界残留（`bounded_residual`）。
>
> **读取优先级：** 当前共享题级MD与其 `sources/` 转写/原件入口 → 仍适用的文档级主档 → 原页/原件核疑。题面、参考答案、正式细则、个人学生原答/批注/实得分，以及群体性反馈分别读取。转换验收不提升原始来源证据等级；实际缺源保持N/A。
>
> **2026-09-22读取器已修复并验证：** `bank.py`已支持本轮核定的新题面、E3、学生层、结构副节及混合来源容器，未知角色保持原名和边界；任务包递归复制并重写本地Markdown/图片依赖。`get <题键> --all`仍可读取整份题稿，`--with-rubric`保留所支持来源层；来源可采信性仍按逐卷状态及各层说明核定。验证回执见[读取器合入记录](../后勤管理/MD全库流水线_20260921/receipts/new_controller_20260922/reader_compat_shared_application.json)。

> 本资料库早期由 DeepSeek 建设，当前由 Codex 多组续修，输出根目录为 `DeepSeek_政治题库资料库_20260918/`，
> 与工作区中 GPT / Claude 的制书工程**物理分离**，不写入、不覆盖、不移动任何原始文件。
>
> 输出根：`/Users/wanglifei/Desktop/gpt和claude共同的小窝/DeepSeek_政治题库资料库_20260918`
> 原料根（只读）：`/Users/wanglifei/Desktop/gpt和claude共同的小窝/00_共同资料/原材料`

---

## 1. 目录与用途

| 目录 / 文件 | 用途 | 读取方式 |
| --- | --- | --- |
| `README_FOR_AI.md` | 本文件，读取协议 | **首先读这个** |
| `indexes/` | 原料、试卷、题目、评分材料、资产、来源映射、汇编出处索引 | 检索与定位入口 |
| `processed_markdown/{source_id}.full.md` | 每份来源的**文档级完整原文主档**（清洗后正文） | 需要整份材料或完整上下文时读 |
| `questions/{exam_id}/{question_id}.md` | **经切分的单题文件**（含已配对材料） | 日常按题读取 |
| `questions_reused/BJ-2026-HD-YIMO/` | 既有试点「2026海淀一模」已复核题（本库格式，标注复用来源） | 该卷优先读这里 |
| `reused/2026海淀一模_试点复用/` | 试点产物副本（**失效的 gpt6 绝对链接已改为相对链接**）+ 评分单元 jsonl | 需试点评分表结构时读 |
| `assets/{source_id}/` | 原图、图表、局部截图、内嵌位图 | 遇到图像时**显式打开** |
| `evidence/{source_id}/` | 原始抽取、原始视觉转写、清洗记录、页面渲染 | 复核与追溯 |
| `validation/` | 机器检查、视觉核验记录、问题清单、验收报告 | 验收使用 |
| `scripts/` | 已实际运行的转换、切分、检索、校验脚本 | 后续增量更新 |
| `PROGRESS.md` / `checkpoint.json` | 早期过程记录；当前状态须再读转换主清单 | 历史追溯 |
| `packets/` | `bank.py packet` 生成的任务包 | 按需生成 |

### 证据分层（重要，不要混用）

```
evidence/{sid}/native_text/raw.txt|raw.md   ← 原始抽取（未清洗，永不覆盖）
evidence/{sid}/native_text/pages.jsonl      ← 逐页字符数/分类/文本块 bbox
evidence/{sid}/native_text/slides.jsonl     ← 逐张幻灯片结构（含隐藏标记）
evidence/{sid}/native_text/notes.md         ← 演讲者备注（分区，不混入正文）
evidence/{sid}/native_text/parts.jsonl      ← DOCX 逐块结构（段落/表格）
evidence/{sid}/visual_transcript/*.ocr.txt  ← **OCR 候选转写**（未人工对照，不是定稿）
evidence/{sid}/figure_objects.jsonl         ← 图表对象清单
evidence/{sid}/cleaning_log.jsonl           ← 每次合并/删除的原值与依据
evidence/{sid}/pages/pNNN.png               ← 按需渲染的页面（记录渲染原因）
evidence/{sid}/meta.json                    ← 探针、页面分类、渲染决策
```

`processed_markdown/*.full.md` 是**清洗后正文**；原始抽取保留在 `evidence/`，两者不互相覆盖。

---

## 2. 默认读取流程（7 步）

1. 读本README、转换主清单与目标卷 `shared_conversion_state.json`（如有），再查 `indexes/exams.csv`、`indexes/questions.csv`。索引是题—来源行，不是独立题数；`visual_checked_shared` 是当前核过题面的优先行。
2. 读经切分的单题文件 `questions/{exam_id}/{question_id}.md` 及其中已确认的评分材料。
3. 涉及图像的题目，**显式打开** `assets/` 下对应图片（路径不等于已看见图片）。
4. 切分待复核、版本冲突或需要完整上下文时，先看当前卷 `sources/README.md` 或 `sources/index.json` 指向的同版完整转写；没有新版来源入口时再回 `processed_markdown/{sid}.full.md`。
5. 对转写疑点，打开原始页面 `evidence/{sid}/pages/pNNN.png` 或原件核对。
6. **不要**默认通读全库 PDF、所有渲染图、全部原始 OCR 或整库 Markdown。
7. `extraction_status` 仍有缺口的题目**不得**当成可以直接出版的定稿。

---

## 3. 检索命令

```bash
cd DeepSeek_政治题库资料库_20260918/scripts
/usr/bin/python3 bank.py exams                                  # 全部试卷清单
/usr/bin/python3 bank.py list --year 2026 --region 海淀          # 按条件筛题
/usr/bin/python3 bank.py list --type 选择题 --status candidate_ocr
/usr/bin/python3 bank.py get BJ-2026-HD-YIMO-Q1 --all           # 输出整份单题MD（保持来源分层）
/usr/bin/python3 bank.py search 桑基鱼塘                          # 原文关键词检索
/usr/bin/python3 bank.py packet BJ-2026-HD-YIMO-Q1              # 生成任务包
/usr/bin/python3 bank.py verify                                 # 资料库自检
```

任务包包含：完整题目材料、已确认评分材料、参考答案（单独标注）、候选材料（明确提示未确认）、
来源表、所需图片清单、逐页/逐张来源映射。共享材料在同包中只保留一份，引用关系明确。

---

## 4. 状态语义

| 字段 | 取值 | 含义 |
| --- | --- | --- |
| `extraction_status` | `extracted` | 已从原生文字/结构抽取（尚未逐题内容核验） |
| | `candidate_ocr` | 来自 OCR 候选转写，**必须回原页对照后才能采用** |
| | `verified` | 已实际查看原页并完成内容核验 |
| | `needs_review` / `blocked` | 存在未解决疑点 / 被阻断 |
| `rubric_status` | `已匹配正式材料` | 已确认关联且来源性质明确 |
| | `仅有参考答案` | 只有参考答案，**不得当作评分依据** |
| | `存在候选` | 有候选但尚未确认 |
| | `暂未找到` | 已完成当前授权范围检索仍未找到 |
| | `存在冲突` | 存在多个版本/勘误需分别保存 |

`extraction_status`、`rubric_status`、`needs_review` **三者相互独立**：缺正式细则不等于转写失败；转写完成也不等于细则齐全。

---

## 5. 必须遵守的保真约束

- 不得用摘要替代题干；不得省略材料、选项、图表、评分说明。
- 不得用参考答案冒充正式细则；不得把等级/分档评分表拆成逐点给分。
- 不得凭常识补写模糊文字或分值；无法辨认处统一标记 `〔无法辨认，见具体来源位置〕`。
- 不得自动改正原卷可能存在的知识错误（原件疑似笔误保留原文，另记疑点）。
- 图片的"图中文字转写"与"模型视觉描述"必须分开标注；视觉描述不含考点判断或答案。
- 汇编文件中的题目**不得继承汇编文件自身的年份/地区/题号**，须逐题核实实际出处。
- 原件路径与哈希记录在 `indexes/source_manifest.csv`；原料根变更时改 `scripts/_paths.py` 一处即可，不必逐条改链接。

---

## 5.1 索引文件一览

| 文件 | 内容 |
| --- | --- |
| `indexes/source_manifest.csv` | 来源文件身份（含量哈希、角色、是否汇编、来源根） |
| `indexes/source_aliases.csv` | 同内容多路径别名（64,344 行） |
| `indexes/exams.csv` / `exam_files.csv` | 考试 / 来源文件三层分离登记 |
| `indexes/questions.csv` | 题-来源记录（含 `type_source` 说明题型判定依据） |
| `indexes/rubric_links.csv` | 逐题配对链接（含定位方式与重叠度证据） |
| `indexes/assets.csv` / `source_map.jsonl` | 资产清单 / 逐页逐张来源映射 |
| `indexes/assembly_blocks.csv` / `assembly_provenance.csv` | 汇编逐块出处核定结果 |
| `indexes/reused_pilot_questions.csv` | 试点复用题与本库题的对应 |
| `indexes/split_review.jsonl` | 逐条切分存疑登记（按 `action` 分类） |
| `validation/源文件缺陷登记.md` | **原件自身**缺陷（如 PPT 部件丢失），与处理失败分开 |
| `validation/视觉核验任务清单.jsonl` | 待核验页面（纯扫描页优先，已排序） |
| `validation/06_配对冲突明细.jsonl` | 需人工裁决的题号冲突 |
| `validation/最终报告.md` / `11_读取测试报告.md` | 验收报告 / 端到端读取测试 |

---

## 5.2 单题文件分层与读取顺序（续修 2026-09-21）

原单题文件的 `## 题目原文` 把 原卷 / OCR候选 / 教师版 / 评分材料 / 参考答案 / 讲评
混在同一区，整段取用会夹带答案。现已按角色拆分为独立小节，**原始文本逐字保留、只搬家不改字**：

| 小节 | 内容 | 能否当作题面 |
| --- | --- | --- |
| `## 读取指引（机器可读）` | 指明本题应采用哪个小节作题面 | —（先读这个） |
| `## 题目原文（原卷·native，读取优先）` | 原卷角色的原生文字层 | **可以** |
| `## 原卷 OCR 候选（未逐字对照，不得直接采用）` | 原卷角色的 OCR 候选 | 回原页对照后才可 |
| `## 教师版题面来源（含答案，须回原卷核实）` | 教师版（题面与答案同块） | 须回原卷核实 |
| `## 评分材料来源块（原样保留，配对状态见下）` | 来自评分/阅卷文件 | **不可以** |
| `## 参考答案来源块（不得当作评分依据）` | 参考答案 | **不可以** |
| `## 讲评来源块（含答案与解析，不得当作题面）` | 讲评 | **不可以** |
| `## 待确认材料来源块（角色未定，须人工裁决）` | 角色未定 | **不可以** |

题面优先级：已核验原卷 > 原卷 native > 教师版 native > 原卷 OCR 候选。
若原卷角色缺失，文件顶部有显式告警，`读取指引` 的"采用题面来源性质"会写明替代来源与其风险。

- `## 质量标记 / rubric_status` 现在与头部 `## 配对状态` **同源**，
  由 `indexes/rubric_links.csv` 派生，不再是硬编码的"暂未配对"。
- `## 质量标记 / 图像依赖` 现在是**页级**（`assets/{sid}/pages/pNNN.png`），
  不再只给整个 `source_id` 目录。

**以下是2026-09-21历史定性，不能覆盖新版原卷重建：** 2023海淀二模现已按原卷重建Q1—Q21，Q1/Q3是实际题；2024海淀期中Q0/Q24/Q25已退出有效题目索引，旧路径保留兼容定位并链接原字节历史。其他题按各自实际最新状态。

历史记录的**未入索引5份实物文件**（`BJ-2023-HD-ERMO-Q1/Q3`、`BJ-2024-HD-QIZHONG-Q0`、
`BJ-2026-FT-ERMO-Q20`、`BJ-2026-FT-YIMO-Q5`）已逐项定性为旧残留/错误题键，
**原件保留未删除**，文件顶部有定性横幅；详见
`validation/续修_20260921/五个未入索引文件_定性.md`。其中 Q20/Q5 同时暴露真实题面缺口。

---

## 6. 本资料库的已知边界（务必阅读）

1. **OCR 是候选转写**。已实测 `ocr-vision`（macOS Vision）存在真实错字（如 ①③→①3、告诫→告诚、阻遏→阻過、繁体混入），
   因此扫描卷的题目在完成"回原页对照"前一律为 `candidate_ocr`。
2. **部分试卷为纯扫描件**（无文字层），其题目切分来自 OCR 候选层。
3. **讲评 PPT 的备注**：实测 29 个 pptx 中仅 4 个含真实备注文字，其余为 PowerPoint 自动生成的空备注部件。
4. **DOCX 内容常在表格里**：`python-docx` 的 `paragraphs` 看不到 `w:tbl`，本库按 `body` 顺序遍历 `p`+`tbl`，
   合并单元格以 HTML `<table colspan/vmerge>` 保留。
5. **矢量图形不等于位图**：`pdfimages` 抽不到矢量线条/组合图形，判断图表必须看整页渲染图。
6. **未覆盖范围**：未扫描整台电脑、未挂载磁盘与其他用户目录；桌面工程目录中的非题源产物仅按哈希核对。
   详见 `validation/原料对账报告.md` 第 5 节。
7. **图表文字可能两条通道都取不到**：2026 北京高考真题第 3 页第 6 题的「查『书』字时」对照表，
   在原生文字层**不存在**（全文检索 0 次命中），OCR 候选段**已含表中文字但被压成平铺行**
   （旧报告说"两个通道都没有"已过时）。凡涉及图表/表格的题，必须打开原页，
   不能只信文字层或只信 OCR。Q6 表格行列与 Q8 选项框问题见
   `validation/续修_20260921/` 下的修复记录。
8. **早期视觉工作单快照（2026-09-21；仅适用于该旧工作单，不是当前全库验收口径）**：分母为工作单按
   `(source_id, page)` **去重**后的唯一页；历史 `reviewed` 只证明"打开过"，
   **不证明页内问题已修完**。
   - 工作单 1,781 行 → **唯一 1,748 页**（重复 33 行）
   - 实际打开过 **42 页**（强证据 42 / 弱证据 0），**未打开 1,706 页**（约 2.40%）
   - 其中已有 verified 改正文本 1 页；登记了未修问题 38 页；
     题包依赖全部核完 0 页；评分关系待审 818 页
   - 唯一汇总源：`validation/续修_20260921/唯一汇总.json`；
     早期README / PROGRESS / checkpoint的该项数字来自此处；当前85套考试任务和9份汇编见转换主清单及各来源覆盖回执
   - 未核验页对应的题目**不得标为已核验**。续作按工作单 `batch_no` 分批，
     用 `scripts/24_record_visual_review.py records.json` 追加；
     **该脚本现在要求真实查看证据**（`viewed_file` 或内容相关 `findings`），
     无证据条目会被拒绝写入，不再默认写 `reviewed`。每批后重跑
     `scripts/30_unique_rollup.py` → `23_status_rollup.py` → `15_report.py` → `16_final_docs.py`
9. **汇编题出处仅部分核定**：9 份汇编 79 个块中 **44 块已定位实际出处**（23 块依汇编内自带出处标注、
   8 块文本比对、7 块标注定区届+比对定年份、6 块标注定区届+比对定题），
   **9 块为原料缺口**（汇编引用了 2024 门头沟/房山一模，但本库无此卷——详见 D-004），
   **26 块待复核**；未解决合计 35 块。数字现算自 `indexes/assembly_blocks.csv`，
   不引用历史报告的 31/44/74 等旧值。待复核/缺口块不得凭相似性归属到某卷某题。
10. **原件自身有缺陷的题**：见 `validation/源文件缺陷登记.md`
    - **D-001**：`高三政治一模试卷讲评.pptx` 的 slide35 部件在原件中丢失（两条独立工具链交叉验证一致）
    - **D-002 / D-003**：两份 PPTX 的 zip 结构不被 LibreOffice 接受，**重打包后转换成功**
    - **D-004**：2024 门头沟/房山一模 原件不在工作区与全部已授权原料根（汇编反查发现）
