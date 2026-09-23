# 北京高考政治教研 Skill 6.0.2

**版本：6.0.2-20260908。修订日期：2026-09-08，America/Los_Angeles。前版：6.0.1-20260905。**

本次恢复每轮实质制书前主代理全文读取宪法及示范，同时保留Astra的常规执行自主权。版本号属于这个Skill；模型选择与工具权限由实际宿主提供。

## 核心安排

每轮实质制书先完整读取宪法，明确标准后直接完成当前请求。新一轮用户修改意见触发重读，同一轮连续操作不反复启动；事务性查询、原件补发和单纯解释条款按需读取。详细边界集中在宪法，其他文件只保持一致引用。

原题、正式评分证据、已确认书级结构和真实验收保持约束。工具、处理顺序、批次、合适的并行任务与可恢复修复交给主代理判断；不配置固定旧模型、逐步开工审批、保活或无条件Git完成门。

本地 Work 模式直接读取四个桌面题源根目录：`/Users/wanglifei/Desktop/2024模拟题`、`/Users/wanglifei/Desktop/2025模拟题`、`/Users/wanglifei/Desktop/2026模拟题`、`/Users/wanglifei/Desktop/历年高考题及细则`。这些目录分别提供三年模拟题、历年北京高考真题及对应细则，是宝典制作的根源与依据；可访问目录不等于逐题证据已闭环。

## 使用

把完整ZIP交给可以访问实际项目的Work或Codex，使用[migration/APPLY_IN_WORK.txt](migration/APPLY_IN_WORK.txt)。先定位真正生效的同名Skill与相关AGENTS/override，备份并按语义合并；不只替换SKILL.md，不覆盖本地更晚的书稿、来源和状态。

本包的历史生成不代表其他项目或远端已安装；本次 6.0.2 更新已写入当前用户级安装路径 `/Users/wanglifei/.codex/skills/beijing-gaokao-politics`，但仍不代表其他宿主或远端自动同步。普通Chat可读取附件中的规则；本次没有修改宪法Word、原卷、正式评分细则或任何宝典正文。

## 文件职责

| 文件 | 作用 | 读取方式 |
| --- | --- | --- |
| SKILL.md | 入口、任务边界、八条成品链路由 | 使用技能时 |
| AGENTS.md | 执行、授权、代理、恢复和完成 | 初次使用或有变化时 |
| references/project-constitution.md | 四项成品原则、完整示范与读取门禁 | 每轮实质制书前全文 |
| references/active/ | 真实工作稿、来源身份、未决与准确断点 | 当前项目和相关册 |
| references/专业协议 | 细则证据、原题保真、计数、排序、样式 | 本轮命中时 |
| references/book-*与账本 | 原始决定、历史纠错、版本谱系 | 按具体问题定位 |
| legacy/与migration/ | 旧机制、迁移差分、用户讲解与验证 | 仅维护或追溯时 |

原题库、宝典DOCX与宪法Word原件不在Skill包内。历史日期和旧成品状态保留其原意；本次修订不证明这些成品已重新审核。

## 阅读与核查

完整说明见[migration/GUIDE.md](migration/GUIDE.md)，实改记录见[migration/CHANGELOG.md](migration/CHANGELOG.md)，可应用的功能文件差分见[migration/CHANGES.diff](migration/CHANGES.diff)，验证边界见[migration/VALIDATION.md](migration/VALIDATION.md)。旧6.0.0维护材料按原字节保存在migration/history/6.0.0-maintenance.zip中，普通制书不解压读取。

```bash
python3 scripts/validate_bundle.py
```

该工具只读核对交付包的功能文件身份、引用与关键条款文本。它不证明模型确实按条款行动，也不作为普通制书的新开工门。安装保留本地更晚状态时，交付快照哈希可能不同；须解释差异，不能为了匹配本包覆盖有效成果。
