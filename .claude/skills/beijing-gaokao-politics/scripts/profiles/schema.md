# 书册配置字段说明（profiles/*.json）

每本书一份 `profiles/<book_id>.json`，只写本册静态约定；每批会变的 SHA、工作头、计数仍在当前状态、审阅清单和同版身份文件里。
`_house.json` 是各册共享的默认值：`profile_lib.load_profile()` 先读 `_house.json`，再用本册配置按键深合并覆盖。
**字典逐键合并，列表整体替换**（本册写了同名列表就不再继承 house 的列表；要追加请用 `*_book` 一类的本册专用键）。
样式一律按 `w:name` 匹配，不按 styleId（必修三 Word 重存后 styleId 变成 1/21/aff5 等）。

本文件列出 `batch_health.py` 用到的字段；标“缺省”的字段不写时用 batch_health.py 里的 `DEFAULTS`。文末“batch_health 实际读取的字段”一节是完整清单，
没列在那里的键（如 `render.soffice`、`publish.archive_to`、`handoff.*`、`naming.*`、`typography.*` 除 `colors.label_blue`）batch_health 不读，由各自工具说明。
只有 batch_health 任务的负责人改 `profiles/`；其他工具需要新字段时在代码里给默认值，并把字段需求报给主代理。
`_house.json` 里的 `output_guard.protected_roots`、`same_version.title_found_min`、`pdf_fonts.*` 另被 block_index.py、render_book.py 读取，改名要同步。

## 分区（zone）与分级

体检先把段落流标成区位，再按区位查：

| zone | 含义 |
|---|---|
| cover | 第一个一级标题之前（封面、目录页标题） |
| heading | 一级/二级标题、考法标题（`styles.method`）、分组标题（`styles.group_heading`）、例题标题样式里认不出题号的小标题 |
| toc | 目录样式段落 |
| title | 例题标题行 |
| source | 题面区：例题标题 → 第一个教学栏目标签 |
| teaching | 教学区：`【思维链条】【答案落点】【答案】【分析过程】【为什么能想到】【链条】`等 |
| rubric | 细则区：细则标签（`labels_rules.rubric_labels`）→ 下一个标签 |
| outside | 例题块以外的节内正文（常见表述、题型分类、专题正文等） |
| drill | 单练部分（`structure.parts[].drill=true`） |

分级：`FAIL` 确定违规；`CANDIDATE` 需主代理判断的候选；`WARN` 提示；`INFO` 统计。门全过只说明机械层没有回退。
回退棘轮：FAIL 级计数增加只记 INFO（原门已判，不重复计）；CANDIDATE 级增加记 WARN“较上批新增 N 条待判”；只有 keepNext 缺失这类明文棘轮计数增加才判 FAIL。
棘轮键是（检查, 规则, 级别, 部分），同一例题块在本检查已有 FAIL 时，它的 CANDIDATE/WARN 不再计。

## 顶层

| 字段 | 说明 |
|---|---|
| `book_id` `title` | 书册标识与显示名 |
| `frozen` `frozen_note` `collab_key` | 冻结册（已送印）只读；写出路径落在本册目录、或项目根下以 `collab_key`（如“必修二”）命名的目录时经 `frozen_guard` 拒绝 |
| `paths.root/workspace/aux_workspace/review_entry/review_history` | `detect_profile` 按这些目录判断书册；`paths.root` 自动成为输出守卫的受保护根 |
| `sources.no_e1_exceptions.{whole_papers,questions}` | 具名“无正式细则”的整卷与题；配合栏目模式的 `exempt_if_source_in` 豁免细则栏 |
| `example_kind_by_labels` | 缺省 `{}`。题型按栏目标签改判：`{"choice": ["【答案与错项】", "【错肢分析】"], "_apply_to": ["subjective"]}`，块内出现所列标签即改判（哲学、选必一、选必三思维等主观题与选择题都叫“例题N”）。编号仍按标题写法连号 |

## styles

`h1` `h2` `example_title` `group_heading` `method` `category_line` `toc` `rubric` `front_heading` `drill_group`：
各语义角色对应的样式名列表。`category_line` 段（如“【常见表述】”“【人大主体与四项职权】”）结束上一道例题块。
`method_desc` `source` `teaching` `trigger_box` batch_health 不读（其他工具用）。

## structure

| 字段 | 说明 |
|---|---|
| `parts[]` | 按一级标题文字切部分：`id`、`match`（正则，search 一级标题）、`schema`（题型 → 栏目模式名）、`numbering_reset`（`h2`/`method`/`group_heading`，一级标题总会重置）、`kind_override`（本部分题型改判，如必修二第五部分“例题N”实为选择题）、`drill`（单练部分）、`method_without_count_allowed`（考法标题可不写“（N题）”，如必修三专题的主体标题）、`choice_after_subjective_in_node`（选择例题须排在本节点主观例题之后） |
| `block_end[]` | 缺省 `[]`。`{styles, regex}`：这些样式里匹配正则的段落结束上一道例题块（必修三专题的“▪ 小标题”“② 执行”） |
| `teaching_leadin_regex` | 缺省无。例题块内匹配的段落切到教学区（必修三专题“学什么：”），免得被算进细则区 |
| `style_zone_switch` | 缺省 `{}`。题面区里出现这些样式的无标签段，按样式切到 `teaching`/`rubric`（专题任务型例题常不写栏目标签） |
| `unmatched_title_style_ends_block` | 缺省 true。`styles.example_title` 样式里认不出题号的段（必修三专题“一、题型与给分方式”“任务五 时评短文与发言稿”）结束上一道例题块，记为 heading |
| `source_style_reenter` | 缺省 `[]`。例题块教学/细则区里出现这些样式的无标签段时回到题面区（必修三“题目设问”：专题任务型【主例】里嵌的后一道小题设问） |
| `copy_check` | 缺省无。同批副本比较：`{copy_parts, ref_parts, copy_kinds, basis}`，把 `copy_parts` 里的例题与 `ref_parts` 里同题键的题面比较（必修三：专题例题须沿用第一部分原排版，style-spec 2026-09-23）。每块最多两条 CANDIDATE（文字不同、图片少）；本批新出现且已按上批另一部分作参照报过差异的块不重复列 |

## example_titles[]

`kind`、`regex`（命名组 `num`、`src`）、`styles`（只在这些样式里认，缺省 `styles.example_title`）、`numbered`（缺省 true）。
题源 `src` 归一成题键：去空白、全角转半角、去“年”、去末尾“（N分/跨模块/…栏）”，`17(1)题`→`17题第(1)问`。
必修三任务型 `topic_case` 认【主例】【变式】【变式一】【变式二】…。

## column_schemas.<name>

| 字段 | 说明 |
|---|---|
| `labels` | 必备标签，按应出现的顺序 |
| `mode` | `each_once`（各恰好一次）或 `at_least_once` |
| `optional` | 可有可无，最多一次 |
| `repeatable` | 可重复（至少一次） |
| `extra_labels` | 本栏目认可的附加标签 |
| `require_one_of` | 标签组列表，每组恰好出现一种一次 |
| `forbidden_labels` | `{标签: {instead, reason}}`：作为段首标签出现即 FAIL“使用了本栏目模式禁止的标签”（附 reason）；它顶替的 `instead` 标签缺失不再重复报。必修三 topic5：【材料】【设问】禁用，须原题排版【题目】（style-spec 第105行，用户2026-09-23） |
| `exempt_if_source_in` | 指向 `sources.no_e1_exceptions`：具名无细则的题缺细则栏不报 |

另有 `column_exemptions[]`（`src_regex`、`labels`、`reason`）写其他具名豁免。标签只认段首的【…】，标签内括注（如“【细则（北京一栏）】”）归一后再比。

## 标签相关

| 字段 | 说明 |
|---|---|
| `section_labels` | 节级栏目（【常见表述】【题型分类】等）；在例题块内出现即结束该块 |
| `hidden_labels` | 已删除、不得再出现的可见标签（必修二【材料原文】【设问】），出现即 FAIL |
| `labels_rules.source_labels` | 题面标签（【题目】【材料】【设问】） |
| `labels_rules.rubric_labels` | 细则标签（【细则说明】【细则】） |
| `labels_rules.answer_labels` | 缺省 `["【答案落点】"]` |
| `labels_rules.answer_score_regex` `answer_score_level` | 答案落点标分的识别与级别；house 缺省 WARN，必修三 FAIL（第49批修订5起答案不标分） |
| `labels_rules.forbid_line_regex` `forbid_line_level` | 已撤销的独立行（必修三“链：”行残留）；只查残留，不查“必须有链行” |
| `labels_rules.block_label_allow_regex` | 例题块内认可的小标签（必修二【角度N·…】），不当异常标签 |

## numbering / method_count

`numbering.per_kind`（各题型分别连号，缺省 true；按标题写法 title_kind 连号，标签改判不影响）、`numbering.unnumbered_kinds`。
`method_count.regex`（缺省 `（(\d+)题）\s*$`）、`bearer_styles`、`count_kinds`（缺省 subjective）、`unit`（`blocks` 或 `unique_questions`）。

## student_text

| 字段 | 说明 |
|---|---|
| `engineering_tags` | （house）纯工程标签：［图、待主代理插入、TODO、需核、待核、uncertain、？？、【编者校注】、校注：。**全区扫描**：题面、例题标题、各级标题、单练题肢与题源格、封面都查，FAIL |
| `forbidden_words_common` | （house）通用工程词，FAIL；只扫 `forbidden_word_zones`（“来源：”“出处”等原卷也可能出现，不扫题面） |
| `forbidden_words_book` | 本册增补工程词，FAIL |
| `forbidden_word_groups` | 分组词表，house 放通用（来源腔、浮夸幼稚），本册放专属（必修三：编校口吻、等级套话）；字典合并。同一个词只归一组：工程标签 → 分组 → 工程词 |
| `forbidden_word_group_levels` | 某组在某部分改级：`{"等级套话": {"default": "FAIL", "parts": {"TOPIC": "CANDIDATE"}}}` |
| `forbidden_word_zones` | 缺省 teaching/rubric/outside/heading；单练里“纠正：”之后的文字、导语和分组行也按全部词表扫 |
| `warn_words` | 含义有歧义、须用户裁定的词，只 WARN（评分标准、（跨模块）、本册…） |
| `allow_contexts` | `{词: [允许的上下文]}`，如“需核”在“无需核验”里不报（工程标签也适用） |
| `line_start_forbidden` | 行首禁用正则（“说明：”） |
| `trailing_tag_regex` `trailing_tag_zones` `trailing_tag_exempt_styles` | 条目末尾试卷/题号/分值括注；只查 teaching/outside，题面区、细则区不查。【答案落点】段也查试卷/题号括注，只含分值的括注交给“答案落点不标分” |
| `trailing_tag_levels` | `{"default": "FAIL", "parts": {"TOPIC": "CANDIDATE"}}` |
| `warn_patterns` | 句式提示（“不是……而是”），WARN，不进棘轮 |
| `collateral_patterns` | 全局替换误伤模式（实施评分标准等），全区扫，CANDIDATE |
| `source_suspect_words` | 题面区出现即列 CANDIDATE 的词（评分标准、细则说明、答案落点） |
| `four_rights` | `{rights, alone_ok, exempt_if_regex, level}`：知情权/参与权/表达权/监督权不一串写只 WARN；只出现“监督权”、或含“人大…监督权”的区分段落不报 |

文字抽取：w:t、w:tab、w:sym（按字符码）；跳过 mc:Fallback 的重复文字；去掉 U+2060 词连接符、零宽字符、软连字符后再比较与匹配（报告 `inputs.docx.zero_width_chars_removed`）。

## drill（单练）

| 字段 | 说明 |
|---|---|
| `layout` | `table3`（三列表：题肢｜判断｜题源，必修二、必修三）或 `paragraph`（段落式：条目段＋其后“纠正：”段，哲学、选必一等） |
| `columns` `stem_col` `answer_col` `source_col` | table3 用 |
| `item_regex` | 条目段/格的正则（组1序号、组2正文） |
| `a1_heading` `a2_heading` | 按二级标题分 A1/A2；table3 缺省按判断栏是否为空括号 |
| `item_styles` `correction_styles` | paragraph 用（可选）：条目段样式、纠正段样式。纠正样式却不以 `correction_marker` 开头的段（如“提示：表述本身成立……”）记为附注，A2 列 CANDIDATE（可能是“不选”类题肢），A1 判 FAIL |
| `group_style` `group_label_regex` | 分组行（paragraph 用来分组统计交替） |
| `paragraph_verdict_regex` | paragraph 可选：条目末尾显式判断“（正确/错误/不选）”；没有时按有无“纠正：”或红色错处推断（报告 `a2_answers_derived`） |
| `a1_blank` `a2_allowed` | A1 空括号；A2 只允许“正确/错误”，“不选”只在这里拦 |
| `correction_marker` `colors.error_run` `colors.correction` | 纠正前缀、错处红、纠正绿 |
| `a1_forbid` `intro_forbidden` | A1 答案提示词（FAIL）、导语禁用词（CANDIDATE） |
| `alternation.required` `max_same_run_per_table` `level` | 交替提示；用户规则只说“总体交替、不成固定规律”，没有给阈值，`level` 缺省 WARN |
| `each_table_has_both` | 每表正误都有（必修二 REQ-BX2-20260915-006），FAIL |
| `max_non_item_ratio` | 缺省 0.3。配置了单练、文中有单练段落却认不出条目，或非条目行占比超过此值，判 FAIL“单练结构未识别”，不静默通过 |

选择题解析里的“（不选）”不检查（材料未体现时允许）。

## toc / footer

`toc.styles`、`toc.entries_expected`（不符 WARN）、`toc.toc_pdf_pages`（缺省扫前 `scan_first_pages`=8 页）、
`toc.check_pageref_equals_hyperlink_anchor`（缺省 true）、`toc.label_differs_from_heading`（目录文字与标题本来就不同的册设 true）。
链路：目录段超链接锚点 → 文档书签 → PDF 链接实际落页（与缓存页码比）→ 落页上能否找到该书签所在标题。
`footer.regex`、`exempt_pages`、`page_offset`、`continuous`、`bottom_band`（页底多高范围内找页脚，缺省 0.12）。

## 颜色、选择题、PDF 字体与同版、分页、基线、输出守卫

| 字段 | 说明 |
|---|---|
| `colors.blue` | （house）标签/标题蓝色系；`typography.colors.label_blue` 自动并入 |
| `colors.blue_exempt_prefix` `blue_exempt_styles` | 豁免的小标题前缀（▪ ◆）与样式（必修二“框架层级”） |
| `choice_check.kinds` `answer_regex` `reverse_regex` `reverse_hint_regex` `verdict_regex` `option_combo_regex` | 选择题【答案】与逐肢判定一致性；`answer_regex` 缺省 `^\s*【答案】\s*([A-D]+)`（哲学写“【答案与错项】答案：D”）；反向设问按“错误”肢反推。设问正则看不出反向而解析自述“逆向选择”时列 CANDIDATE“设问方向与解析自述不一致”，不判一致也不判矛盾 |
| `pdf_fonts.expected_cjk_regex` `fail_min_chars_page` | 汉字应落的字体（必修三 STSongti/STKaiti；必修二另含 SimSun）；某页回退汉字 ≥ 阈值 FAIL，否则 WARN |
| `render.identity_file` `publish.manifest` | 同版身份记录文件名（缺省“同版身份.json”“.review-manifest.json”），在 PDF/DOCX 所在目录及上两级查找，或用 `--identity` 指定（指定时只认这一份）。记录里本 DOCX 对应别的 PDF、或本 PDF 属于别的 DOCX → FAIL；找不到 → WARN |
| `same_version.title_found_min` | （house）缺省 0.98。DOCX 的一二级标题、考法与例题标题在 PDF 文字里按序找到的比例低于此值 → FAIL“疑似非同版”，页脚、字体、目录门加注“结论不能记在本批名下” |
| `pagination.keep_next_label_regex` `keep_next_target_style` `keep_next_title_required` | 材料小标题、例题/考法标题的 keepNext；缺失 WARN，比上批增加即棘轮 FAIL |
| `baseline.near_edit_ratio` | 同题键题面“改字”、合并、拆分的相似度下限（缺省 0.85） |
| `pixel.policy` | 像素判定基础口径 `same_page_full_pixels`；batch_health 不做页复用判定。用户2026-09-23裁定放宽：`allow_content_addressed_map=true`（错位但正文区像素一致、仅页码/页脚不同的页视同未变）；`subpixel_tolerance_pt=0.2`（只有字形位移且小于该值、文字图片图形都没变，视同未变）；`inherit_unchanged_without_ledger=true`（阶段稿里与上一版一样的页即使没有实看记录也不重看；定稿/送印终审用 page_delta `--final`，仍须旧页实看记录） |
| `output_guard.protected_roots` | （house）受保护根：~/GaokaoPolitics、~/.codex/skills、~/.claude/skills、~/Desktop；各书册 `paths.root` 与本 Skill 目录自动并入 |
| `output_guard.allowed_subpath_regex` | （house）受保护根内唯一允许写出的位置，缺省 `/协作/候选/[^/]+/[^/]+/构建/体检(/|$)`；系统临时目录放行 |

输出守卫另有固定规则：必须是 .json；不得等于任何输入（大小写折叠后比较）；目标已存在时只允许覆盖旧的 batch_health 报告；目标目录里有 .docx/.pdf 时拒绝。

## 题面零改写（门 9）怎么比

带 `--baseline` 时逐块比较：本批每个例题块与上批**同题键里题面最相近的一块**比（同一题在第一部分和专题各有一份时不合并段落，互不掩盖）。
差异分：改字（FAIL，逐段附原文差异片段）、几段并一段（FAIL）、一段拆几段（纯分段 CANDIDATE，拆分同时改字 FAIL）、上批段缺失（FAIL，按块汇总并附原文截取）、
新段（CANDIDATE，按块汇总）、仅段首标签不同（CANDIDATE）、仅空白不同（INFO，计数）、图片变少或换了（CANDIDATE，按媒体字节哈希）。
同一题键、同一差异在几个块里重复出现时只列一条，其余位置记在 `also_in`（`occurrences` 计数）。
`--source-restore-list` 登记的题键，文字差异降为 INFO（图片差异仍 CANDIDATE）。

## batch_health 实际读取的字段

`book_id` `title` `frozen` `frozen_note` `collab_key` `paths.{root,workspace,aux_workspace,review_entry,review_history}`；
`styles.{h1,h2,example_title,group_heading,method,category_line,toc,rubric,front_heading,drill_group}`；
`structure.{parts,block_end,teaching_leadin_regex,style_zone_switch,unmatched_title_style_ends_block,source_style_reenter,copy_check}`；`example_titles`；`example_kind_by_labels`；
`column_schemas`；`column_exemptions`；`section_labels`；`hidden_labels`；`labels_rules.*`；`sources.no_e1_exceptions`；`numbering.*`；`method_count.*`；
`student_text.*`；`drill.*`；`toc.*`；`footer.*`；`colors.*`；`typography.colors.label_blue`；`choice_check.*`；`pdf_fonts.*`；`same_version.*`；
`render.identity_file`；`publish.manifest`；`pagination.{keep_next_label_regex,keep_next_target_style,keep_next_title_required}`；`baseline.near_edit_ratio`；
`pixel.{policy}`（只回显）；`output_guard.*`。

## 写书侧工具读取的字段（2026-09-24）

apply_patch、layout_prepare、publish_review、drill_tool 的判定全部经 `batch_health.Prof/walk/cfg` 解释上面各节字段，另读下列字段；新字段都有代码缺省值。

| 工具 | 字段 | 说明 |
|---|---|---|
| apply_patch | `student_text.*` 词表、`frozen` | 新文字过学生正文词表；冻结册写模式拒绝（按输入稿路径重新 detect，不看 --profile） |
| layout_prepare | `numbering.*`、`structure.parts[].numbering_reset`、`example_titles`、`method_count.*` | 例题编号与考法题数，口径同体检 |
| layout_prepare | `pagination.keep_next_labels` | 整段即标签、须与后文同页的行；缺省 `[]`；必修三登记【思维链条】【答案落点】 |
| layout_prepare | `pagination.max_keep_next_chain` | （house）缺省 20；补 keepNext 后所在链超过此长且比改前长就不补、列 blocked |
| layout_prepare | `toc.mode` `toc.styles` `toc.toc_pdf_pages` `toc.scan_first_pages` | `pageref_in_hyperlink`（必修三）或 `hyperlink_static`（必修二） |
| layout_prepare | `toc.pdf_align_min` | （house）缺省 0.98；目录 PDF 无同版身份记录、显式 `--allow-unbound-pdf` 时的双向正文对位率下限；有记录时以 SHA 绑定为准 |
| publish_review | `paths.root/workspace/review_entry/review_history/review_manifest/central_state/handoff/build_subdir` | 写入目标全部由这些路径渲染并逐级核不越界、不经符号链接 |
| publish_review | `publish.note_file` `manifest` `archive_to` `preserve` `central_state_backup` `central_state_fields` `central_state_status_template` | 模板占位符 `{review_history}` `{prev}` `{stamp}` `{candidate}`；`central_state_fields` 为中央状态字段名映射，缺省按必修三现状 |
| publish_review | `naming.docx_stem`、`handoff.owner_file`、`render.identity_file` | 工作区根文件名；接管 owner 与 phase=owned；同版身份交叉核对 |
| drill_tool | `drill.*` | 同上“drill（单练）”一节；build 目前只支持 `layout=table3`，`paragraph`/`card` 抽取或生成不了时列出缺的字段并非零退出 |

## 变更记录

- 2026-09-24（写书侧工具）：`bixiu3.pagination.keep_next_labels` 登记；`_house` 增 `pagination.max_keep_next_chain`、`toc.pdf_align_min`；新增上节“写书侧工具读取的字段”。

- 2026-09-23（batch_health 2.1，验证意见返修）：`_house.json` 新增 `student_text.engineering_tags`（全区扫描，原“工程标签”词组并入）、`forbidden_word_zones` 加 heading、`same_version`、`output_guard`；
  必修三 `column_schemas.topic5` 改为 `labels=[题目,思维链条,答案落点,细则]`＋`forbidden_labels={材料,设问}`（不再用 require_one_of 放行【材料】【设问】）；
  `example_titles` 的 topic_case 认【变式一】【变式二】；新增 `structure.unmatched_title_style_ends_block`、`structure.source_style_reenter`、`structure.copy_check`；
  必修二 `drill.alternation.level=WARN`（阈值 3 非用户原话）。代码侧新增读取 `example_kind_by_labels`、`drill.layout=paragraph` 及其子字段、`choice_check.answer_regex`、`render.identity_file`、`publish.manifest`。
- 2026-09-23（batch_health 2.0）：新建 `_house.json`，把两册相同的 `forbidden_words_common`、trailing/zone/warn 设置移入；新增 `forbidden_word_groups`、`warn_words`、`collateral_patterns`、`source_suspect_words`、`choice_check`、`pdf_fonts`、`colors`、`labels_rules.answer_*`、`structure.block_end/teaching_leadin_regex/style_zone_switch`、`drill.a2_heading`、`four_rights`（替代必修三原 `candidate_patterns.四权拆写`）；`section_labels` 增【题型分类】【主线】【过程总述】【结果总述】；`labels_rules.forbid_line_regex` 改为 `^链[：:]`；必修二增 `labels_rules.block_label_allow_regex` 与 `colors.blue_exempt_styles`。
