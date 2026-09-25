# 核心输入快照（major⑤修复）

对抗审查指出 v1 的核心输入（`classified_prod.jsonl`、`units.jsonl`）只存在于另一次会话的
`/private/tmp/.../scratchpad/completeness/classifier/` 下，tmp 被清理或题库更新后就无法复现，
也无法判断结果是否已失效。本目录把生成 v2 归属表实际用到的全部核心输入原样快照到交付目录，
并记录SHA-256（见 `MANIFEST.sha256`）与题库/矩阵签名，供以后重跑前先校验"输入有没有变"。

## 快照清单与来源路径（生成本版 attribution.csv 时的真实路径）

| 文件 | 来源 | 用途 |
|---|---|---|
| `classified_prod.jsonl` | `完整性调查_20260924/原型脚本/classify.py` 的生产输出 | 九模块三态(IN/MAYBE/OUT)与证据ev |
| `units.jsonl` | 同上分类器的题面/细则全文缓存 | content_fingerprint、stem_len/rubric_len |
| `classify.py` | 分类器源码本身（同一份代码在 `完整性调查_20260924/原型脚本/classify.py` 也有存档，本身不在tmp、不会丢） | 记录判定规则版本，供以后核对分类逻辑是否变过 |
| `rubric_links.csv` | 题库 `indexes/rubric_links.csv` | 逐题E1/E3证据判定（本版核心修复点） |
| `exams.csv` | 题库 `indexes/exams.csv` | 卷身份、学年、notes里的逐题细则范围 |
| `assembly_blocks.csv` | 题库 `indexes/assembly_blocks.csv` | 只在汇编中出现的卷候选行生成 |
| `matrix.csv` | `完整性调查_20260924/matrix.csv`（coverage.py产物） | 各书S/F/M收录层级、题级dup_of/dup_covered_by |
| `bank_duplicate_exams.csv` | `完整性调查_20260924/bank_duplicate_exams.csv`（coverage.py产物） | 重复登记卷候选 |

## 重跑前校验

```bash
cd 归属表_v1/inputs_snapshot
shasum -a 256 -c MANIFEST.sha256
```
全部 OK 才说明本次快照与当时生成 attribution.csv 用的输入完全一致；任何一条 FAILED 都说明题库/分类器/矩阵已经更新，
attribution.csv 需要重新生成，不能直接复用旧产物当"最新状态"。

## 生成命令（可追溯，供以后重跑分类器时对照，本身不在本轮重跑）

`classified_prod.jsonl`/`units.jsonl` 由 `classify.py` 生成，命令形如：
```bash
cd 完整性调查_20260924/原型脚本/classifier
/usr/bin/python3 classify.py --lex seed+head --out classified_prod.jsonl
```
（依赖同目录 `lexicon.py`、`truth.py`；`--with-e` 未启用，即生产口径不强制把已收录模块直接判IN，
由 build_attribution_v2.py 自己按 matrix.csv 的 COLLECTED 状态叠加，两处不重复计入。）

`rubric_links.csv`/`exams.csv`/`assembly_blocks.csv` 由题库自身的抽取/核验流程维护，不属于本次归属表任务的产物，
本目录只快照当时读到的版本，不代表题库当前最新版本。

`matrix.csv`/`bank_duplicate_exams.csv` 由 `完整性调查_20260924/原型脚本/coverage.py`（或同名脚本）生成，
同样只快照当时版本。
