# CP-QIMO Q16 image3 定点修复回执

- 对应独立复核缺陷：`FIG-Q16-IMG3-LABEL-DUP`。
- 修复前：image3 条目同时描述 image2 的雕漆照片与 image3 的京绣照片，导致当前对象名错置。
- 修复后：`image3 为红底彩色刺绣纹样照片，图下标注“京绣”；原题表格文字另在题面转写中完整保留。`
- 同步修复：`build_candidate.py` 改为按图片文件保存独立转写，防止重建候选时回退；已重建候选并刷新 Q16、图文回执和自检哈希。

## 刷新后 SHA-256

- `candidates/BJ-2026-CP-QIMO-Q16.md`: `3eae218a503a1e8365dad4b55749a2e06bed203ef83b2ae16b2cb586a30c4b7d`
- `figure_transcription/figures.md`: `22d08befcceaa13761807d8b6d2f24fbae5a0ed7e50372d9815fab5e04f35737`
- `figure_transcription/figures.json`: `07c30ed895dfa963b55c6800b6370fbcdfb8bd3daa190ec88e40f281e30cd16c`
- `complete_candidate.json`: `2c1441e3438b3db860171945693ac9713c879ee8e3bc9841eefeebd0043f48b0`
- `self_check.json`: `50feccf2fd163e103d8f9b7a2747f9700bd8b612c03199e8dc2c5ab56f788245`

## 当前状态

`fixed_pending_independent_delta_review`。本回执不自行把原 `fail` 升级为 merge-ready。
