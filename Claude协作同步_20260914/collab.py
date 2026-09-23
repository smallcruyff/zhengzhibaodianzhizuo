#!/usr/bin/env python3
"""Local material publication and cooperative, fingerprint-checked handoff.

This does not edit manuscripts or enforce OS-level write protection.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from datetime import datetime, timezone
import uuid

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'Claude协作同步_20260914'

def now():
    return datetime.now(timezone.utc).isoformat()

def read_json(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def atomic_json(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.pending-', dir=p.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def signature(p):
    before = p.stat()
    digest = sha(p)
    after = p.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f'文件读取中发生变化，请重试：{p}')
    return {'sha256': digest, 'size': after.st_size, 'mtime_ns': after.st_mtime_ns}

@contextlib.contextmanager
def lock(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.mkdir()
    except FileExistsError:
        raise RuntimeError(f'已有协作操作正在执行，或上次异常留下锁。核实进程后处理：{p}')
    try:
        (p / 'owner.json').write_text(json.dumps({'pid': os.getpid(), 'time': now()}))
        yield
    finally:
        (p / 'owner.json').unlink()
        p.rmdir()

def resolve(value):
    p = Path(value)
    if not p.is_absolute():
        return ROOT / p
    for prefix in ['/Users/wanglifei/Desktop/gpt6', '/Users/wanglifei/Desktop/gpt和claude共同的小窝']:
        try:
            return ROOT / p.relative_to(prefix)
        except ValueError:
            pass
    return p

def display(p):
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)

def walk_files(base, rules=False):
    for folder, dirs, files in os.walk(base, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__' and not (Path(folder) / d).is_symlink())
        for name in sorted(files):
            p = Path(folder) / name
            if name == '.DS_Store' or name.startswith(('._', '~$')) or p.is_symlink():
                continue
            if rules and p.suffix.lower() in ('.zip', '.skill', '.pyc'):
                continue
            yield p

def sync():
    config = read_json(WORK / 'sources.json')
    manifest_path = WORK / '发布清单.json'
    with lock(WORK / '.sync-lock'):
        old = read_json(manifest_path).get('files', {}) if manifest_path.exists() else {}
        records = dict(old)
        seen, errors, changed = set(), [], []
        for group in config['groups']:
            srcroot = resolve(group['source'])
            if not srcroot.is_dir():
                errors.append(f'源目录不可访问：{srcroot}')
                continue
            for source in walk_files(srcroot, group.get('rules', False)):
                for target in group['targets']:
                    dest = ROOT / target / source.relative_to(srcroot)
                    key = display(dest)
                    seen.add(key)
                    try:
                        s = signature(source)
                        current = signature(dest) if dest.exists() else None
                        if current and current['sha256'] != s['sha256']:
                            previous = old.get(key)
                            if not previous or current['sha256'] != previous['sha256']:
                                raise RuntimeError('目标未登记或已被修改，保留原状')
                        if not current or current['sha256'] != s['sha256']:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            fd, tmp = tempfile.mkstemp(prefix='.copy-', dir=dest.parent)
                            os.close(fd)
                            try:
                                shutil.copy2(source, tmp)
                                if sha(tmp) != s['sha256'] or signature(source)['sha256'] != s['sha256']:
                                    raise RuntimeError('复制期间源文件变化，未发布')
                                if dest.exists():
                                    if sha(dest) != current['sha256']:
                                        raise RuntimeError('目标在复制期间变化，未覆盖')
                                    archive = WORK / '发布历史' / datetime.now().strftime('%Y%m%d_%H%M%S') / key
                                    archive.parent.mkdir(parents=True, exist_ok=True)
                                    shutil.copy2(dest, archive)
                                os.replace(tmp, dest)
                            finally:
                                if os.path.exists(tmp):
                                    os.unlink(tmp)
                            changed.append(key)
                        records[key] = {'source': str(source), 'sha256': s['sha256'], 'size': s['size'], 'source_mtime_ns': s['mtime_ns']}
                    except Exception as exc:
                        errors.append(f'{key}：{exc}')
        stale = sorted(set(old) - seen)
        result = {'updated_at': now(), 'files': records, 'changed': changed, 'errors': errors, 'source_missing_or_removed': stale}
        atomic_json(manifest_path, result)
        atomic_json(WORK / '最近同步结果.json', {k: v for k, v in result.items() if k != 'files'} | {'tracked_files': len(records)})
        if errors or stale:
            raise RuntimeError(f'同步未完全通过：{len(errors)}错误，{len(stale)}源缺失。详见最近同步结果.json')
        return {'tracked_files': len(records), 'changed_files': len(changed), 'errors': 0}

def book_config(name):
    books = read_json(WORK / 'books.json')['books']
    if name not in books:
        raise RuntimeError(f'未登记册别：{name}')
    return books[name]

def snapshot(name):
    cfg = book_config(name)
    if not cfg.get('review_manifest'):
        return {'book': name, 'ready': False, 'reason': '本册真实续修稿尚未核定；不得从历史包猜最新版', 'entry': cfg['skill_entry']}
    path = ROOT / cfg['review_manifest']
    m = read_json(path)
    files = {}
    for label, field in [('docx', m.get('docx_source') or m.get('source_docx')), ('pdf', m.get('pdf_source') or m.get('source_pdf'))]:
        if not field:
            raise RuntimeError(f'{name}审阅清单缺少{label}来源')
        p = resolve(field)
        actual = signature(p)
        if actual['sha256'] != m.get(label + '_sha256'):
            raise RuntimeError(f'{name} {label}与登记指纹不符，需核实最新实物')
        files[label] = {'path': display(p), 'sha256': actual['sha256'], 'size': actual['size']}
    checks = {display(path): sha(path)}
    for item in cfg.get('progress_files', []):
        p = resolve(item)
        if not p.is_file():
            raise RuntimeError(f'进度入口不可访问：{p}')
        checks[display(p)] = signature(p)['sha256']
    # A user may have edited the review copy. Detect this rather than silently replacing it.
    user_changes = []
    review_dir = path.parent
    for label, suffix in [('docx', '.docx'), ('pdf', '.pdf')]:
        candidates = [resolve(m[label])] if m.get(label) else [review_dir / x for x in m.get('tracked_files', []) if x.endswith(suffix)]
        for p in candidates:
            if p.is_file() and sha(p) != files[label]['sha256']:
                user_changes.append(display(p))
    result = {'book': name, 'ready': not user_changes, 'revision': m.get('revision') or m.get('latest_batch'), 'central_confirmed_revision': m.get('central_confirmed_revision'), 'status': m.get('status'), 'pdf_pages': m.get('pdf_pages'), 'files': files, 'progress_fingerprints': checks, 'user_modified_review_copies': user_changes, 'progress_files': cfg.get('progress_files', []), 'note': 'revision为当前审阅版本；未渲染或更新中的候选须另读progress_files，不自动视为终稿'}
    # Recheck the manifest so a concurrently published file pair is not mixed.
    if sha(path) != checks[display(path)]:
        raise RuntimeError('核验期间审阅清单变化，请重试')
    return result

def state_path(name):
    return ROOT / book_config(name)['workspace'] / '协作' / '接管.json'

def load_state(name):
    p = state_path(name)
    return read_json(p) if p.exists() else {'owner': None, 'phase': 'unclaimed', 'generation': 0}

def assert_actor(state, actor):
    if state['owner'] != actor or state['phase'] != 'owned':
        raise RuntimeError(f'当前负责人为{state.get("owner")}，状态{state.get("phase")}；未完成接管不可写共享稿')

def checkpoint(name, actor, note):
    p = state_path(name)
    with lock(p.parent / '.handoff-lock'):
        state = load_state(name)
        assert_actor(state, actor)
        text = Path(note).read_text(encoding='utf-8').strip()
        if not text:
            raise RuntimeError('交接说明不能为空')
        snap = snapshot(name)
        if not snap['ready']:
            raise RuntimeError('当前稿或用户批注身份待核，不能交接')
        receipt = p.parent / '交接历史' / (datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8] + '.json')
        data = {'saved_at': now(), 'owner': actor, 'note': text, 'snapshot': snap}
        atomic_json(receipt, data)
        state.update(checkpoint=display(receipt), checkpoint_sha256=sha(receipt), updated_at=now(), generation=state['generation'] + 1)
        atomic_json(p, state)
        return state

def offer(name, actor, recipient, tasks_stopped):
    if not tasks_stopped:
        raise RuntimeError('交出前须核实该册后台写稿已停止，并提供--tasks-stopped；本程序不会停止其他软件任务')
    p = state_path(name)
    with lock(p.parent / '.handoff-lock'):
        state = load_state(name)
        assert_actor(state, actor)
        receipt = resolve(state.get('checkpoint', '不存在的交接'))
        if not receipt.is_file() or sha(receipt) != state.get('checkpoint_sha256'):
            raise RuntimeError('缺少有效checkpoint')
        if read_json(receipt)['snapshot'] != snapshot(name):
            raise RuntimeError('保存checkpoint后稿件或进度变化，请重新保存交接')
        if recipient not in ['codex', 'claude']:
            raise RuntimeError('接收平台应为codex或claude')
        state.update(phase='offered', offered_to=recipient, updated_at=now(), generation=state['generation'] + 1)
        atomic_json(p, state)
        return state

def accept(name, actor):
    p = state_path(name)
    with lock(p.parent / '.handoff-lock'):
        state = load_state(name)
        if state['phase'] != 'offered' or actor.split(':', 1)[0] != state.get('offered_to'):
            raise RuntimeError('没有交给本平台的有效交接')
        receipt = resolve(state['checkpoint'])
        if sha(receipt) != state['checkpoint_sha256'] or read_json(receipt)['snapshot'] != snapshot(name):
            raise RuntimeError('交出后稿件/进度/交接说明发生变化，不接管过期快照')
        previous = state['owner']
        state.update(owner=actor, phase='owned', previous_owner=previous, updated_at=now(), generation=state['generation'] + 1)
        state.pop('offered_to', None)
        atomic_json(p, state)
        return state

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['sync', 'status', 'check', 'checkpoint', 'offer', 'accept'])
    parser.add_argument('--book')
    parser.add_argument('--actor', help='例如claude:实际会话ID；不得冒用其他任务身份')
    parser.add_argument('--note')
    parser.add_argument('--to', choices=['codex', 'claude'])
    parser.add_argument('--tasks-stopped', action='store_true')
    args = parser.parse_args()
    if args.action == 'sync':
        result = sync()
    elif args.action == 'status':
        names = [args.book] if args.book else read_json(WORK / 'books.json')['books']
        result = [{'snapshot': snapshot(n), 'handoff': load_state(n)} for n in names]
    else:
        if not args.book or not args.actor:
            parser.error('需要--book和--actor')
        if args.action == 'check':
            assert_actor(load_state(args.book), args.actor)
            result = snapshot(args.book)
            if not result['ready']:
                raise RuntimeError('稿件身份未通过')
        elif args.action == 'checkpoint':
            if not args.note:
                parser.error('需要--note说明文件')
            result = checkpoint(args.book, args.actor, args.note)
        elif args.action == 'offer':
            result = offer(args.book, args.actor, args.to, args.tasks_stopped)
        else:
            result = accept(args.book, args.actor)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'未完成：{exc}', file=sys.stderr)
        sys.exit(1)
