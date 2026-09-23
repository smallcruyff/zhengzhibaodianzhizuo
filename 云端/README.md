# 本地 ⇄ 云端 使用方法

本地仓库位置：`/Users/wanglifei/GaokaoPolitics/宝典云端仓库`（不在桌面，避免 iCloud 同步 1G+ 的 git 数据）。

## 去云端之前（本地）

```
python3 Claude协作同步_20260914/云端同步.py export
python3 Claude协作同步_20260914/云端同步.py push
```

export 按清单把规则、原材料、必修三最新稿与进度复制进仓库并提交；push 推到 GitHub 私有仓库。

## 在云端

在 claude.ai/code 或桌面 Code 标签页选这个仓库、选“宝典云端”环境，新建会话。云端会话会读仓库里的 CLAUDE.md，产出只写 `协作/候选/Claude云端/`。

## 回到本地

```
python3 Claude协作同步_20260914/云端同步.py pull
```

把云端各分支的新候选取回本地同一路径；本地已有文件不覆盖，冲突列出来交人工判断。

## 未上云的内容

- 必修二全部、历史批次稿、协作/候选（8.8G）、外部证据副本（8.5G）、DeepSeek 题库资料库（6.9G）。
- 超过 GitHub 100MB 单文件上限的文件，见 `云端/同步清单.json` 的 `local_only_too_big`。
