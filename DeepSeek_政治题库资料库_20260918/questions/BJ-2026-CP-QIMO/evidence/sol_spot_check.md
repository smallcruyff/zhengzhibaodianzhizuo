# BJ-2026-CP-QIMO Sol 组长抽检

## 抽检结果

1. **普通题 Q10：pass**
   - 题干、A—D 四项、3分、教师版 E3 答案 `C`、选择题 E1 不适用的角色边界闭合。
   - 当前 SHA：`85369d3054eacc271987227d9cc13d032e6146b5e6dcc8fd454846153b6bc1bb`。

2. **跨页题 Q2：pass**
   - 候选明确记录教师版题面页 1、2；题干、四个题肢、选项组合及 E3 答案 `A` 完整，未因换页丢行。
   - 当前 SHA：`1a90a7c5de73bf54f6b0f85fe9f0d85a3dce6a42300e657c8b4b3582daad49ef`。

3. **复杂图题 Q16：pass**
   - 已实际打开 image2/image3：image2 为红色雕漆器物，图下“雕漆”；image3 为红底彩色刺绣纹样，图下“京绣”。候选现按图片分开转写，没有再把 image3 写成 image2。
   - image2 SHA：`e2ee356dcb817c7fb2f10243686a198dda7c3ce1a136c3cd6099a2e08a1e5f57`；image3 SHA：`6e49362e3814ea8f4ab84f580131234f3da66a51e50de862109812c11ad393bb`。
   - Q16 题面表格、两图上下对应关系、教师版 E3、正式 E1 已分层；原题未逐题标分，候选未从第二部分 55 分倒推。
   - Q16 当前 SHA：`3eae218a503a1e8365dad4b55749a2e06bed203ef83b2ae16b2cb586a30c4b7d`。

## 签出

`conversion_complete_merge_ready_pending_controller_bundle_dry_run`。

独立 R2 已确认唯一图文对象名缺陷清零。缺独立原卷、独立答案和学生层是已声明的来源限制，不构成现有来源转换失败。待新包接口 `--dry-run` 通过后交总控。
