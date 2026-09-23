# Skill 6.0.2-20260908 验证记录

## 本次静态验证

已运行 `python3 scripts/validate_bundle.py --root /Users/wanglifei/.codex/skills/beijing-gaokao-politics`，结果为 **PASS**：37 个功能文件、77 个 Markdown 本地链接、版本 `6.0.2-20260908`，错误 0。验证范围为 Skill 文件完整性、清单指纹、链接、入口元数据和宪法读取门关键文本；不证明宿主行为、宝典内容准确性或逐题覆盖。

本轮规则更新同步了本地 Work 四个题源根目录和更新后的宪法原件指纹；没有重新审查宝典正文、题级覆盖或正式评分证据。

# Skill 6.0.1-20260905 验证记录

**文件级检查：27/27通过。** 当前记录不代表用户宿主已安装，不代表模型行为对照、教材质量或token节省已经验证。

从6.0.0直接修订：**22个功能文件变化，15个功能文件逐字节不变，合计37个功能文件。** 最终ZIP共50个文件成员，包含维护资料及一个历史维护ZIP。

## 已实际执行

| 检查 | 结果 | 范围 |
| --- | --- | --- |
| 功能文件完整保留 | PASS | {"original": 37, "revised": 37, "missing": []} |
| 确有正文级文件变更 | PASS | {"changed": 22, "unchanged": 15} |
| 八份分册历史逐字节不变 | PASS | references/book-bixiu-2.md；references/book-bixiu-3.md；references/book-culture.md；references/book-philosophy.md；references/book-reasoning.md；references/book-xuanbi-1.md；references/book-xuanbi-2.md；references/book-xuanbi-3.md |
| 成品清单保真协议图标与旧工具保全 | PASS | references/artifact-manifest.md；references/original-fidelity-checklist.md；assets/icon.svg；legacy/5.6/scripts/task_checkpoint.py；legacy/5.6/task-continuity.before.txt；legacy/5.6/tests/test_task_checkpoint.py；legacy/README.md |
| 宪法专业正文与完整示范逐字节不变 | PASS | 从宝典的定位和用途至文件末尾，包含四原则与两张示范图转录 |
| 宪法原件身份字段保全 | PASS | constitution_revision；effective_date；source_file；source_library_identity；source_size_bytes；source_sha256 |
| 角色样式与分册专属样式原文保全 | PASS | ('### 项目统一语义角色字体系', '## 全项目共同规则')；('## 七本宝典专属样式', '## 选择题 A1/A2 协议') |
| 计数排序专业正文逐字节不变 | PASS | 含四套口径、唯一标识、正文落位、排序、Excel与量化审查要求 |
| 题源历史登记段落原文保全 | PASS | 原登记资料至配对与披露规则之前，全部历史事实段落 |
| 七份活动快照仅改控制引用 | PASS | 角色、Artifact/Library身份、全部原计数、未决、next_action、resume_token原文保留 |
| 活动快照既有SHA完整保全 | PASS | 逐文件按顺序比较全部64位哈希 |
| 历史追加保全 user-requirements-ledger.md | PASS | REQ-PROJ-20260905-ASTRA-002 唯一；只修改原元数据并追加新事件 |
| 历史追加保全 correction-log.md | PASS | CORR-PROJ-20260905-ASTRA-002 唯一；只修改原元数据并追加新事件 |
| 活动规则版本引用同步 | PASS | 七份册快照及项目入口；原宪法修订2不变 |
| 6.0.0维护历史原字节归档 | PASS | {"members": 11} |
| 历史归档无字体二进制 | PASS | 仅保留上一版维护资料，不作为活动Skill发现入口 |
| Skill和UI元数据可解析 | PASS | PyYAML读取；技能名称保持不变 |
| 所有Python文件语法检查 | PASS | 仅静态解析，未执行旧监视脚本 |
| 关键读取入口同步 | PASS | 包含同一新轮重读、正文/示范、事务性豁免与同轮连续边界 |
| 主动执行边界静态检查 | PASS | 条款存在检查，不代替实际行为测试 |
| 27个行为用例未伪称通过 | PASS | 全部为用户真实宿主待执行用例 |
| 逐行差分实际回放 | PASS | {"modified_files": 22, "matched_functional_files": 37, "exit_code": 0} |
| 只读验证器正向检查 | PASS | 37个功能文件，77个Markdown本地引用；错误0 |
| 验证器能发现意外字节变化 | PASS | 在隔离副本追加测试行，验证器返回FAIL |
| 验证器能发现缺少宪法文件 | PASS | 隔离副本缺文件，返回非零；不是模型行为测试 |
| 完整压缩包逐成员回读 | PASS | {"members": 50, "CRC": "PASS", "byte_comparison": "all members"} |
| 全新解压副本验证 | PASS | 37个功能文件，77个Markdown本地引用；错误0 |

## 未执行与适用限制

- 用户实际Work/Codex安装与生效链检查。
- 27项真实模型行为用例。
- 新旧规则的token/时间/成功率对照。
- 任何宝典正文、宪法Word及原卷细则重新核验。
- Git提交、远端推送或持久库覆盖。

静态条款检查用于确认文字与引用同步，不能证明模型在每一条实际任务中都遵守。完整示范逐字节保全仅证明迁移未丢失旧文本，本轮没有重新读取宪法Word以确认转录准确性。

## 复查办法

在完整解压后的技能根运行：

```sh
python scripts/validate_bundle.py --root .
```

该脚本用于核对本次发布快照，属于维护工具，不参与普通制书任务的开工或结束条件。正常修改Skill后应更新版本及清单，不应把新内容与旧快照不一致误判为模型故障。

CHANGES.diff已在精确6.0.0副本实际应用，回放所得全部37个功能文件与新版相同。维护报告单独生成，旧版11个维护文件原字节归档；不可将旧差分对5.6或本地更晚状态强行应用。
