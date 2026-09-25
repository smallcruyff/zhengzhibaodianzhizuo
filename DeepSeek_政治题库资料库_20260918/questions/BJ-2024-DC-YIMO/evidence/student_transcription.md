# BJ-2024-DC-YIMO：评分 PPTX 学生样卷/批注/实得分转写

## 证据范围与使用方式

- 试卷键：`BJ-2024-DC-YIMO`。
- 学生/批改来源：`/Users/wanglifei/Desktop/2024模拟题/2024东城一模/细则/细则.pptx`，SHA-256：`4b2073bcc9e26f626b49b66dd6e0c64ec93650292d50719806830d7aea9fa3ce`。
- PPTX 共 74 张幻灯片；本回执处理其中出现学生答卷或批改界面的 12 张：28、29、30、35、42、46、47、52、58、65、73、74。
- 每个样本同时保留：PPTX 内嵌原图（`../assets/student_samples/pptx_media/`）、审计渲染页（`../assets/student_samples/rendered_slides/`）以及在审计目录中的原始引用。内嵌原图是逐字复核的优先视觉证据；渲染页用于确认它在幻灯片中的位置和周围界面。
- 原生文字层文件 `../assets/student_samples/native_text/slideNNN.txt` 均为空；学生手写内容不能由文字层恢复。
- 下面的转写是“可稳定辨认的字逐字保留＋不能稳定辨认处显式 `[uncertain]`”。不以参考答案反推学生原文，不把涂改后的猜测当成原字。任何转写与图片不一致时，以图片为准。
- `⟦不可辨区域⟧` 表示该处保留了字迹占据的连续区域，但当前截图分辨率/拍屏摩尔纹不足以安全识读；对应坐标和原图均在 `inventory.json` 与本目录资产中保留。

## 样本总表

| 样本 | 题号/小问 | PPTX页 | 画面可见实得分 | 学生图像 | 主要批注/标记 |
|---|---|---:|---:|---|---|
| Q16-S1 | 16 | 28 | 7.0/7 | `../assets/student_samples/pptx_media/slide28_image26.jpeg` | 右侧在线评分 7；黑色手写答案，无可安全分离的红色逐点标记 |
| Q16-S2 | 16 | 29 | 7.0/7 | `../assets/student_samples/pptx_media/slide29_image27.jpeg` | 右侧在线评分 7；黑色手写答案，保留画面中的改写/下划线 |
| Q16-S3 | 16 | 30 | 0/7 | `../assets/student_samples/pptx_media/slide30_image28.jpeg` | 红色大字“没答哲学”；右侧分数 0；答案区仍可见文化角度手写内容 |
| Q17-S1 | 17 | 35 | 7.0/7 | `../assets/student_samples/pptx_media/slide35_image31.jpeg` | 右侧在线评分 7；黑色批注/插入字，右侧红色 7.0 |
| Q18-S1 | 18（1） | 42 | 8.0/8 | `../assets/student_samples/pptx_media/slide42_image35.jpeg` | 右侧红色 8.0；小问栏可见 2 分、6 分 |
| Q18-S2 | 18（2） | 46 | 6.0/6 | `../assets/student_samples/pptx_media/slide46_image39.jpeg` | 右侧红色 6.0；右侧小问栏输入 6；有下划线、圈/改写痕迹 |
| Q18-S3 | 18（2） | 47 | 6.0/6 | `../assets/student_samples/pptx_media/slide47_image40.jpeg` | 右侧红色 6.0；有划线、删除/插入和黑色批改字 |
| Q18-S4 | 18（3） | 52 | 6.0/6 | `../assets/student_samples/pptx_media/slide52_image43.jpeg` | 右侧红色 6.0；右侧显示“18-3(6.0分)”与输入 6 |
| Q19-S1 | 19 | 58 | 未显示 | `../assets/student_samples/pptx_media/slide58_image47.png` | 未见可确认的实得分；整张是手写答案图 |
| Q20-S1 | 20 | 65 | 8.0/8 | `../assets/student_samples/pptx_media/slide65_image50.png` | 左侧红色“8分”；答案中有多个红色“1”逐点标记；右侧小问栏为 8 |
| Q21-S1 | 21 | 73 | 未显示 | `../assets/student_samples/pptx_media/slide73_image53.jpeg` | 未见可确认的实得分；底部有超出黑色答题框无效提示 |
| Q21-S2 | 21 | 74 | 未显示 | `../assets/student_samples/pptx_media/slide74_image54.jpeg` | 未见可确认的实得分；底部有同一答题区提示 |

## 逐样本转写

### Q16-S1：slide 28，得分 7.0/7

来源：`../assets/student_samples/pptx_media/slide28_image26.jpeg`；幻灯片渲染：`../assets/student_samples/rendered_slides/slide28.png`。

画面题头为“16.（7分）”，右侧红色显示“7.0”，右侧小框显示 `16(7.0分)` 和输入值 `7`。答案区为连续黑色手写，分为 ①—④；没有可以安全区分为教师红笔的逐点标记。

可辨手写转写（原有行序）：

```text
① 矛盾具有普遍性、[uncertain]，要用对立统一的观点看问题。不同民族的文化有着不同的特点，[uncertain]，为人类文明进步作出贡献。

② [可辨开头] 实践是认识的基础，[uncertain]；[uncertain]

③ [可辨开头] 联系具有普遍性、客观性，事物之间相互联系，[uncertain]；中华文化[uncertain]世界文化多样性，[uncertain]。

④ [可辨开头] 价值观对人们的实践活动[uncertain]。价值观[uncertain]；[uncertain]
```

说明：slide 28 的拍屏摩尔纹和倾斜使第 ②—④ 点的部分字形无法达到安全逐字级别；这些区域没有用答案或讲评内容补齐。完整黑色笔迹、下划线和页面边界以原图为准。右下方还可见第 17 题题头。

### Q16-S2：slide 29，得分 7.0/7

来源：`../assets/student_samples/pptx_media/slide29_image27.jpeg`；幻灯片渲染：`../assets/student_samples/rendered_slides/slide29.png`。

画面题头为“16.（7分）”，右侧在线评分显示 7。答案区是另一张手写样卷，能看到 ①—④ 的分点、若干下划线/改写痕迹；未见可安全分离的红色逐点批注。

可辨手写转写（不对难辨字作规范化）：

```text
① [开头可辨为] 矛盾/矛盾的观点[uncertain]；[uncertain]对立统一的观点看问题。不同民族的文化有着不同的特点，[uncertain]。

② [可辨片段] 中国共产党领导中国人民走出中国式现代化道路，创造了人类文明新形态；[uncertain]

③ [可辨片段] 中国[uncertain]促进世界文明交流互鉴、相互融合，不仅[uncertain]，也让世界文化变得更加绚丽多彩；[uncertain]

④ [可辨片段] [uncertain]价值观/人民[uncertain]；中华文明新形态[uncertain]，中国式现代化[uncertain]。

最后，[可辨片段] 我们应[uncertain]文化自信，推动中华优秀传统文化[uncertain]，为世界[uncertain]。
```

说明：该样本的第 ①—④ 点之间有连写、覆盖和局部涂改；`../assets/student_samples/pptx_media/slide29_image27.jpeg` 是 PPTX 内嵌原始拍屏图，保留了比渲染页更多的上下边界。

### Q16-S3：slide 30，得分 0/7

来源：`../assets/student_samples/pptx_media/slide30_image28.jpeg`；幻灯片渲染：`../assets/student_samples/rendered_slides/slide30.png`。

画面顶部红色大字可辨为“没答哲学”，右侧红色分数显示 0；这不是学生笔迹，作为教师/阅卷界面批注单列。学生答案区仍有三段黑色手写：

```text
① 中华民族的文化成就[可辨为“既是/又是民族的，也是世界的”][uncertain]。中华民族有5000年源远流长、博大精深的历史文化，为世界文明的发展做出了不可磨灭的贡献。

② 中国共产党领导中国人民走出了中国式现代化道路，创造了人类文明新形态，不仅促进了自身发展，也为世界上[uncertain]发展中国家提供了发展经验。

③ 中国秉持对外开放，世界文明交流互鉴、相互融合，不仅为中华民族[uncertain]世界民族之林[uncertain]，也让世界文化变得更加绚丽多彩。中国[uncertain]推动构建人类命运共同体[uncertain]，中国方案、中国智慧、中国力量，[uncertain]。
```

页面没有看到学生在答案区写出的哲学角度；红色“没答哲学”和 0 分应原样保留，不能把学生的文化角度答案改判为 7 分。

### Q17-S1：slide 35，得分 7.0/7

来源：`../assets/student_samples/pptx_media/slide35_image31.jpeg`；原生裁图副本：`../assets/student_samples/native_shape_refs/slide035_shape01.jpg`；幻灯片渲染：`../assets/student_samples/rendered_slides/slide35.png`。

可辨手写转写：

```text
该市政府做法是错误的，干扰市场竞争。

① 以政府未依法履行经济建设、社会管理职能，但没有依法行政，违反了《反垄断法》的规定，仅允许竞得拍卖权的共享单车企业等进入，排除了市场竞争；

② 不利于维护市场秩序，发挥市场在资源配置中的决定性作用，限制了市场公平竞争，阻碍了优胜劣汰的市场退出机制，易造成市场混乱；

③ 侵犯了企业合法权益，不利于诚信守法经营，易造成垄断，缺乏创新动力，间接损害了消费者合法权益；

④ 该政府应坚持依法行政，依“条例”允许主体等进入，平等权规范公平文明执法，维护市场基础制度规则统一，坚持毫不动摇鼓励、支持、引导非公有制经济等参与市场竞争，促进[uncertain]市场秩序。
```

可见批注/改写：第 ① 点“拍得/竞得特许经营权的主体”等字句附近有黑色插入性批注，视觉上可辨为“[不符合/不符]‘案例’要求”一类提示；该批注的个别字形不稳定，故不把方括号内内容当作确定原文。右侧红色 `7.0`、输入框 `7` 和提交界面保留。没有另见红色逐点给分。

### Q18-S1：slide 42，18（1），得分 8.0/8

来源：`../assets/student_samples/pptx_media/slide42_image35.jpeg`；原生裁图副本：`../assets/student_samples/native_shape_refs/slide042_shape01.jpg`；幻灯片渲染：`../assets/student_samples/rendered_slides/slide42.png`。

右侧红色显示 8.0；右侧小问栏可见 `18(2.0分)` 输入 2 和 `18(6.0分)` 输入 6。当前页从第 18 题（1）开始，底部已经露出（2）题头和下一行，故这里只转写当前页可见区域，不推断后续页。

```text
（1）（8分）依托优势：北京人才资源总量增加，包含科研院所和高校资源，[uncertain]。

经费投入大幅提升，数字经济[uncertain]发展，科技体制、[uncertain]改革[uncertain]。

如何：人才资源量增加，创新型人才增多，[uncertain]；[uncertain]。

促进技术创新和发展，转变经济增长方式，推动经济发展[uncertain]。

依托[uncertain]数字基础设施，推动数字经济发展，降低[uncertain]成本，促进[uncertain]发展。

科研经费占比逐年提升，为创新发展注入活力，促进新质生产力发展；[uncertain]。

北京建设数字基础设施，实现数字经济[uncertain]，依托[uncertain]改革措施，推动[uncertain]。

（2）（6分）△ 政协开展调研课题，召开座谈会，充分发挥[uncertain]……（本页下缘截断）
```

说明：Q18（1）的数字、专业名词和连词有多处受拍屏纹理影响，未用题面或评分文字反填。原图中的 2 分、6 分小问栏和红色 8.0 是评分证据。

### Q18-S2：slide 46，18（2），得分 6.0/6

来源：`../assets/student_samples/pptx_media/slide46_image39.jpeg`；原生裁图副本：`../assets/student_samples/native_shape_refs/slide046_shape01.jpg`；幻灯片渲染：`../assets/student_samples/rendered_slides/slide46.png`。

可辨手写转写：

```text
（2）（6分）政协发挥政治协商、民主监督、参政议政职能，政协委员围绕新质生产力建言献策、凝聚共识，充分发挥[uncertain]。

政协通过召开座谈会、组织协商，听取各方意见，提出[uncertain]建议，推动[uncertain]发展。

政协协商民主制度具有独特优势，政协委员围绕新质生产力建言献策，发挥协调作用，推动[uncertain]。

政协委员通过提案和协商履行职责，提案主办单位与委员交流，推动问题解决。

通过督办提案、沟通协调，发挥民主监督职能，推动政府/有关部门改进工作。
```

说明：原图上部是上一小问末行的截断片段，下部出现“（3）（6分）”题头但没有完整（3）答案；本转写不把下缘以外的内容补入。右侧红色 6.0、小问栏 `18-2(6.0分)` 与输入值 `6` 原样保留。画面中有黑色下划线、圈写、插入字和覆盖笔画，无法确定每一笔是学生自改还是阅卷标记，故不强行归类。

### Q18-S3：slide 47，18（2）另一份样卷，得分 6.0/6

来源：`../assets/student_samples/pptx_media/slide47_image40.jpeg`；原生裁图副本：`../assets/student_samples/native_shape_refs/slide047_shape01.jpg`；幻灯片渲染：`../assets/student_samples/rendered_slides/slide47.png`。

可辨手写转写：

```text
（2）（6分）① [开头有覆盖/涂改，稳定可辨片段] 围绕/政协履行[uncertain]职能，围绕新质生产力建言献策，促进[uncertain]。

政协协商民主制度具有独特优势，能够充分发挥协商民主作用，推动[uncertain]；[uncertain]。

② 政协委员[uncertain]围绕新质生产力建言献策，提出[uncertain]，充分发挥[uncertain]作用，推动[uncertain]。

③ 政协[uncertain]发挥民主监督作用，召开提案督办会，推动有关部门办理提案；[uncertain]。

（3）（6分）① 我认为传统产业与未来产业[uncertain]，要[uncertain]。
```

可见批注/涂改：第（2）题开头有多处黑色覆盖线；中部有圈号、上方插入字（视觉上像“[uncertain]”），第③点附近有删除线和重写；下方第（3）题开头也有下划线。右侧红色 6.0、输入框 6 和绿色提交/确认图标保留；底部系统栏可见“试题 18-2”“密号 -18590496”“评卷量 284”“速度 18.61秒/份”“平均分 3.99分”“用时 00:00:53”。

### Q18-S4：slide 52，18（3），得分 6.0/6

来源：`../assets/student_samples/pptx_media/slide52_image43.jpeg`；原生裁图副本：`../assets/student_samples/native_shape_refs/slide052_shape01.jpg`；幻灯片渲染：`../assets/student_samples/rendered_slides/slide52.png`。

可辨手写转写：

```text
（3）（6分）要用联系观点、全面的观点[uncertain]。传统产业与
未来产业相互联系、相互补充，传统产业是[uncertain]发展的基础，未来产业[uncertain]。

传统产业发展，[uncertain]；要努力打造[uncertain]，再产业是[uncertain]。

传统产业[uncertain]，要用未来产业带动[uncertain]，推动传统产业转型升级，实现高质量发展。

要用辩证的观点看待，认识到传统产业与未来产业相互联系、相互促进，二者[uncertain]。
```

说明：页面上缘有上一小问末尾残行；（3）答案正文从“要用联系观点……”开始。可见的下划线、黑色覆盖/改写和右侧“更改”下拉界面保留。右侧红色 6.0、小问栏 `18-3(6.0分)` 与输入值 6 为画面分数。

### Q19-S1：slide 58，实得分未显示

来源：`../assets/student_samples/pptx_media/slide58_image47.png`；原生裁图副本：`../assets/student_samples/native_shape_refs/slide058_shape01.png`；幻灯片渲染：`../assets/student_samples/rendered_slides/slide58.png`。

这是单独截取的第 19 题手写答卷图，没有题头、右侧评分栏或可确认分值。可辨字很少，拍屏摩尔纹覆盖几乎每一行；不作答案反推。按图像自上而下保留如下可辨片段：

```text
[第1行] [uncertain]权利义务：[uncertain]权利人[uncertain]积极[uncertain]行使[uncertain]，以便[uncertain]……

[第2行] [uncertain]中，诉讼时效[uncertain]，自[uncertain]……

[第3行] [uncertain]，故[uncertain]积极[uncertain]，还会[uncertain]……

[第4行] [uncertain]法律规定，诉讼时效不适用[uncertain]，保护[uncertain]的[uncertain]合法权益。

[第5行] [uncertain]，赡养义务[uncertain]，成年子女[uncertain]父母[uncertain]。

[第6行] [uncertain]赡养费[uncertain]，有利于[uncertain]老年人[uncertain]基本生存权利[uncertain]，构建和谐家庭/彰显[uncertain]。
```

说明：上述每行均是“可辨片段＋不确定占位”，不是把模糊字猜成标准答案。完整连续笔迹、行线和裁剪边界只以 `slide58_image47.png` 为准；`inventory.json` 记录了整体学生答卷框和逐行不确定区域。

### Q20-S1：slide 65，得分 8.0/8

来源：`../assets/student_samples/pptx_media/slide65_image50.png`；原生裁图副本：`../assets/student_samples/native_shape_refs/slide065_shape01.png`；幻灯片渲染：`../assets/student_samples/rendered_slides/slide65.png`。

可辨手写转写（保留原有五点结构和错别字/不稳定字）：

```text
① 围绕“绿色”观念，多地[uncertain]管理理念，促进重点行业设备更新、[uncertain]消费品以旧换新，促进消费，扩大内需。

② 降低物流成本，推动[uncertain]交换效率，带动[uncertain]，物通国内外循环。

③ 对照国际标准[uncertain]国内改革，有利于国内国际双循环，促进[uncertain]经济活力。

④ 取消部分领域[uncertain]，全面降低市场准入[uncertain]，促进贸易投资自由化，吸引外资，增加经济活力。

⑤ 通过构建以国内大循环为主体、国内国际双循环相互促进的新发展格局，促进经济高质量发展。
```

评分/批注：画面左侧红色“8分”；学生答案上方和行间分布多个红色“1”标记，原图中至少可见 9 个逐点红色“1”（坐标见 `inventory.json`）；右侧小问栏显示 `20(8.0分)`，输入框为 `8`。画面最右上还露出一个截断的红色“0.”，其上下文不足以安全解释为本题得分，故不把它当作本题分数。红色标记不覆盖的黑色手写字按原貌保留，受红色标记遮挡的位置以图片为准并标 `[uncertain]`。

### Q21-S1：slide 73，实得分未显示

来源：`../assets/student_samples/pptx_media/slide73_image53.jpeg`；原生裁图副本：`../assets/student_samples/native_shape_refs/slide073_shape01.jpg`；幻灯片渲染：`../assets/student_samples/rendered_slides/slide73.png`。

可辨手写转写：

```text
① 提速“通勤圈”，完善京津冀交通网络体系，提升人流、物流[uncertain]流动，促进资源[uncertain]配置，实现[uncertain]发展。

② 优化“功能圈”，[uncertain]重点，发挥[uncertain]与重点[uncertain]；北京以[uncertain]首都功能[uncertain]，推动[uncertain]新区和[uncertain]城市副中心发展，促进区域[uncertain]。

③ 打造“产业圈”，创新经济发展模式，三地充分发挥比较优势，促进[uncertain]产业链[uncertain]，推动[uncertain]。
```

画面未见可确认的红色实得分或右侧评分输入。底部提示文字可辨为“请在各题目的答题区域内作答，超出黑色矩形边框限定区域的答案无效”；该提示不是学生答案，已与正文分开记录。学生答案区存在下划线/行线，未见能安全识读的教师逐点红批。

### Q21-S2：slide 74，实得分未显示

来源：`../assets/student_samples/pptx_media/slide74_image54.jpeg`；原生裁图副本：`../assets/student_samples/native_shape_refs/slide074_shape01.jpg`；幻灯片渲染：`../assets/student_samples/rendered_slides/slide74.png`。

可辨手写转写：

```text
① 三圈联动关注首都圈发展的整体性，坚持全面看问题，通过发挥京津冀各部分在区域内的优势，资源优化配置，实现整体功能大于部分之和。

② 三圈联动要抓住关键，同时坚持两点论与重点论，发挥[uncertain]；北京[uncertain]在全局/整体基础上，带动[uncertain]发展。

③ 三圈联动构成的交通网络作为重要基础设施，降低了三地联通成本，促进资源优化配置。

④ 三圈联动有利于科技创新成果[uncertain]交流/转化，推动产业间合作，促进[uncertain]发展。
```

画面未见可确认的实得分、红色评分数或右侧输入值。底部同样可见“请在各题目的答题区域内作答，超出黑色矩形边框限定区域的答案无效”提示；学生正文和系统提示分开保留。没有把标准答案的“通勤圈/功能圈/产业圈”三点强行补入学生文字。

## 批注、涂改和分数的边界说明

1. 红色数字（Q16 的 7.0、Q17 的 7.0、Q18 各小问的 8.0/6.0、Q20 的 8 分及逐点“1”）按画面记录；没有画面分数的 Q19、Q21 不从标准答案或样卷内容推算。
2. 黑色插入字、圈号、下划线、覆盖线和删除线均随原图保留。除 slide 35 附近视觉上可辨的“[不符合/不符]‘案例’要求”外，无法安全区分是学生自改还是教师标注的笔画不另行归因。
3. Q16-S3 的红色大字按视觉读取为“没答哲学”；如果后续在更高质量来源中证实不同字形，应以新来源覆盖本行，并保留本回执作为旧图审计记录。
4. 每个 `[uncertain]` 均对应 `inventory.json` 中的页/图像坐标或整行范围；不确定字符没有被答案、讲评文字、常识或上下文替换。

## 当前状态

- 学生图像和嵌入原件：已保存。
- 12 张学生样本的页位、题号、小问、可见分数：已盘点。
- 手写逐字层：已尽力转写；多个截图受低分辨率/摩尔纹影响，仍保留明确不确定区，**不能把本回执称为“全部手写字均无歧义”**。
- 共享题库、父稿、索引和 `conversion_manifest.json`：本任务未修改。
