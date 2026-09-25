# BJ-2025-CY-ERMO Q19 structured delta v2 独立复核

结论：**PASS**。本工位是非生产者独立复核，只写本目录 `review/verification.json` 与本文件；没有应用替换，没有修改候选、旧 delta、共享题库、索引、manifest 或 `controller_ready`。

## 实物与页面

- 原始 `细则.docx`、组内 `sources/细则.docx` 和隔离 `isolated_sources/细则_same_sha.docx` SHA-256 均为 `73c36c3077dced724eb48b81aec7492e8e5ac59a7f72d7fb729d3581ea3fb5e8`。
- 直接解析同 SHA DOCX 的 OOXML 表索引 3 右栏 E1：源单元格为 927 字，SHA-256 为 `c514b32cf33567c4590e3e3fb13b8b7432614b8d56e5ffdeb0c5408cb3c1a284`；重建文本与源 delta 927 字逐字相同。
- 实际打开派生可读 PDF p9、p10、p11：PDF SHA-256 `64625d39104ccae68e19d9e428b478b2b66fbae610eadf8ec49d21dfaf6d3c3d`。三页均能读到 Q19 三类内容、跨页续行和表外提示，没有看到替换符、白方框或裁切。
- 页图 SHA：p009=`a510a6d84c1f13322b9b01b2a5060eb24ae46bf6716b4faafce78c88add93a72`，p010=`a9763d82ce056cf80004e3bc603478f0b616ee79348bb1eb899f2ddfa1b8264d`，p011=`f7e9729d9dd70d5ba41d01f6d7e79ac1df1dfa7ba154ae9c3d09c107b9cf5870`。
- `pairing_map.json` 中 52 个建议/理由文字锚点和 3 个表外说明锚点都能在对应派生页找到；派生页码不冒充原生 Word 12 页分页。

## 结构与配对

源 DOCX 的嵌套表为 9×3：每类占“标题行—内容行—说明行”，第三列是理由。v2 replacement 恢复为三张 Markdown 两列表，每张恰为 3 个数据行：

| 类别 | 源行 | 建议段数 | 理由段数 | 配对结论 | 派生页 |
|---|---:|---:|---:|---|---|
| ①公共法律服务 | 0/1/2 | 3 | 3 | 同索引自上而下 1↔1、2↔2、3↔3 | p9–p10 |
| ②普法工作方面 | 3/4/5 | 3 | 3 | 同索引自上而下 1↔1、2↔2、3↔3 | p10–p11 |
| ③依法治网方面 | 6/7/8 | 3 | 3 | 同索引自上而下 1↔1、2↔2、3↔3 | p11 |

总计 9 个建议—理由组。配对依据是两列各自非空段落的源内顺序，而不是跨列视觉最近基线；依法治网第三个理由前的空段不计为内容段，未改变三段同序配对。

每类表外的原句均保留：

> 以上三个左右对应关系，答出任意一个“建议 + 理由”，即可得3分

共 3 次。末尾降分提示也逐字保留：

> 提示：如上面建议和理由不能一一对应，则建议答出任意2个给2分，理由答出任意1个给1分。

源字面守卫通过：`利用利用` 源文与 replacement 各 1 次；`以上三个左右对应关系` 源文与 replacement 各 3 次。927 字源文经 NFKC、去空白后为 912 字，规范化 SHA-256 `3d9e0ce8ae1106e3e1f87dd3dd91f3bf97e87dc3b0f14525a832283f5a167195`；按 pairing_map 的源顺序（每类建议三段后理由三段）重建 v2 内容后完全相同。v2 为了保留左右对应而逐行交错，故没有把这种预期的结构重排误报成文字改写。

## 替换与保护守卫

| 项目 | 独立复算值 |
|---|---|
| 冻结 Q19 candidate base | `04b54100407cd40b5d47f5d0fb5bfd75266a6a293c2bb1321fd9e4053d2df819` |
| `old_exact` SHA / 命中 | `8562d8c7833663fb7578181ecb7088b72853a4588befeb002e81da4a8e2a932f` / 1 次 |
| v2 replacement SHA | `7fcf8198b80d5bd86b8f8fba25bc57b99315e77e3eeeadca4400c172dbdd26f4` |
| 内存一次替换 post SHA | `05f11bab92963bbf1028c99570e73a933999eea0b8dc9a119ce563f62b3aedef` |
| post `old_exact` 命中 | 0 次 |

内存替换没有落盘，当前候选仍为 base SHA。E0 题面段前后 SHA 均为 `0c7347220fde938c4ad50f713a28887de5c95175d0c1b5d3c660ae38289c0791`；E3 参考答案段前后 SHA 均为 `ed330b0386399b5ba907f1ec9a7a637a2918032cd826f3a0803aa72819c03984`；题号仍为 19、分值仍为 9 分；学生层为 N/A，SHA `d0fac3a2bee4702b009b8139d23539174993cc49e7242dda15c10b58af39bc3a`；邻题 Q18/Q20 SHA 仍分别为 `719c1c390cc80a357eb313503ef76c5dc1639d2cb5e77f4bcbb8cf80d581b0df`、`0b00b551eef12588551a1a98c10328e9c9121a1a57842c4c83861cb8f0771534`。

旧 flat delta `../q19_exact_delta.json` 文件 SHA 为 `98fca9b84c5b0ed296140e3f0998f295ddf0a0da84125ca5e55dd2379d525278`，本复核明确标记为 **SUPERSEDED_BY_V2**；旧文件本身未改。其旧 replacement SHA 为 `10f5772a9ab0afda42810d935ff7371596646259dba5f9256805dbb70c8884d6`，不再作为本轮结构化替换值。

最终判定：**PASS**。v2 结构、页面证据、源文字规范化、特殊字面、base/old/replacement/post SHA 以及 E0/E3/9分/学生层/Q18/Q20 守卫均通过；状态仍是 `proposal_not_applied`，等待总控按单写入流程处理。
