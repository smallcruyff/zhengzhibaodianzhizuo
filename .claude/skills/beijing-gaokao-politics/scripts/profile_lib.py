#!/usr/bin/env python3
"""书册配置读取：各通用工具共用。

每本书一份 profiles/<book_id>.json，只写静态的本册约定（样式名、栏目、编号、禁用词、渲染、发布等）；
每批会变的 SHA、工作头、计数仍在当前状态.json、审阅清单和同版身份.json。
profiles/_house.json（可选）是共享默认值，本册配置按键深合并覆盖它。

  from profile_lib import load_profile, detect_profile, frozen_guard
  prof = load_profile('bixiu3')            # 或传配置文件路径
  prof = detect_profile('/path/to/本批.docx')  # 按路径猜是哪本书，猜不到返回 None
"""
import json
from pathlib import Path

PROFILE_DIR = Path(__file__).resolve().parent / 'profiles'


def _merge(base, over):
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for k, v in over.items():
            out[k] = _merge(base[k], v) if k in base else v
        return out
    return over


def list_profiles():
    return sorted(p.stem for p in PROFILE_DIR.glob('*.json') if not p.stem.startswith('_'))


def load_profile(name_or_path):
    p = Path(name_or_path)
    if not p.suffix:
        p = PROFILE_DIR / f'{name_or_path}.json'
    prof = json.loads(p.read_text(encoding='utf-8'))
    house = PROFILE_DIR / '_house.json'
    if house.exists():
        prof = _merge(json.loads(house.read_text(encoding='utf-8')), prof)
    prof['_profile_path'] = str(p.resolve())
    return prof


def root(prof):
    return Path(prof['paths']['root'])


def resolve(prof, rel):
    """配置里的相对路径按项目根解析；绝对路径和 ~ 原样展开。"""
    if rel is None:
        return None
    q = Path(str(rel)).expanduser()
    return q if q.is_absolute() else root(prof) / q


def detect_profile(path):
    """按文件路径落在哪本书的工作区、审阅入口或历史目录里来判断书册。"""
    # 原路径与解析后的真实路径都比：书册目录可能已移出 iCloud、原位置只留符号链接（2026-09-24）
    p = Path(path).expanduser()
    cands = {str(p.absolute()), str(p.resolve())}
    for name in list_profiles():
        prof = load_profile(name)
        keys = [prof['paths'].get(k) for k in ('workspace', 'aux_workspace', 'review_entry', 'review_history')]
        for k in filter(None, keys):
            d = resolve(prof, k)
            dirs = {str(d), str(d.resolve())}
            if any(x in s for x in dirs for s in cands):
                return prof
    return None


def styles(prof, role):
    """某个语义角色对应的样式名列表（一律按 w:name，不按 styleId）。"""
    v = prof.get('styles', {}).get(role, [])
    return set(v if isinstance(v, list) else [v])


def frozen_guard(prof, action='写入'):
    """冻结册（如已送印的必修二）只允许只读；写操作调用此函数会直接退出。"""
    if prof.get('frozen'):
        raise SystemExit(f"{prof.get('title', prof.get('book_id'))} 已冻结，拒绝{action}：{prof.get('frozen_note', '')}")
