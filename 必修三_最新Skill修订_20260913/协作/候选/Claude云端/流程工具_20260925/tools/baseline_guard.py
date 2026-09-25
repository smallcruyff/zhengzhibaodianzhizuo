#!/usr/bin/env python3
"""真实输入未变证明：记录/比对书稿、审阅入口、题库、Skill、原材料、协作登记的 SHA/mtime/size。

  python3 baseline_guard.py snap  --out base.json      # 记录
  python3 baseline_guard.py check --base base.json     # 比对；有变化退出 1
只读；输出只写 --out 指定位置（应在系统临时目录或候选目录 构建/ 下）。
"""
import sys
sys.dont_write_bytecode = True
import hashlib, json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]   # 仓库根
SETS = {
    'book3': ['必修三_最新Skill修订_20260913'],
    'review': ['00_必修三最新审查稿'],
    'other_books': ['其他书工作头'],
    'bank': ['DeepSeek_政治题库资料库_20260918', '共享题库'],
    'skill': ['.claude/skills'],
    'raw': ['00_共同资料'],
    'cloud': ['云端'],
    'logistics': ['后勤管理', 'Claude协作同步_20260914'],
}
SKIP_PREFIX = '必修三_最新Skill修订_20260913/协作/候选/Claude云端/'
HASH_LIMIT = 64 << 20  # 超过 64MB 的文件只记 size+mtime


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def snap():
    out = {}
    for tag, dirs in SETS.items():
        for d in dirs:
            base = ROOT / d
            if not base.exists():
                continue
            for p in sorted(base.rglob('*')):
                if not p.is_file() or '__pycache__' in p.parts:
                    continue
                rel = p.relative_to(ROOT).as_posix()
                if rel.startswith(SKIP_PREFIX):
                    continue
                st = p.stat()
                out[rel] = {'size': st.st_size, 'mtime': st.st_mtime_ns,
                            'sha256': sha(p) if st.st_size <= HASH_LIMIT else None}
    return out


def main():
    if len(sys.argv) < 4 or sys.argv[1] not in ('snap', 'check'):
        print(__doc__)
        return 2
    if sys.argv[1] == 'snap':
        s = snap()
        Path(sys.argv[3]).write_text(json.dumps({'root': str(ROOT), 'files': s}, ensure_ascii=False), encoding='utf-8')
        print(f'已记录 {len(s)} 个文件')
        return 0
    base = json.loads(Path(sys.argv[3]).read_text(encoding='utf-8'))['files']
    now = snap()
    changed = [k for k in base if k in now and base[k] != now[k]]
    removed = [k for k in base if k not in now]
    added = [k for k in now if k not in base]
    pyc = [str(p) for p in (ROOT / '.claude/skills').rglob('__pycache__')]
    print(json.dumps({'files': len(base), 'changed': changed[:50], 'removed': removed[:50],
                      'added': added[:50], 'skill_pycache': pyc}, ensure_ascii=False, indent=1))
    return 1 if (changed or removed or added or pyc) else 0


if __name__ == '__main__':
    sys.exit(main())
