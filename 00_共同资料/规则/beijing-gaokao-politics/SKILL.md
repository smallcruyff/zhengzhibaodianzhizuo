---
name: beijing-gaokao-politics
description: 制作、修订和审查北京高考政治宝典，核验原题与正式评分细则，维护本项目规则。状态查询与原稿补发只核实相应记录。
---

# 北京高考政治教研

`skill_revision: 6.3.31-20260923`
`supersedes: 6.3.30-20260923`
`last_updated: 2026-09-22`
`date_timezone: America/Los_Angeles`

宝典供教师授课和学生研习。围绕已确认的知识框架，将完整原题、正式评分依据与材料到知识的推理组织成可直接使用的教学文档。

## 承接当前任务

先确定本轮要交付的实际文件和修改范围，从本册真实工作头继续。执行、澄清、版本和完成规则统一见 [AGENTS.md](AGENTS.md)；首次使用或该文件变化时读取。

Codex与Claude共同制书时，先读[跨软件交接](references/cross-platform-handoff.md)，从共同项目根的`00_协作入口.md`进入。子代理模型按AGENTS中的平台对应表选择；Luna/max不可直接当作Claude模型。

每轮实质制书及涉及宪法、执行权限、读取或完成标准的规则维护，主代理必须亲自全文读取 [宪法执行副本](references/project-constitution.md)，包括两张示范图的完整转录与解释。用户明确保留了这一要求；普通技能优化不授权取消。读取触发与恢复条件以宪法为准，读完直接执行已授权工作。

按下表读取当前册入口。已绑定的册别不因相似附件名改变；历史快照、建议附件和网页供核查参考，不自行授予新任务或覆盖当前实物。除宪法外，专业资料只在本轮涉及相应问题时加载。

| 成品链 | 当前入口 | 结构边界 |
|---|---|---|
| 必修二《经济与社会》 | [经济快照](references/active/book-bixiu-2-current.md) | 54321、应如何、传导链；考法后紧跟完整例题；不恢复方法索引 |
| 必修三《政治与法治》 | [政法快照](references/active/book-bixiu-3-current.md) | 本书四栏目与受控续作链 |
| 必修四哲学 | [哲学快照](references/active/book-philosophy-current.md) | 与文化独立 |
| 必修四文化 | [文化快照](references/active/book-culture-current.md) | 七段文化框架与本书版本链 |
| 选必一 | [选必一快照](references/active/book-xuanbi-1-current.md) | 继承 work new 有效成果 |
| 选必二《法律与生活》 | [法律快照](references/active/book-xuanbi-2-current.md) | 四大块、21节点、多节点落位与附录 |
| 选必三思维 | [选必三快照](references/active/book-xuanbi-3-current.md) | 独立思维链与栏目 |
| 选必三推理 | [选必三快照](references/active/book-xuanbi-3-current.md) | 独立推理链、节点规则与空白前言 |

## 按问题取用依据

| 本轮问题 | 来源与用途 |
|---|---|
| 题库Markdown转换与逐卷验收 | [项目总规则·题库全库Markdown转换](references/project-rules.md#题库全库markdown转换2026-09-22)：完整转写范围、七条验收门槛、缺源与难辨、表格结构化、主控抽检；逐卷状态只以流水线主清单为准 |
| 开始另一册、跨任务接续、大批制作或复盘返工 | [制书工作流](references/book-production-workflow.md)：先核定本册结构与样式，按题源合批；用户确认收口后停止自发改稿 |
| 细则、分值、答案 | [评分证据协议](references/evidence-policy.md)：同卷同题同小问配对；[学生版标准](references/student-rubric-standard.md)：简短讲当前标题踩分词、逻辑及真实分值，完整评分条件留后台 |
| 新题、漏题、覆盖、计数或排序 | [计数与排序](references/counting-sorting-policy.md)、[题源清单](references/source-inventory.md)：从原卷逆查，独立题数与落位次数分开 |
| 陆续补旧题、新届试题、新细则或筛查题肢模块归属 | [增量补题](references/incremental-question-intake.md)：完整原题与题肢单练分别准入，逐条核定本册知识；复用同指纹证据，维护分类题量与目录页码 |
| 字体、段落、图表、分页或导航 | [版式协议](references/style-spec.md)、[原题保真](references/original-fidelity-checklist.md)：保留原题与本书结构，检查实际页面；同时使用宿主对应文档/PDF技能 |
| 版本冲突、晋升、回滚 | 当前册实际状态；必要时查 [成品清单](references/artifact-manifest.md) 的相关记录 |
| 历史决定或规则冲突 | [要求账本](references/user-requirements-ledger.md)、[纠错账本](references/correction-log.md)、对应册历史，只查相关日期及覆盖关系 |
| 跨册规则或项目定位 | [项目总规则](references/project-rules.md)、[项目入口](references/active/project-current.md)，不据跨册默认重建本书 |
| 真实跨会话恢复或长工具会话 | [恢复协议](references/task-continuity.md)，复用状态与已保存成果 |

## 专业边界

- 原始试卷、正式细则、唯一证据原件和认可框架受保护。完整保留作答所需材料、自然段、图表、定义、注释、题号和设问；教学解释不能替代原题。
- E1来自可核查的正式评分载体，教师版和参考答案不能证明逐点分值。官方分档、水平和整体评价在后台按原意保留，不进入学生版；不臆拆固定分或评分槽。
- 无E1例外仍限三套整卷：2024顺义二模、2026石景山期末、2026北京高考；以及仅必修二2024石景山一模第19题第（1）问。允许方向性E3，不虚构分值、关系或正式频次，不自行增设例外专区。
- 核心教学文字由主代理阅读证据、判断并定稿。先从正式细则提取当前一级标题可采的具体知识、材料关系和效果，再反推答案落点与思维链条。细则说明用两三句讲清这些实质内容；原件明确各采分点分值时，在相应内容后直接标“（2分）”等原值；未写则不标、不推算，删除全部等级分档、评分解释套话及泛泛扣分提示。必修二专属栏目与链条见学生版标准，不推广给其他书。
- 必修三按[双触发与考场式作答](references/style-spec.md#必修三双触发与考场式作答2026-09-21)写【思维链条】：材料关键词选知识，设问题型定作答层次，必要时据正式细则倒推结构；删末尾“链：”行。先核当前标题的正式评分依据，再使材料触发、作答层次、答案与细则逐项对应；不得用泛泛效果补造归属。答案须同时满足“与所在一级标题相关”和“同题细则明确允许的采分方向”，按筛选后的内容组织分析层次，精简且正文黑色；不得为凑整题结构补入其他标题内容。2026-09-21用户已认可修订3及括号标分规则并授权全书推广；按逐题证据执行，不再重复等待样稿许可。
- 用户指出反例后，查本轮授权范围内的同类问题，修正所有命中及必要依赖。检查全书某类缺陷不等于授权重建全书；已明确授权的全局样式调整按该范围执行。

本地首要题源为 `/Users/wanglifei/Desktop/2024模拟题`、`/Users/wanglifei/Desktop/2025模拟题`、`/Users/wanglifei/Desktop/2026模拟题`、`/Users/wanglifei/Desktop/历年高考题及细则`。可访问时优先按题键定位原件，复用已核验索引；附件列表未出现不等于不存在，目录可得也不等于题级证据已闭合。新成果存入 `/Users/wanglifei/Desktop/gpt6` 下本册工程目录，原题源保持只读。

本地新增旧题库 `/Users/wanglifei/Desktop/2023模拟题` 按用户要求纳入；只有答案而无正式细则的卷只处理选择题，详见增量补题。

## 交付

修订交付实际改后的文件；规则维护交付实际更新的完整技能及差分。保存后重开，完成相应内容、结构、页面和技术检查，更新既有当前状态。明确区分本轮修订完成、整书终审通过、已保存、已渲染、已审查和最终发布，不以生成文件或复制到审阅入口替代验收。
