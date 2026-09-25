# BJ-2025-DC-ERMO source support delta

状态：`source_support_only_not_question_materialization`。

本目录只补充当前共享卷缺少的可携带来源入口：两份原 PDF、原卷 8 页与正式评分材料 5 页的完整页图、缓存原生/清洗/版面转写、卷首和印刷说明、题级页映射、现有 21 题 SHA 锁，以及既有 13 页视觉检查回执链。没有复制、重写或重新 materialize 任何题目 MD；没有修改共享题库、索引或 manifest。

## 原始来源

- [主卷 PDF](sources/original/main_exam_试卷.pdf)：8 页，SHA-256 `9b287871f660f23de9593be4c16952103c1c6873d6bd52d25ddd57ddd1a8d268`。
- [正式评分材料 PDF](sources/original/formal_scoring_细则.pdf)：5 页，SHA-256 `606dbae1d5ce3e59c8daef227c8b797cfbda2b7f90b8c9e07f47654af13e1cc2`。
- [原卷页图](assets/page_index.md#原卷与内嵌答案)：p001–p008，全部可读。
- [正式评分页图](assets/page_index.md#正式评分材料)：p001–p005，全部可读。
- [Q3 题图](assets/figures/Q3_painting_caption.png)：图下注名明确为“张京生　王元珍”，题名为《没有共产党就没有新中国》。这只是图字定位，不改 Q3 正文。

## 转写层级

完整转写入口见 [transcriptions/README.md](transcriptions/README.md)：

1. `cached_native/` 保存缓存原生文字层，不静默修字；
2. `cached_cleaned/` 保存按页完整清洗稿；
3. `layout/` 保存版面型全文抽取，辅助核对跨页、表格和题号；
4. `visual_variants.md` 只登记已有视觉复核确认的差异，不把推测写回全文。

其中 Q17 的 native 层确有“輸送/仙远/随中办/诉让/立電/办素”等提取异常；视觉确认读法与 native 字面并列保留。原卷 p007–p008 的参考答案与等级表仍属于同一试卷内嵌 E3/等级材料，不是独立答案文件，也不是正式 E1。正式评分 PDF p001–p005 单独作为 E1 来源层。

## 现有视觉与题级覆盖链

- `repair_2025_dc_ermo/checkpoint.json`：主卷 p001–p008、评分 p001–p005 全部实际打开；13 页源页 SHA 与题级修复边界登记。
- `complete_2025_dc_ermo_remaining/completion.json`：补充题逐题核验，确认原卷答案/等级与正式评分材料角色分开，学生层为 `source_not_provided`。
- `materialize_2025_dc_ermo_merge_ready/verification.json`：21题与局部化资产、链接和来源 SHA 机械核验。
- `group_2025_east/.../consolidated_signoff/verification.json`：当前共享 21 题的新鲜度与重点视觉复核。
- `new_controller_20260922/BJ-2025-DC-ERMO_Q18_current_metadata_acceptance.json`：总控接受当前 Q18 等价元数据措辞；不追认未知原执行者/时间。

上述回执路径和 SHA 在 `source_index.json` 中完整登记。学生原答、教师批注、评分标记和逐生实得分的独立源件并未提供，继续明确记录为 `source_not_provided`，不得以聚合阅卷报告替代。

## 总控使用方式

这是可携带的 source-support 附件，不是旧 materialization 的替代品，也不能触发旧包重跑。总控可将本目录作为当前共享 21 题的来源入口；使用前核 `source_index.json` 的两份源 SHA 与 `current_shared_question_sha256`。任何题目内容更新仍须另走精确候选与单写合并流程。
