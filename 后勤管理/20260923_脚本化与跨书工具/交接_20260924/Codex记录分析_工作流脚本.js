export const meta = {
  name: 'codex-process-mining',
  description: '读取 Codex 全部会话记录与本地工程历史，还原各册“做书全流程”的环节、花费与返工，找出可脚本化的缺口',
  phases: [
    { title: 'Catalog', detail: '脚本扫描 64GB Codex 会话，生成会话目录（任务、书线、阶段、token）', model: 'sonnet' },
    { title: 'Mine', detail: '按书线并行还原做书流程、花费与返工', model: 'sonnet' },
    { title: 'Synthesize', detail: '汇总全流程图、工具缺口与优化方案' },
    { title: 'Critic', detail: '核对关键数字与方案风险' },
  ],
}

const ROOT = '/Users/wanglifei/Desktop/gpt和claude共同的小窝'
const SK = '/Users/wanglifei/.codex/skills/beijing-gaokao-politics'
const SC = '/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/codex_mining'
const PRIOR = '/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad'

const COMMON = `
项目：北京高考政治宝典（${ROOT}）。用户在 Codex（GPT-5.4/5.5/5.6/GPT-6 各时期）里做了大部分书：必修二（已送印）、必修三前期、必修四哲学与文化、选必一、选必二、选必三思维与推理，以及题库线；Claude 只参与了必修三后几批与题库线一段。现在要为后续五六本书的大改省 token：机械活交脚本，模型只做题目分析等高智力工作。本轮目标是用 Codex 的真实记录与本地工程历史，还原“做一本书”的全流程，找出花费与返工集中在哪、哪些还能脚本化。
Codex 会话记录：~/.codex/sessions（15G）与 ~/.codex/archived_sessions（49G），共约 2096 个 rollout-*.jsonl。格式：每行 JSON，type 有 session_meta（payload.cwd、originator、model 等）、turn_context（cwd、model）、event_msg（payload.type=token_count 时 payload.info.last_token_usage / total_token_usage 含 input_tokens、cached_input_tokens、output_tokens、reasoning_output_tokens；task_started/task_complete 的 last_agent_message 是该轮收尾汇报；item_completed 里 item.type=UserMessage 是用户消息）、response_item（function_call：exec_command 的 arguments.cmd；custom_tool_call：apply_patch 的 input 含写了哪些文件；message；reasoning 为加密，不可读）。子代理（协作模式）可能是独立会话文件，按 session_meta 或 turn_context 中的父子线索关联。
本地工程历史：${ROOT} 下各册工程目录（必修二_*、必修三_*、99_工程与历史归档、后勤管理 等）；${ROOT}/必修二_全程复盘与跨册工作流_20260913/（证据/六条主线用户消息原文.json、01_用户要求总表.json 等，是现成的复盘材料，先读）；~/GaokaoPolitics/Codex的北京高考政治/（Codex 工作区，如 必修三续作_20260908、必修四哲学续作_20260908）；~/Desktop/2026模拟题/（文化、选必二等续作目录）；Skill 母版 ${SK}/references/（artifact-manifest.md 版本链、correction-log.md 纠错、user-requirements-ledger.md 用户要求、book-*.md 各册规则、book-production-workflow.md 流程）。六本半成品的现稿路径见 ${PRIOR}/crossbook/census_*.json。
我们已有的通用工具（${SK}/scripts/）：batch_health、page_delta、render_book、qpack、block_index、profile_probe、doc2md、bank_retro_audit、usage_profile（已能部分解析 Codex rollout）、bank_compile（在建）、profiles/ 书册配置；前期结论在 ${PRIOR}/measure_result.json、${PRIOR}/crossbook/stage_table.json、${ROOT}/后勤管理/20260923_脚本化与跨书工具/。
硬约束：只读；不得读取或输出任何凭据（~/.codex/auth.json、*api-key*、config.toml 里的密钥等一律不碰）；不改任何书稿、题库、协作文件、Skill；产物只写 ${SC}/<子目录>/；大文件流式读，用脚本统计，不要把原始记录大段读进上下文；结论附证据（会话 id、路径、计数）；Codex 的 token 数按 last_token_usage 逐次累加，分清 cached 与未缓存，只报 token 不编美元；不确定就写不确定；中文输出。`

const FINDINGS = {
  type: 'object',
  properties: {
    summary: { type: 'string' },
    numbers: { type: 'array', items: { type: 'object', properties: { metric: { type: 'string' }, value: { type: 'string' }, evidence: { type: 'string' } }, required: ['metric', 'value', 'evidence'] } },
    stages: { type: 'array', description: '该书线做书流程的各环节', items: { type: 'object', properties: {
      stage: { type: 'string' }, what: { type: 'string' }, tokens: { type: 'string', description: '该环节 token（未缓存/缓存/输出）与占比' },
      rework: { type: 'string', description: '返工次数与原因' }, mechanical_share: { type: 'string', description: '其中机械活的比例与例子' },
      covered_by_tool: { type: 'string', description: '现有通用工具能否覆盖，哪个工具' }, gap: { type: 'string' } },
      required: ['stage', 'what', 'tokens', 'rework', 'mechanical_share', 'covered_by_tool', 'gap'] } },
    lessons: { type: 'array', items: { type: 'string' } },
    files_written: { type: 'array', items: { type: 'string' } },
  },
  required: ['summary', 'numbers', 'stages', 'lessons', 'files_written'],
}

phase('Catalog')
const catalog = await agent(`${COMMON}
任务 catalog：写一个流式扫描脚本 ${SC}/catalog/codex_catalog.py，用多进程扫完全部 Codex rollout 文件，生成会话目录 ${SC}/catalog/sessions.jsonl 与 sessions.csv，每个会话一行：会话 id、文件路径与大小、起止时间、cwd、模型、originator、父会话（若可判定）、轮数、API 调用次数、token（input、cached_input、未缓存＝input−cached、output、reasoning）、第一条与最后若干条用户消息（各截 300 字，标注截断）、每轮收尾汇报 last_agent_message 的前 200 字（最多 20 条）、exec 命令按特征归类计数（渲染/soffice、python 构建脚本、grep/sed 浏览、git、pdftoppm/图像、OCR、其他）、apply_patch 写过的文件路径（去重，最多 200 个）、书线判定（必修二/必修三/哲学/文化/选必一/选必二/选必三思维/选必三推理/题库线/项目配置/无关，依据 cwd、写入路径、用户消息关键词，给出依据与置信度）。再按“书线×月份”“书线×阶段关键词（普查/筛卷、抽细则、写稿/改写、构建/合稿、渲染/排版、页面检查、题肢单练、发布/晋升、交接）”汇总 token。先小样本验证解析正确，再全量跑（后台多进程，记录总耗时）。与本项目无关的会话（cwd 不在本项目、消息与宝典无关）单列“无关”，不要丢。报告：会话总数、各书线会话数与 token、最贵的 20 个会话（id、书线、日期、首条消息摘要、token）、扫描耗时，以及解析失败的文件数与原因。`,
  { label: 'catalog:codex', phase: 'Catalog', model: 'sonnet', schema: FINDINGS })

const LINES = [
  { key: 'bixiu2', name: '必修二《经济与社会》（Codex 主做，已送印；另有 必修二_全程复盘与跨册工作流_20260913 复盘材料）' },
  { key: 'bixiu3_codex', name: '必修三《政治与法治》Codex 部分（R1—R31、第43—49批前期；Claude 接手前）' },
  { key: 'bixiu4', name: '必修四：哲学宝典与文化宝典' },
  { key: 'xuanbi1', name: '选必一《当代国际政治与经济》' },
  { key: 'xuanbi2', name: '选必二《法律与生活》' },
  { key: 'xuanbi3', name: '选必三《逻辑与思维》：思维宝典与推理宝典' },
  { key: 'bank', name: '题库线（DeepSeek、hy4、Codex 多组、Luna 续修）' },
]

phase('Mine')
const mined = (await parallel(LINES.map(l => () => agent(`${COMMON}
会话目录已由上一步生成：${SC}/catalog/sessions.jsonl（及 csv、汇总），脚本 ${SC}/catalog/codex_catalog.py 可复用或扩展做深入查询。catalog 报告摘要：${JSON.stringify(catalog || {}).slice(0, 6000)}
任务 mine:${l.key}：只负责书线「${l.name}」。
1 从目录里取本书线全部会话，按时间排出时间线（版本号、阶段、用户关键裁定），对照本地工程历史（该册工程目录、版本链 artifact-manifest、book-*.md、correction-log、ledger、复盘材料）核实每个阶段做了什么、产出了哪个版本。
2 把本书线的做书过程拆成环节（例如：题源盘点与普查筛卷、抽原题与细则、定节点框架与考法分类、写四栏目/教研内容、构建 DOCX 与合稿、编号目录分页、插图裁切、渲染 PDF、逐页检查、题肢单练 A1/A2、Excel/台账同步、审阅发布、交接与状态维护、返修），每个环节给 token（未缓存/缓存/输出）与占比、返工次数与原因（尤其用户否决后重做、QA 作废、版本回滚、BLOCKED）、机械活比例与例子（用会话里的 exec 命令与写过的脚本判断）、现有通用工具能否覆盖、还缺什么工具。
3 特别找“从零构建一本宝典”那一段（第一版如何从题源到成书），以及各版本之间为何质量不稳（例如 GPT 时期做得一般的原因），总结成对后续大改有用的教训。
4 用脚本查询目录与会话，不要把原始记录整段读进上下文；每个会话最多读其用户消息与收尾汇报。`,
  { label: `mine:${l.key}`, phase: 'Mine', model: 'sonnet', schema: FINDINGS }).then(r => r ? { key: l.key, ...r } : null)))).filter(Boolean)

phase('Synthesize')
const synth = await agent(`${COMMON}
下面是 Codex 会话目录与七条书线的流程还原结果。请汇总为一份对后续五六本书大改可直接执行的方案：
1 “做一本宝典”的标准全流程图：环节、每环节的历史 token 占比（跨书合计与各书对比）、返工率、机械活比例；
2 最大的 5—8 个浪费点及根因（附证据）；
3 工具覆盖矩阵：每个环节现有工具能替代多少、还缺哪些工具，给出新工具清单（名称、输入输出、替代的历史工作量、优先级、风险边界：哪些必须模型或用户判断）；特别说明“从零构建/大改一本书”阶段需要的工具与流程；
4 流程与规则建议（写进 Skill 的哪一节），包括模型分工（Codex 与 Claude 各自做什么、何时用 Luna/Sol/Opus/Sonnet）、何时用户裁定、如何避免 GPT 时期质量不稳的问题；
5 对五六本书改版的推荐执行顺序与预计 token 量级（相对历史的节省比例，给出计算依据）。
把完整报告写到 ${SC}/synthesis/做书全流程复盘与优化方案.md，并返回结构化结果。
目录报告：${JSON.stringify(catalog || {}).slice(0, 20000)}
书线结果：${JSON.stringify(mined).slice(0, 160000)}`,
  { label: 'synthesize:方案', phase: 'Synthesize', schema: {
    type: 'object', properties: {
      report_path: { type: 'string' }, summary: { type: 'string' },
      top_waste: { type: 'array', items: { type: 'string' } },
      new_tools: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, what: { type: 'string' }, replaces: { type: 'string' }, priority: { type: 'string' }, boundary: { type: 'string' } }, required: ['name', 'what', 'replaces', 'priority', 'boundary'] } },
      rules: { type: 'array', items: { type: 'string' } },
      plan: { type: 'string' },
    }, required: ['report_path', 'summary', 'top_waste', 'new_tools', 'rules', 'plan'] } })

phase('Critic')
const critic = await agent(`${COMMON}
你审查下面的汇总方案与书线结果：1 抽查 5—8 个关键数字（各书线 token、最贵会话、返工次数、机械活比例），用 ${SC}/catalog/ 的目录或重新流式统计核对；2 指出书线归属错误（例如同一会话跨多书、配置测试会话被算进书线）、口径混用（缓存与未缓存、会话级与调用级）；3 指出方案里会违反项目规则的建议（机器结论冒充已核验、用脚本替代教学判断或用户裁定、放宽已裁定门槛以外的门槛）；4 指出遗漏的重要环节或证据源。
汇总：${JSON.stringify(synth || {}).slice(0, 40000)}
书线结果：${JSON.stringify(mined).slice(0, 100000)}`,
  { label: 'critic:方案', phase: 'Critic', schema: {
    type: 'object', properties: {
      spot_checks: { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, verdict: { type: 'string' }, evidence: { type: 'string' } }, required: ['claim', 'verdict', 'evidence'] } },
      problems: { type: 'array', items: { type: 'string' } },
      missing: { type: 'array', items: { type: 'string' } },
    }, required: ['spot_checks', 'problems', 'missing'] } })

return { catalog, mined, synth, critic }
