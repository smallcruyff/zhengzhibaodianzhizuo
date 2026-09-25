# BJ-2025-CY-ERMO Q19 structured delta v2

状态：proposal_not_applied。

本目录是对上一版 q19_exact_delta 的 superseding exact delta。上一版已核通过同 SHA DOCX 表4右栏 E1 的 927 字内容，但把三类内容压成了顺序段落，未保留“建议 2分”与“理由 1分”的左右对应。v2 只把同一份已核 docx_text 恢复成三张 Markdown 两列表，每张表有三行建议—理由配对。

## 本轮写入边界

本目录是本轮唯一写入目录。没有修改：

- 上一版 ../q19_exact_delta.json 或 ../q19_exact_delta.md；
- 冻结候选 ../controller_ready/candidates/BJ-2025-CY-ERMO-Q19.md；
- 共享父稿、共享题库、index、manifest、controller_ready；
- Q19 的 E0 题面、E3 参考答案、题号 19、9 分字段、学生层或邻题。

状态仍为 proposal_not_applied，不表示替换已经应用或合并。

## 来源与重建方式

- 来源 DOCX：../isolated_sources/细则_same_sha.docx
- DOCX SHA-256：73c36c3077dced724eb48b81aec7492e8e5ac59a7f72d7fb729d3581ea3fb5e8
- 外层表4（OOXML table index 3）右栏 E1 cell SHA-256：c514b32cf33567c4590e3e3fb13b8b7432614b8d56e5ffdeb0c5408cb3c1a284
- 927 字 docx_text 由既有 source_specific_delta.json 的已核字段直接复用；未作文字润色、纠错或 E3 回填。
- 源字面守卫：保留“利用利用”1次和“以上三个左右对应关系”3次。
- DOCX 内嵌 9×3 表的内容行按两列各自的非空段落从上到下同索引配对：建议1—理由1、建议2—理由2、建议3—理由3。不是按渲染后两列的最近 y 坐标猜配。

## 三类结构

1. ①公共法律服务：嵌套源行 0/1/2，派生可读页 p9–p10；
2. ②普法工作方面：嵌套源行 3/4/5，派生可读页 p10–p11；
3. ③依法治网方面：嵌套源行 6/7/8，派生可读页 p11。

每类均为两列：左列建议  2分，右列理由 1分；每类 3 个数据行。每张表后的“以上三个左右对应关系，答出任意一个‘建议 + 理由’，即可得3分”保留在表外。第三类表后继续保留末尾不能一一对应的降分提示原句。

完整的段落、嵌套源行、分页和 PDF point 坐标证据见 pairing_map.json；便于人工复核的配对表见 pairing_map.md。

## 冻结替换守卫

- 冻结候选 base SHA-256：04b54100407cd40b5d47f5d0fb5bfd75266a6a293c2bb1321fd9e4053d2df819
- old_exact SHA-256：8562d8c7833663fb7578181ecb7088b72853a4588befeb002e81da4a8e2a932f
- 当前 old_exact 命中次数：1；应用只能精确替换一次。
- v2 replacement SHA-256：7fcf8198b80d5bd86b8f8fba25bc57b99315e77e3eeeadca4400c172dbdd26f4
- 仅内存应用 v2 replacement 的候选暂定 SHA-256：05f11bab92963bbf1028c99570e73a933999eea0b8dc9a119ce563f62b3aedef
- 内存应用后 old_exact 命中次数：0。

应用前仍需核对 live candidate SHA、old_exact 唯一命中和独立复核回执；本目录不执行应用、合并或晋升。

## 文件

- structured_delta.json：结构化 replacement、9 个同序行配对、SHA、应用边界和 E0/E3/9分/学生层/邻题守卫；
- pairing_map.json：三页 p9–p11 的逐行文字片段与 PDF point 坐标；
- pairing_map.md：供人工复核的可读配对表和页坐标摘要；
- validation.json：机器验证结果和未应用状态。
