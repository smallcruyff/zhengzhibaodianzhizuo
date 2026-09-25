#!/usr/bin/env python3
"""verify_live_inputs_v3.py —— major⑤修复：重跑前校验"线上题库文件是否已变"，不是自己对自己。

v2 的重跑说明只写了 `cd inputs_snapshot && shasum -a 256 -c MANIFEST.sha256`——这只能证明快照文件本身
没有被后来的操作篡改，比不出题库/矩阵是否已经更新（快照永远等于快照自己，逐字面意义上"每次都OK"，
不是有效的"输入未变"校验）。本脚本改为对照本表实际依赖的线上文件，逐个算当前SHA-256并与
inputs_snapshot/MANIFEST.sha256登记的快照哈希比较；同时补记questions.csv（题库最上游源文件）当前哈希，
即使本表脚本不直接读它，也按 确认意见_v2.json major⑤ 的要求留痕，供人工判断题库是否已整体重建。

用法：python3 verify_live_inputs_v3.py [--bank-dir <题库根目录>] [--review-dir <完整性调查目录>] \
      [--snapshot-dir inputs_snapshot]
退出码：0=全部一致（可直接信任inputs_snapshot离线重放）；1=至少一项不一致（需要用--bank-dir/--review-dir
      指向线上路径重新生成exam_identity.json/attribution.csv，而不是只信旧快照）。
"""
import sys
sys.dont_write_bytecode = True
import argparse, hashlib
from pathlib import Path

BANK_DEFAULT = '/Users/wanglifei/Desktop/gpt和claude共同的小窝/DeepSeek_政治题库资料库_20260918'
REVIEW_DEFAULT = '/Users/wanglifei/Desktop/gpt和claude共同的小窝/后勤管理/20260923_脚本化与跨书工具/完整性调查_20260924'


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bank-dir', default=BANK_DEFAULT)
    ap.add_argument('--review-dir', default=REVIEW_DEFAULT)
    ap.add_argument('--snapshot-dir', default='inputs_snapshot')
    a = ap.parse_args()
    bank = Path(a.bank_dir)
    review = Path(a.review_dir)
    snap = Path(a.snapshot_dir)

    manifest = {}
    for line in (snap / 'MANIFEST.sha256').read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        h, name = line.split(None, 1)
        manifest[name.strip()] = h

    # 本表脚本实际直接读取的线上文件（有"是否已变"意义的5个，classify.py/classified_prod.jsonl/
    # units.jsonl 没有独立于快照之外的"线上路径"，本脚本不重复校验那3个，只能靠人工确认分类器是否重跑过）
    live_checks = [
        ('rubric_links.csv', bank / 'indexes/rubric_links.csv'),
        ('exams.csv', bank / 'indexes/exams.csv'),
        ('assembly_blocks.csv', bank / 'indexes/assembly_blocks.csv'),
        ('matrix.csv', review / 'matrix.csv'),
        ('bank_duplicate_exams.csv', review / 'bank_duplicate_exams.csv'),
    ]
    ok = True
    for name, path in live_checks:
        if not path.exists():
            print(f'MISSING  {name}  (线上路径不存在: {path})')
            ok = False
            continue
        live_hash = sha256(path)
        snap_hash = manifest.get(name)
        if snap_hash is None:
            print(f'NO_MANIFEST_ENTRY  {name}')
            ok = False
        elif live_hash == snap_hash:
            print(f'OK       {name}  (线上与快照一致)')
        else:
            print(f'CHANGED  {name}  快照={snap_hash[:16]}…  线上={live_hash[:16]}…  '
                  f'——题库/矩阵已更新，attribution.csv需要用 --bank-dir/--inputs-dir 指向线上重新生成，'
                  f'不能只信旧快照')
            ok = False

    # questions.csv：本表脚本不直接读它，但按major⑤要求补记哈希留痕
    qcsv = bank / 'indexes/questions.csv'
    if qcsv.exists():
        print(f'INFO     questions.csv 当前SHA-256={sha256(qcsv)}（题库最上游源文件，本表脚本不直接读取，'
              f'仅留痕供人工核对题库是否整体重建；行数供参考）')
    else:
        print('INFO     questions.csv 未找到，跳过留痕')

    print()
    print('全部一致，可信任 inputs_snapshot 离线重放当前 attribution.csv/exam_identity.json' if ok
          else '存在不一致，重跑前必须先用线上路径重新生成，不能假设旧快照仍然有效')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
