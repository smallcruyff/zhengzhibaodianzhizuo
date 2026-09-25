#!/usr/bin/env python3
"""本地小窝 ⇄ 云端仓库（GitHub 私有仓库）同步。

本地仍是唯一真源。云端仓库只放“能在云端正常工作”的精简集：
规则/Skill、协作入口、全部原材料、必修三最新稿与进度、共享题库。
云端会话只写候选，回收时只新增文件、不覆盖本地任何已有文件。

用法：
  python3 Claude协作同步_20260914/云端同步.py export   # 本地 → 云端仓库（复制＋提交）
  python3 Claude协作同步_20260914/云端同步.py push     # 推送到 GitHub
  python3 Claude协作同步_20260914/云端同步.py pull     # 取回云端候选到本地
  python3 Claude协作同步_20260914/云端同步.py status
"""
import hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
REPO = Path('/Users/wanglifei/GaokaoPolitics/宝典云端仓库')
BOOK3 = '必修三_最新Skill修订_20260913'
BOOK3_STATE = Path('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/必修三续作_20260908/当前状态.json')
CLOUD_CANDIDATES = f'{BOOK3}/协作/候选/Claude云端'
GITHUB_LIMIT = 95 * 1024 * 1024  # GitHub 单文件上限 100MB，留余量

# 整目录纳入（相对本地项目根）
TREES = [
    '.claude/skills', '.claude/agents', '.claude/commands',
    '00_共同资料/规则', '00_共同资料/原材料',
    '00_必修三最新审查稿',
    f'{BOOK3}/主代理修订',
    f'{BOOK3}/协作/交接历史', f'{BOOK3}/协作/题源覆盖台账',
    '共享题库',
    # 2026-09-24 流程优化线（规格、回执、测试脚本、归属表与各书清单、Codex 分析；不含 195MB 中间产物）
    '后勤管理/20260923_脚本化与跨书工具/书侧工具_20260924',
    '后勤管理/20260923_脚本化与跨书工具/交接_20260924',
    '后勤管理/20260923_脚本化与跨书工具/完整性调查_20260924',
    '后勤管理/20260923_脚本化与跨书工具/Codex记录分析_20260924',
    '后勤管理/20260923_脚本化与跨书工具/证据',
]
# 单文件纳入
FILES = [
    '00_协作入口.md', '00_目录导航.md', 'AGENTS.md',
    f'{BOOK3}/本轮修订与审查说明.md', f'{BOOK3}/00_新任务交接.md', f'{BOOK3}/网页审核回传.md',
    f'{BOOK3}/协作/接管.json',
    'Claude协作同步_20260914/collab.py', 'Claude协作同步_20260914/sync.py',
    'Claude协作同步_20260914/books.json', 'Claude协作同步_20260914/sources.json',
    'Claude协作同步_20260914/云端同步.py',
    # 2026-09-24 流程优化线：给云端做工具用的文档
    '后勤管理/20260923_脚本化与跨书工具/给Codex的提速指令_20260924.md',
    '后勤管理/20260923_脚本化与跨书工具/给Codex的下一步指令_20260924晚.md',
    '后勤管理/20260923_脚本化与跨书工具/00_结论与待裁定.md',
    'DeepSeek_政治题库资料库_20260918/README_FOR_AI.md',
    'DeepSeek_政治题库资料库_20260918/PROGRESS.md',
]
# 2026-09-24：按后缀过滤的目录（题库精简版：只要逐题文字、索引、脚本，不带原件与页图）
FILTERED_TREES = [
    ('DeepSeek_政治题库资料库_20260918/questions', {'.md', '.json'}),
    ('DeepSeek_政治题库资料库_20260918/questions_reused', {'.md', '.json'}),
    ('DeepSeek_政治题库资料库_20260918/indexes', None),
    ('DeepSeek_政治题库资料库_20260918/scripts', {'.py', '.json', '.md'}),
]
FILTER_SKIP_DIRS = {'sources', 'assets', 'tmp'}
# 2026-09-24：项目外的其余六本书工作头（用户 09-24 确认），放进仓库 其他书工作头/
EXTERNAL = [
    ('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/必修四哲学续作_20260908/交付/哲学宝典_修订稿_R10_漏节点与附录补全及触发词修正版_20260908.docx', '其他书工作头/哲学'),
    ('/Users/wanglifei/Desktop/2026模拟题/文化_v6.9续作_20260908/工作稿/2026北京高考政治文化宝典_v6.30_校订稿_20260908.docx', '其他书工作头/文化'),
    ('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/选必一_v11.13续作_20260908/work/选必一_当代国际政治与经济_主客观题宝典_v11.14_修订工作稿_20260908.docx', '其他书工作头/选必一'),
    ('/Users/wanglifei/Desktop/2026模拟题/选必二_v15.0续作_20260908/工作稿/选必二法律与生活宝典_v15.0_出版校订稿_20260908_r22.docx', '其他书工作头/选必二'),
    ('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/选必三思维_v6.4续作_20260908/选必三思维宝典_v6.20_丰台补题分页修订工作稿_20260908.docx', '其他书工作头/思维'),
    ('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/推理_v7.31续作_20260908/输出/选必三_逻辑与思维_推理宝典_v7.50_主观原图与评分替代条件修订工作稿_20260908.docx', '其他书工作头/推理'),
]
SKIP_NAMES = {'.DS_Store', '__pycache__', 'Thumbs.db'}


def skip(p: Path) -> bool:
    return p.name in SKIP_NAMES or p.name.startswith('~$') or p.name.startswith('._')


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def git(*args, check=True, capture=False):
    return subprocess.run(['git', '-C', str(REPO), *args], check=check, text=True,
                          capture_output=capture)


def copy_if_changed(src: Path, dst: Path, stats):
    if dst.exists() and dst.stat().st_size == src.stat().st_size and \
            int(dst.stat().st_mtime) == int(src.stat().st_mtime):
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not os.access(dst, os.W_OK):   # 仓库里的只读副本（Skill 文件 r--r--r--）先改可写再覆盖
        os.chmod(dst, dst.stat().st_mode | 0o200)
    shutil.copy2(src, dst)
    stats['copied'] += 1


def wanted_files():
    """(本地源, 仓库相对路径) 列表；工作头 docx/pdf 由当前状态.json 决定。"""
    out = []
    for rel in TREES:
        root = PROJECT / rel
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
            dirnames[:] = [d for d in dirnames if d not in SKIP_NAMES]
            for fn in filenames:
                p = Path(dirpath) / fn
                if not skip(p):
                    out.append((p, p.relative_to(PROJECT).as_posix()))
    for rel in FILES:
        if (PROJECT / rel).is_file():
            out.append((PROJECT / rel, rel))
    for rel, exts in FILTERED_TREES:
        root = PROJECT / rel
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
            dirnames[:] = [d for d in dirnames if d not in SKIP_NAMES and d not in FILTER_SKIP_DIRS]
            for fn in filenames:
                p = Path(dirpath) / fn
                if not skip(p) and (exts is None or p.suffix.lower() in exts):
                    out.append((p, p.relative_to(PROJECT).as_posix()))
    for src, dst_dir in EXTERNAL:
        p = Path(src)
        if p.is_file():
            out.append((p, f'{dst_dir}/{p.name}'))
    state = json.loads(BOOK3_STATE.read_text(encoding='utf-8'))
    head = Path(state['working_head'])
    for p in (head, head.with_suffix('.pdf')):
        if p.is_file():
            out.append((p, p.relative_to(PROJECT).as_posix()))
    out.append((BOOK3_STATE, '云端/必修三当前状态.json'))
    return out, state


def cmd_export():
    if not (REPO / '.git').exists():
        sys.exit(f'云端仓库不存在：{REPO}（先按 云端/README.md 初始化）')
    stats = {'copied': 0}
    files, state = wanted_files()
    kept, too_big = set(), []
    for src, rel in files:
        if src.stat().st_size > GITHUB_LIMIT:
            # 替代版由本地 LibreOffice（中文 fontconfig）转成 PDF 后手工放入，文本已核可读
            sub = f'云端/大文件PDF版/{rel}.pdf'
            too_big.append({'path': rel, 'bytes': src.stat().st_size,
                            'cloud_substitute': sub if (REPO / sub).exists() else None})
            continue
        copy_if_changed(src, REPO / rel, stats)
        kept.add(rel)
    # 删除仓库里已不在清单内的镜像文件（云端/、候选、仓库自身文件除外）
    removed = 0
    protected = ('.git/', '云端/', CLOUD_CANDIDATES + '/')
    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [d for d in dirnames if d != '.git']
        for fn in filenames:
            p = Path(dirpath) / fn
            rel = p.relative_to(REPO).as_posix()
            if rel in kept or rel.startswith(protected) or '/' not in rel and rel in \
                    {'CLAUDE.md', '.gitattributes', '.gitignore'}:
                continue
            p.unlink(); removed += 1
    head_rel = Path(state['working_head']).relative_to(PROJECT).as_posix()
    manifest = {
        'exported_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'local_project': str(PROJECT),
        'book3_working_head': head_rel,
        'book3_working_head_sha256': sha256(REPO / head_rel) if (REPO / head_rel).exists() else None,
        'book3_owner': json.loads((PROJECT / f'{BOOK3}/协作/接管.json').read_text(encoding='utf-8')).get('owner'),
        'files': len(kept),
        'local_only_too_big': too_big,
    }
    (REPO / '云端').mkdir(exist_ok=True)
    (REPO / '云端/同步清单.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    git('add', '-A')
    if git('diff', '--cached', '--quiet', check=False).returncode:
        git('commit', '-q', '-m', f'本地导出 {manifest["exported_at"]}：必修三工作头 {head_rel.split("/")[-1]}')
    print(json.dumps({**manifest, 'copied': stats['copied'], 'removed': removed}, ensure_ascii=False, indent=1))


def cmd_push():
    git('push', '-u', 'origin', 'main')


def cmd_pull():
    """把云端各分支上 协作/候选/Claude云端/ 下的新文件取回本地；已存在的本地文件一律不覆盖。"""
    git('fetch', '--all', '--prune')
    branches = git('for-each-ref', '--format=%(refname:short)', 'refs/remotes/origin',
                   capture=True).stdout.split()
    got, conflicts = [], []
    for br in branches:
        if br.endswith('/HEAD'):
            continue
        ls = git('ls-tree', '-r', '--name-only', br, '--', CLOUD_CANDIDATES,
                 capture=True, check=False).stdout.splitlines()
        for rel in ls:
            rel = rel.strip('"')
            dst = PROJECT / rel
            blob = subprocess.run(['git', '-C', str(REPO), 'show', f'{br}:{rel}'],
                                  capture_output=True, check=True).stdout
            if dst.exists():
                if dst.read_bytes() != blob:
                    conflicts.append({'branch': br, 'path': rel})
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(blob)
            got.append({'branch': br, 'path': rel})
    print(json.dumps({'new_files': got, 'conflicts_not_overwritten': conflicts}, ensure_ascii=False, indent=1))


def cmd_status():
    print(git('status', '-sb', capture=True).stdout)
    print(git('log', '--oneline', '-5', capture=True, check=False).stdout)
    m = REPO / '云端/同步清单.json'
    if m.exists():
        print(m.read_text(encoding='utf-8'))


if __name__ == '__main__':
    {'export': cmd_export, 'push': cmd_push, 'pull': cmd_pull, 'status': cmd_status}.get(
        sys.argv[1] if len(sys.argv) > 1 else '', lambda: sys.exit(__doc__))()
