# Source-support production validation

结论：`PASS_PRODUCTION_AWAITING_INDEPENDENT_REVIEW`。

- 两份原 PDF fresh SHA：2/2 通过。
- 8张原卷页图、5张正式评分页图：13/13 与既有已核缓存逐字节一致。
- Q3题图与已核父资产逐字节一致，图下注名“张京生　王元珍”可读。
- 两份按页完整清洗稿、两份 native 全文、两份 layout 全文均已携带；清洗稿与缓存逐字节一致。
- 当前共享21题 SHA：21/21 与 `source_index.json` 锁定值一致；Q18 为总控已接受的 `9e1ef21…6dd64b`。
- 5条既有回执路径和 SHA：5/5 通过。
- 本 delta 中题目 MD 数量：0；没有重新 materialize、没有改共享、索引或 manifest。

角色边界：原卷 p007–p008 是内嵌 E3/等级材料，正式评分 p001–p005 才是 E1；聚合阅卷报告不是学生原答。Q17 native 异常与视觉读法分层并列。学生层继续为 `source_not_provided`。

生产 payload 共27项，树 SHA-256 为 `8ee3d280f380b2441a330d0c7428df552400d9ebf42964a17531568bb64afda7`（不含本 validation 和后续 review）。
