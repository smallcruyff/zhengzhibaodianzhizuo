# 选必二《法律与生活》活动快照

`snapshot_revision: 7`
`snapshot_date: 2026-09-05`
`artifact_status_as_of: 2026-09-03；本轮只更新规则引用，未重审成品或确认旧进程存活`
`book_ledger_revision: 26`
`thread_binding: 选必二chat、选必二work、法律宝典相关固定线程`
`rule_revisions: constitution 2；project-rules 41；requirements 179；artifact-manifest 107；correction-log 144；evidence 12；counting 12；style 29；fidelity 14；source-inventory 29；continuity 16`

## 本次执行迁移边界

执行与停止按[AGENTS.md](../../AGENTS.md)；每轮实质制书按[宪法读取门禁](../project-constitution.md#权威与读取门禁)全文重读，其他无变化资料按需复用。旧的仅接受补证下一动作限定原补证任务，不阻止用户新授权的独立修订。以下版本、SHA、计数及未决是截至2026-09-03的继承记录；本轮没有自动晋升、重新取证或复跑验收。涉及官方分档的历史排除结论，只有回到同题原件复核后才能更新；不得在迁移时批量改成通过。

## 当前裁决

v14.1继续是唯一结构、格式回滚母本；`ART-XB2-V15.0-EDITABLE-REBUILD-CAND-20260903`是最新实际`working_head`。本轮在v14.1冻结的四大块、21个二级节点、四个主观题栏目和三个附录中，把235个唯一题面全部实质重建为Word可编辑段落、原生表格与最少必要图示，纯图片题面降为0。v15.1、v15.2仍是已否决双轴结构分支，禁止作为母本、目录、样式或正文来源。

## 三类成品角色

| 角色 | 文件身份 | 状态 |
|---|---|---|
| **rollback_base** | `ART-XB2-V14.1`；Library `libfile_89ba1cd4177481919c15b27b13c80879`；472,102字节；SHA-256 `986b0ff99978ebfcc425cce723b8be5550cea7bfecae4140ea4a33dbcd33a2a9` | 唯一有效结构与格式母本 |
| **working_head** | `ART-XB2-V15.0-EDITABLE-REBUILD-CAND-20260903`；DOCX Library `libfile_8a01a540a2408191822f072c78875110`；29,402,748字节；SHA-256 `dc646b86dd5acf5f20bf5f99e574e9bfa07397b320a7eb04cf7277428d47315a` | 全题可编辑实质重建受控候选；三路独立终审PASS；两项E1阻断未关闭 |
| **release_head** | 无 | `FINAL-SUBJ-087`、`FINAL-SUBJ-089`未关闭，不得晋升 |

配套PDF：Library `libfile_8691d52195cc8191a9929d08e90c8957`；规范视觉终审源8,323,233字节，SHA-256 `629bbc923bc4cf9f8de0c8ccd57dd86397b4696973c892476be61b084e62fc9c`；Library C2PA回读8,348,397字节，SHA-256 `6362da908af46f6232b8b836873b916df55bcf1f6170a74783f7f3eda3c33416`；A4共464页。受控候选审计报告：Library `libfile_5eb210355a788191a04823836a77835a`版本1；6,801字节；SHA-256 `62d600f249f2e1b3dca2ee54a1c52eb2954372f7665d5b061f539ee7863fb686`。

## 已冻结成果

- 235个唯一题面＝146道选择题＋89道主观题；正文题面落位470，`【题目】`471个且471/471后接原生可编辑题面；A1/A2各146，A2完整题面落位1。
- 3,842次可编辑段落落位、1,481个唯一段落块；52个唯一原生表格组件形成136次表格落位，355/355行启用`cantSplit`；8个唯一必要图示形成21次落位。
- 包内媒体8个且8/8被使用；纯图片题面、孤儿媒体、断裂关系、占位符和缺失订正均为0；Source Han Sans SC Regular/Bold两种字体实体有效。
- 29/29目录条目、29个内部链接及目标页一致；第2页保留`preface`书签且视觉全白；最终PDF 464/464页独立重渲染有效。
- 三路独立R3终审全部PASS：内容规范化指纹`36000c810d76e82538d7d1c2644ad4f2ac4e3ad33b7ca0b43c2d6b1f933f0a66`无漂移；OOXML、可编辑性、ZIP、字体、书签及关系PASS；19张联系表覆盖464页，R2十处内层标签孤置10/10修复，成品级视觉阻断0。

## 未决与下一动作

仅余两项正式评分证据：`FINAL-SUBJ-087`为2026门头沟一模Q18（1），题面8分，历史正式载体线索出现三个“各占4分”角度但没有任选、封顶或折算规则；`FINAL-SUBJ-089`为2026顺义二模Q18（2），现行“评标”DOC中的该小问只有参考作答／阅卷方向，没有可操作E1评分槽。只接受同卷、同题、同小问的正式评分标准、评分细则、评标、阅卷总结／报告／讲评等合格E1；取得后同步DOCX、PDF、审计材料与发布状态。

2026题源本轮已重新枚举：`SRC-010`—`SRC-013`、`SRC-015`、`SRC-016`六个ZIP及`SRC-014` PDF均完成文件级完整性复核；ZIP CRC全部通过，无加密、路径越界、符号链接或零字节文件。`SRC-009 2026各区一模.zip`这次仍未形成完整工作区文件；发现的所有失败上传临时文件都是从字节0开始的严格前缀，最长234,225,664字节，相对登记完整源464,810,953字节仍缺230,585,289字节，无中央目录，内容只到东城目录，尚未到门头沟。它们只用于上传故障诊断，未作为完整题源或E1使用。已在留痕后清理27个可恢复的重复失败前缀，共1,579,286,528字节；全部可见完整原源、v15.0成品及一份当前最长可用诊断前缀保留。下一步只需重新取得完整`2026各区一模.zip`，不必重传或重审其他2026文件。

`next_action: 重新取得完整SRC-009后只读门头沟一模正式载体；继续为FINAL-SUBJ-087与FINAL-SUBJ-089取得同卷同题同小问合格E1`
`resume_token: XB2-V15.0-EDITABLE-REBUILD-REMAINING-2-E1`

## 按需加载

评分冲突读`evidence-policy.md`；原卷与题源读`source-inventory.md`、`original-fidelity-checklist.md`；多节点计数读`counting-sorting-policy.md`；Word与视觉读`style-spec.md`。若用户重传`2026各区一模.zip`，只为反向题源完整性及`FINAL-SUBJ-087`继续检索读取；`FINAL-SUBJ-089`的现有顺义原卷与评标DOC已深检完毕，不重做。两项均不得触发重做已通过的235题可编辑重建和464页视觉。
