#!/usr/bin/env python3
"""publish_review.py —— 把已通过技术验收的候选 DOCX/PDF 发布到本册固定审阅入口。

用途：
    合并 publish_b49/50/51/52.py、promote_b52.py、必修二 publish230.py、R45 publish_batch.py 这些
    每批复制一次的一次性脚本，改成按 `--profile` 读取书册配置（`paths.*`、`publish.*`、`naming.*`、
    `handoff.*`）运行的通用工具。判定“这批能不能发”只看验收 JSON、接管.json、审阅入口现状与中央状态，
    脚本不做任何教学判断。

用法：
    publish_review.py --profile bixiu3 --batch 53 \
        --docx 候选/构建/xxx.docx --pdf 候选/构建/xxx.pdf \
        --acceptance 构建/最终主代理技术验收.json --actor claude:会话ID \
        [--note 本轮修订与审查说明.md] [--label 说明] [--health] [--apply] [--report out.json]

    默认（不带 --apply）是 dry-run：只打印完整计划与全部门的结果，不写任何文件；报告只能写到
    系统临时目录或 `.../协作/候选/<谁>/<批次>/{构建,发布准备}/` 之下（见 guard_write / 本文件
    `_confine_receipt`）。只有全部门通过，`--apply` 才会真正写审阅入口、工作区根与中央状态。

读写承诺：
    - dry-run 不写任何文件（`--report` 除外，且 `--report` 路径本身要过 guard_write）。
    - `--apply` 事务式写：先把中央状态、审阅清单、先看这里备份到候选目录 `发布准备/状态备份/<时间戳>/`，
      再按顺序：归档审阅入口现有登记文件 → 复制候选到工作区根 → 复制到审阅入口 → 写新清单 →
      更新先看这里 → 更新中央状态 → 写晋升回执。任一步失败，用备份把已改的文件全部还原，
      不留半成品，退出码 2。
    - 所有写入目标（工作区根、审阅入口、中央状态所在目录、归档目录、`发布准备/`）都先用
      `os.path.realpath` 解析并核对落在配置声明的目录之内，防符号链接逃逸。
    - 冻结册（`profile.frozen`）任何模式下只要看到 `--apply` 就立即拒绝退出 3；dry-run 允许跑，
      但会在门结果里明确写“已冻结，不允许发布”。
    - 本工具不修改 batch_health.py / docx_lib.py / profile_lib.py / profiles/ 下任何文件，不运行
      collab.py，不启动子代理。

退出码：
    0 — 全部门通过（dry-run：可以 --apply；--apply：已成功发布并复核）。
    1 — 仅在 `--health` 探测到写后/候选新增 FAIL 且验收 JSON 未显式接受时，作为“待处理”提示
        （不中止，此时工具仍按门规则决定能否 --apply）。本工具其余场景不用 1，见下。
    2 — 任一门 FAIL（父稿/清单/验收/批次号/写权不符等）：dry-run 报告失败但不算“程序错误”，
        `--apply` 时中止且不留输出（若已过备份点则先回滚）；输入/配置解析错误同样用 2。
    3 — 冻结册配置下的写模式；或写入目标解析不落在配置声明的位置内（守卫/符号链接逃逸）。
    4 — 第五轮新增：`--apply` 事务中途失败，且随后的回滚本身也失败（回滚过程再次抛错，例如磁盘满、
        权限变化）：工具已尽力执行完剩余各步回滚（每一步各自 try，一步失败不影响其余步骤继续），
        但仍有文件/目录未能恢复到发布前状态。stderr 与 `--report`（若给出）都会写“回滚不完整，
        需要人工核查”并逐项列出未恢复的路径与原因；不会再落进“输入或配置错误”的通用提示，避免
        主代理误判为“发布尚未开始写入”。

读取的配置字段（书册 `profiles/<book_id>.json`，均可缺省，缺省值见下与代码里的 `_DEFAULTS`）：
    paths.root / paths.workspace / paths.aux_workspace / paths.review_entry / paths.review_history /
    paths.review_manifest / paths.central_state / paths.handoff / paths.build_subdir
    publish.entry / publish.note_file（缺省 "先看这里.md"）/ publish.manifest（缺省 ".review-manifest.json"）/
    publish.archive_to（模板，缺省 "{review_history}/第{prev}批_原样审阅_{stamp}"）/
    publish.preserve（缺省 [".DS_Store", "~$*"]）/ publish.central_state_backup（模板，
    缺省 "{candidate}/发布准备/状态备份/{stamp}"）/ publish.central_state_fields（字段名映射，见 _DEFAULTS）
    naming.docx_stem（模板，必须能用 {n}/{rev}/{label}/{date} 等占位符渲染；本册没配就报
    profile_fields_needed，工具本身仍可退化为直接使用候选文件名，见 _stem_name）
    handoff.owner_file（缺省 "协作/接管.json"）
    render.identity_file（缺省 "同版身份.json"，用于同版身份交叉核对，找不到只 WARN）

新字段（本工具引入、当前书册配置未必写）一律给了代码默认值，见 `_DEFAULTS`，并在 `--report`/
回执里列进 `profile_fields_needed`，由主代理决定要不要登记进 profiles/。
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import batch_health as bh  # noqa: E402
import docx_lib as dl  # noqa: E402
from profile_lib import load_profile, resolve  # noqa: E402

TOOL_NAME = 'publish_review'
TOOL_VERSION = '1.0.0'

_DEFAULTS = {
    'publish.note_file': '先看这里.md',
    'publish.manifest': '.review-manifest.json',
    'publish.archive_to': '{review_history}/第{prev}批_原样审阅_{stamp}',
    'publish.preserve': ['.DS_Store', '~$*'],
    'publish.central_state_backup': '{candidate}/发布准备/状态备份/{stamp}',
    'publish.central_state_fields': {
        'working_head': 'working_head', 'working_head_sha256': 'working_head_sha256',
        'working_head_bytes': 'working_head_bytes', 'previous_working_head': 'previous_working_head',
        'latest_batch': 'latest_batch', 'latest_render': 'latest_render',
        'latest_render_sha256': 'latest_render_sha256', 'latest_render_pages': 'latest_render_pages',
        'updated_at': 'updated_at',
        # 修复 major#7：前身 publish_b52 还更新的字段，本工具之前遗漏。
        'review_entry': 'review_entry', 'review_manifest': 'review_manifest',
        'latest_rendered_docx_sha256': 'latest_rendered_docx_sha256',
        'latest_rendered_pages': 'latest_rendered_pages',
        # 修复 r3verify major：前身 publish_b52 还更新 status 与 active_revision_round，
        # 本工具之前遗漏，导致主代理/collab 读中央状态判断当前轮次时被旧文字/旧字段误导。
        'status': 'status', 'active_revision_round': 'active_revision_round',
    },
    # 仿 publish_b52：{n}/{rev} 可用，书册没配就用这份缺省文案。
    'publish.central_state_status_template': '第{n}批完成，待人工审阅；整书教研终审未完成',
    'handoff.owner_file': '协作/接管.json',
    'render.identity_file': '同版身份.json',
    'naming.batch_label': '第{n}批',
}
PROFILE_FIELDS_USED = set()


def _cfg(prof, dotted, default=None):
    """按点号路径读配置；本册没写就退回 _DEFAULTS，再退回 default，并登记本工具用到的字段。"""
    PROFILE_FIELDS_USED.add(dotted)
    cur = prof
    for part in dotted.split('.'):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return _DEFAULTS.get(dotted, default)
    return cur


class Gate(Exception):
    """门失败：dry-run 报告失败，apply 中止（若已过备份点则先回滚）。"""


class GuardRefusal(Exception):
    """冻结册写模式 / 写入目标解析越界：退出码 3。"""


class RollbackIncomplete(Exception):
    """第五轮新增：`--apply` 中途失败、且 `_rollback` 已尽力执行但仍有步骤失败时抛出，退出码 4。
    `original` 是触发本次回滚的原始错误说明；`incomplete` 是 `_rollback` 收集到的、未能恢复到
    发布前状态的路径/原因列表；`note` 是完整的回滚步骤日志（成功与失败都记）。main() 专门捕获
    这个类型，不能被落进 Gate(退出2)/GuardRefusal(退出3)/通用 Exception(退出2) 的任何一条分支。"""

    def __init__(self, original, incomplete, note):
        super().__init__(f'{original}；回滚不完整：{incomplete}')
        self.original = original
        self.incomplete = list(incomplete)
        self.note = note


def now_iso():
    return dt.datetime.now().astimezone().isoformat()


def stamp():
    return dt.datetime.now().strftime('%Y%m%d_%H%M%S')


def sha256_file(p):
    return dl.sha256_file(p)


def file_info(p):
    p = Path(p)
    return {'path': str(p), 'sha256': sha256_file(p), 'bytes': p.stat().st_size}


def load_json(p, label):
    p = Path(p)
    if not p.is_file():
        raise Gate(f'{label} 不存在：{p}')
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        raise Gate(f'{label} 不是合法 JSON：{p}：{e}')


def atomic_write_json(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + p.name + '.', suffix='.tmp', dir=str(p.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write('\n')
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_write_text(p, text):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + p.name + '.', suffix='.tmp', dir=str(p.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _realpath(p):
    return os.path.realpath(str(Path(p).expanduser()))


def _confine(path, allowed_dirs, what):
    """写入目标必须解析（realpath，防符号链接逃逸）在 allowed_dirs 之一内，否则 GuardRefusal。"""
    rp = _realpath(path)
    for d in allowed_dirs:
        rd = _realpath(d).rstrip('/')
        if rp == rd or rp.startswith(rd + '/'):
            return Path(rp)
    raise GuardRefusal(f'{what} 解析后不在配置声明的位置内：{path}\n允许的位置：{list(allowed_dirs)}')


def _within_rp(child, parent):
    """与 _confine 同口径的布尔版本，用于 dry-run 预检（不抛异常）。"""
    c = _realpath(child)
    p = _realpath(parent).rstrip('/')
    return c == p or c.startswith(p + '/')


def _is_sys_link(cur):
    """macOS 系统自带的 /var、/tmp、/etc → /private/… 不算逃逸（沙盒放在系统临时目录时会经过它们）。"""
    return os.path.realpath(str(cur)) == '/private' + str(cur)


def _confine_no_escape(root, configured, resolved, what):
    """修复 r3verify major：_reject_symlink 只查路径最后一级，路径中间某一级是符号链接时不会拦，
    _confine 再拿已经 resolve 过的目录跟自己比也形同虚设。这里逐级核对：
    - configured 是相对路径（相对 paths.root 解析，如 review_entry/workspace/review_history/
      review_manifest）：从 root 往下逐级检查每一级是否是指向 root 之外的符号链接；并且要求
      resolved（完全 resolve 后）仍落在 realpath(root) 之内，否则 GuardRefusal。
    - configured 是绝对路径（如 paths.central_state 可能配置在项目根之外的位置，这是合法用法，
      不能直接拿 paths.root 去比）：逐级核对配置路径的每一级是否是符号链接（无论指向哪里都拒绝），
      并核对 realpath 与配置路径本身逐字符一致；不一致就说明中途被链接替换过，GuardRefusal。
    两种模式（dry-run / --apply）都要跑，不放过任何一次。
    """
    if configured is None or resolved is None:
        return
    q = Path(str(configured)).expanduser()
    if q.is_absolute():
        cur = Path(q.anchor)
        for part in q.parts[1:]:
            cur = cur / part
            try:
                is_link = cur.is_symlink()
            except OSError:
                is_link = False
            if is_link and _is_sys_link(cur):
                continue
            if is_link:
                raise GuardRefusal(f'{what}（配置为项目根之外的绝对路径）中间一级是符号链接，拒绝：'
                                    f'{cur} -> {_realpath(cur)}')
        if _realpath(q) not in (str(q), '/private' + str(q)):
            raise GuardRefusal(f'{what} 的 realpath 与配置路径不一致（疑似符号链接逃逸）：{q} -> {_realpath(q)}')
    else:
        root_rp = _realpath(root)
        cur = Path(root_rp)
        for part in q.parts:
            cur = cur / part
            try:
                is_link = cur.is_symlink()
            except OSError:
                is_link = False
            if is_link:
                target_rp = _realpath(cur)
                if not (target_rp == root_rp or target_rp.startswith(root_rp + '/')):
                    raise GuardRefusal(f'{what} 路径中间一级 {cur} 是指向项目根之外的符号链接：{target_rp}')
        if not _within_rp(resolved, root):
            raise GuardRefusal(f'{what} 解析后不在项目根 {root_rp} 内：{resolved}')


def _confine_template_result(prof, template, ctx, base, what):
    """修复终审 major#1（回执 fix5）：`publish.archive_to`／`publish.central_state_backup` 这类
    模板，渲染结果可能是相对路径（书册配置里写成不带 `{review_history}`／`{candidate}` 占位符的
    字面相对路径，按 `resolve()` 同一套“相对项目根”语义解析——沙盒测试与部分书册配置就是这样写
    的），也可能是绝对路径（默认模板把 `{review_history}`／`{candidate}` 的真实绝对路径整段替换
    进结果里）。不管是哪种，最终都必须 realpath 落在声明的 `base`（`paths.review_history`／
    候选目录）之内——这与 note_path/manifest/central_state 的逃逸判定是同一个终审标准：只看最终
    解析位置，不能只汇总进 problems 变成普通门 FAIL（退出 2），命中即 `GuardRefusal`（退出 3），
    dry-run 与 `--apply` 两种模式都要跑，不能只在 --apply 时才检查（回执 fix5 major#1 明确要求
    "dry-run 阶段就报出"）。模板本身缺占位符取值时，`render_template` 抛出的 `Gate` 原样透传给
    调用方处理——这是配置问题，不是安全边界问题，不升级成 GuardRefusal。"""
    rendered = render_template(template, ctx, what)
    resolved = resolve(prof, rendered)
    if not _within_rp(resolved, base):
        raise GuardRefusal(f'{what} 渲染结果不在 {base} 内：{resolved}')
    return resolved


def _reject_symlink(p, what):
    """修复 major#5：目标本身（未 resolve 前）是符号链接就直接拒绝，防 review_entry/review_history
    等配置指向树外时靠 .resolve() 悄悄把写入带出去。"""
    if p is None:
        return
    try:
        is_link = Path(p).is_symlink()
    except OSError:
        is_link = False
    if is_link:
        raise GuardRefusal(f'{what} 本身是符号链接，拒绝写入：{p}')


def _reject_symlink_chain(p, what):
    """修复 confirm major#1（先看这里.md 等审阅入口内文件是符号链接、指向项目根内但审阅入口外
    的文件）：_reject_symlink 单独查最终一级已经不够——build_context 里 note_path/manifest_path
    在真正做符号链接判定之前就先 .resolve() 过一次，链接早被解引用，之后再查"是不是链接"永远是
    False。这里趁 resolve() 之前，对未解析路径本身及其每一级父目录逐个查是否符号链接，命中任何
    一级都 GuardRefusal（退出 3），不管链接指向哪里；dry-run 与 --apply 都要跑到这一步。"""
    if p is None:
        return
    q = Path(p).expanduser()
    parts = q.parts
    if not parts:
        return
    cur = Path(parts[0])
    for part in parts[1:]:
        cur = cur / part
        try:
            is_link = cur.is_symlink()
        except OSError:
            is_link = False
        if is_link and _is_sys_link(cur):
            continue
        if is_link:
            raise GuardRefusal(f'{what} 路径中 {cur} 是符号链接，resolve 前查出，拒绝：'
                                f'{cur} -> {_realpath(cur)}')


def _check_frozen_target(path, what):
    """修复 blocker#3：写入目标（不只是本册自身的 profile.frozen）逐一核对是否落在任何已登记
    冻结册的目录内，命中即 GuardRefusal（dry-run 也要跑，防止用改过 frozen=false 的 profile 副本
    绕过、而实际写入路径还是真实冻结册目录）。"""
    if path is None:
        return
    hits = dl._frozen_hits(Path(path))
    if hits:
        raise GuardRefusal(f'{what} 落在冻结册目录（{hits[0].get("title", hits[0].get("book_id"))}），拒绝写出：{path}')


_CANDIDATE_ROOT_RX = re.compile(r'/协作/候选/[^/]+/[^/]+/?$')


def gate_candidate_root(prof, candidate_root):
    """修复 major#8：候选根目录必须落在项目根内、形如 …/协作/候选/<谁>/<批次>/，否则备份/回执会
    写进书稿工作区根等不该写的位置。"""
    root = Path(prof['paths']['root']).expanduser().resolve()
    cr = Path(candidate_root).resolve()
    within_root = _within_rp(cr, root)
    shape_ok = bool(_CANDIDATE_ROOT_RX.search(str(cr) + '/'))
    if not (within_root and shape_ok):
        return {'id': 'candidate_root', 'level': 'FAIL',
                'message': f'候选目录必须落在项目根 {root} 内、形如 …/协作/候选/<谁>/<批次>/（可选 …/{{build_subdir}}/）：{cr}'}
    return {'id': 'candidate_root', 'level': 'PASS', 'message': str(cr)}


_PLACEHOLDER_RX = re.compile(r'\{(\w+)\}')


def render_template(template, ctx, what):
    missing = [m for m in _PLACEHOLDER_RX.findall(template) if m not in ctx]
    if missing:
        raise Gate(f'{what} 模板 {template!r} 缺少占位符取值：{missing}（需要在 profiles 里配置或用命令行参数提供）')
    return template.format(**ctx)


def match_preserve(name, patterns):
    import fnmatch
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def find_identity_file(near, name):
    """按 schema.md：在 near 及其上两级目录里找同版身份记录，找不到返回 None。"""
    p = Path(near).resolve()
    for d in (p, p.parent, p.parent.parent):
        cand = d / name
        if cand.is_file():
            return cand
    return None


# ---------------------------------------------------------------- 门（gates）
def build_context(args, prof):
    root = Path(prof['paths']['root']).expanduser().resolve()
    ws_rel = prof['paths'].get('workspace') or prof['paths'].get('aux_workspace')
    ws_raw = resolve(prof, ws_rel) if ws_rel else None
    _reject_symlink(ws_raw, '工作区根（paths.workspace/aux_workspace）')
    ws = ws_raw.resolve() if ws_raw else None
    if ws_rel:
        _confine_no_escape(root, ws_rel, ws, '工作区根（paths.workspace/aux_workspace）')
    aux = resolve(prof, prof['paths'].get('aux_workspace')).resolve() if prof['paths'].get('aux_workspace') else None
    if prof['paths'].get('aux_workspace'):
        _confine_no_escape(root, prof['paths'].get('aux_workspace'), aux, '辅助工作区（paths.aux_workspace）')
    review_raw = resolve(prof, prof['paths']['review_entry'])
    _reject_symlink(review_raw, '审阅入口（paths.review_entry）')
    review = review_raw.resolve()
    _confine_no_escape(root, prof['paths']['review_entry'], review, '审阅入口（paths.review_entry）')
    history_rel = prof['paths'].get('review_history')
    history_raw = resolve(prof, history_rel) if history_rel else None
    _reject_symlink(history_raw, '归档历史目录（paths.review_history）')
    history = history_raw.resolve() if history_raw else None
    if history_rel:
        _confine_no_escape(root, history_rel, history, '归档历史目录（paths.review_history）')
    manifest_rel = prof['paths'].get('review_manifest') or (str(Path(prof['paths']['review_entry']) / _cfg(prof, 'publish.manifest')))
    manifest_raw = resolve(prof, manifest_rel)
    # 修复 confirm major#1：resolve() 会把符号链接直接解引用，之后再查"是不是链接"就查不出来了——
    # 必须趁 resolve() 之前，对未解析路径本身及各级父目录逐一查是否符号链接。
    _reject_symlink_chain(manifest_raw, '审阅清单（paths.review_manifest）')
    manifest_path = manifest_raw.resolve()
    _confine_no_escape(root, manifest_rel, manifest_path, '审阅清单（paths.review_manifest）')
    # 审阅清单默认就配置在 review_entry 之内（真实 bixiu2/bixiu3 皆如此）；命中这种情况时，
    # realpath 还必须真落在 realpath(审阅入口) 内，不能只满足"落在项目根内"（否则一个指向
    # 项目根内、审阅入口外某文件的符号链接，若恰好在 resolve() 之前就被换成目标本身，仍可能
    # 绕过——这里与上面的 chain 检查是双保险，不依赖检测顺序）。
    manifest_entry_rel = str(Path(prof['paths']['review_entry']))
    if str(manifest_rel).replace('\\', '/').rstrip('/') == (manifest_entry_rel.replace('\\', '/').rstrip('/') + '/' + Path(manifest_rel).name) or \
            str(Path(manifest_rel).parent) == manifest_entry_rel:
        if not _within_rp(manifest_path, review):
            raise GuardRefusal(f'审阅清单（paths.review_manifest）解析后不在审阅入口 {review} 内：{manifest_path}')
    handoff_rel = prof['paths'].get('handoff')
    if handoff_rel:
        handoff_path = resolve(prof, handoff_rel).resolve()
        _confine_no_escape(root, handoff_rel, handoff_path, '接管.json（paths.handoff）')
    else:
        base = aux or ws
        if base is None:
            raise Gate('配置缺 paths.handoff，也缺 paths.workspace/aux_workspace，无法定位接管.json')
        handoff_path = (base / _cfg(prof, 'handoff.owner_file')).resolve()
    cs_rel = prof['paths'].get('central_state')
    if not cs_rel:
        raise Gate('配置缺 paths.central_state')
    central_raw = resolve(prof, cs_rel)
    _reject_symlink_chain(central_raw, '中央状态（paths.central_state）')
    central_path = central_raw.resolve()
    _confine_no_escape(root, cs_rel, central_path, '中央状态（paths.central_state）')
    # 修复终审 major#1（回执 fix5）：note_path 之前完全没有过 containment 检查——
    # compute_targets 里的 `_confine(p, [p.parent])` 是拿路径跟它自己刚算出来的父目录比，
    # 对任何路径都恒真。note_file 带 '../' 时（如 '../../G2_外部.md'）能把"先看这里"写到
    # 审阅入口之外甚至 paths.root 之外，且回滚会把根外原文件当"新建"的一并搬走/覆盖。
    # 这里先要求 note_file 必须是单级文件名（不能是路径），再和 manifest 同口径地过
    # _confine_no_escape（相对 paths.review_entry、以项目根为 root 逐级核对）。
    note_name = _cfg(prof, 'publish.note_file')
    note_name_str = str(note_name)
    if (not note_name_str or note_name_str in ('.', '..')
            or any(sep in note_name_str for sep in ('/', '\\'))
            or '..' in Path(note_name_str).parts):
        raise GuardRefusal(f'先看这里（publish.note_file）只允许单级文件名，不能包含路径分隔符或上级目录：{note_name!r}')
    note_rel = str(Path(prof['paths']['review_entry']) / note_name_str)
    note_raw = review / note_name_str
    # 修复 confirm major#1（剩余口子）：先看这里.md 若本身就是符号链接（不管指向哪里，哪怕是
    # 项目根内、审阅入口外的文件），resolve() 之前先查出来拒绝——这是终审确认的实际攻击面：
    # note_path 原先先 .resolve() 再检查，链接早被解引用，_reject_symlink/_confine_no_escape
    # 都查不出"这一级本身是链接"。
    _reject_symlink_chain(note_raw, '先看这里（publish.note_file）')
    note_path = note_raw.resolve()
    _confine_no_escape(root, note_rel, note_path, '先看这里（publish.note_file）')
    # 先看这里必然是"审阅入口内新文件"（note_rel 就是拿 review_entry 拼出来的），realpath
    # 必须真落在 realpath(审阅入口) 内，不能只满足"落在项目根内"。
    if not _within_rp(note_path, review):
        raise GuardRefusal(f'先看这里（publish.note_file）解析后不在审阅入口 {review} 内：{note_path}')
    return {
        'root': root, 'ws': ws, 'review': review, 'history': history,
        'manifest_path': manifest_path, 'handoff_path': handoff_path,
        'central_path': central_path, 'note_path': note_path,
        # 供 compute_targets 复核用：保留各写入目标"配置里的原始相对/绝对路径写法"，
        # 这样 compute_targets 能再跑一遍真正的 _confine_no_escape，而不是拿已经算好的
        # 路径的 .parent 去跟它自己比（那样恒真，等于没查）。
        'manifest_configured': manifest_rel, 'central_configured': cs_rel, 'note_configured': note_rel,
    }


def candidate_root_of(docx_path, prof):
    build_subdir = prof['paths'].get('build_subdir', '构建')
    p = Path(docx_path).resolve().parent
    return p.parent if p.name == build_subdir else p


def gate_frozen(prof, apply_):
    if prof.get('frozen'):
        msg = f"{prof.get('title', prof.get('book_id'))} 已冻结（{prof.get('frozen_note', '')}），拒绝发布"
        if apply_:
            raise GuardRefusal(msg)
        return {'id': 'frozen', 'level': 'FAIL', 'message': msg}
    return {'id': 'frozen', 'level': 'PASS', 'message': '未冻结'}


def gate_ownership(ctx, actor):
    handoff = load_json(ctx['handoff_path'], '接管.json')
    owner_ok = handoff.get('owner') == actor
    phase_ok = handoff.get('phase') == 'owned'
    if owner_ok and phase_ok:
        return {'id': 'ownership', 'level': 'PASS', 'message': f'owner={actor} phase=owned'}, handoff
    return {'id': 'ownership', 'level': 'FAIL',
            'message': f"接管.json 与写权不符：owner={handoff.get('owner')!r}（要求 {actor!r}），phase={handoff.get('phase')!r}（要求 owned）"}, handoff


def gate_acceptance(args, prof, docx_info, pdf_info, pdf_pages, central):
    acc = load_json(args.acceptance, '验收 JSON')
    pdf_sha_hint = pdf_info['sha256']
    problems = []
    if acc.get('approval_type') != 'root_technical_acceptance':
        problems.append('approval_type 不是 root_technical_acceptance')
    if acc.get('approved') is not True:
        problems.append('approved 不为 true')
    if acc.get('final_qa_passed') is not True:
        problems.append('final_qa_passed 不为 true')
    if acc.get('actor_owned') != args.actor:
        problems.append(f"actor_owned={acc.get('actor_owned')!r} 与 --actor {args.actor!r} 不符")
    approved_batch = str(acc.get('batch') or '')
    if approved_batch not in (str(args.batch), f'batch{args.batch}'):
        problems.append(f"验收 batch={approved_batch!r} 与 --batch {args.batch!r} 不符")
    cand = acc.get('candidate') or {}
    if cand.get('docx_sha256') != docx_info['sha256']:
        problems.append(f"验收里候选 docx_sha256 与实际不符：{cand.get('docx_sha256')!r} vs {docx_info['sha256']}")
    if cand.get('pdf_sha256') != pdf_sha_hint:
        problems.append(f"验收里候选 pdf_sha256 与实际不符：{cand.get('pdf_sha256')!r} vs {pdf_sha_hint}")
    if cand.get('pdf_pages') is None or int(cand.get('pdf_pages')) != pdf_pages:
        problems.append(f"验收里候选 pdf_pages={cand.get('pdf_pages')!r} 与实际页数 {pdf_pages} 不符")
    binding = acc.get('same_version_binding')
    if not isinstance(binding, dict):
        problems.append('缺 same_version_binding')
    else:
        if str(binding.get('status', '')).upper() != 'PASS':
            problems.append(f"same_version_binding.status={binding.get('status')!r}，要求 PASS")
        if binding.get('docx_sha256') != docx_info['sha256']:
            problems.append('same_version_binding.docx_sha256 与候选不符')
        if binding.get('pdf_sha256') != pdf_sha_hint:
            problems.append('same_version_binding.pdf_sha256 与候选不符')
        if binding.get('pdf_pages') != pdf_pages:
            problems.append('same_version_binding.pdf_pages 与候选不符')
    fields = _cfg(prof, 'publish.central_state_fields')
    field = fields['working_head_sha256']
    central_sha = central.get(field)
    # 修复 minor：两个别名键都读（前身 publish_b52 同时接受 expected_working_head_sha256）。
    expected = acc.get('expected_current_working_head_sha256')
    if expected is None:
        expected = acc.get('expected_working_head_sha256')
    warn = None
    if expected is None:
        warn = f'验收 JSON 未给 expected_current_working_head_sha256/expected_working_head_sha256，无法核对父稿（中央状态 {field}={central_sha!r}）'
    elif expected != central_sha:
        problems.append(f'验收 expected_current_working_head_sha256(或别名)={expected!r} 与中央状态 {field}={central_sha!r} 不符')
    # 修复 minor：核中央状态记录的工作头文件磁盘 SHA 是否仍等于记录（工作头是否被人工改动）。
    wh_field = fields['working_head']
    wh_path = central.get(wh_field)
    if wh_path:
        if not Path(wh_path).is_file():
            problems.append(f'中央状态记录的工作头文件不存在：{wh_path}')
        elif central_sha and sha256_file(wh_path) != central_sha:
            problems.append(f'工作头磁盘文件 SHA 与中央状态记录的 {field} 不符，工作头疑似被人工改动：{wh_path}')
    if problems:
        return {'id': 'acceptance', 'level': 'FAIL', 'message': '；'.join(problems)}, acc
    lvl = 'WARN' if warn else 'PASS'
    return {'id': 'acceptance', 'level': lvl, 'message': warn or '验收 JSON 各字段核对一致'}, acc


def _parse_batch_num(s):
    """修复 minor：优先匹配 batch(\\d+)/第(\\d+)批；否则要求字符串里只有唯一一段数字，
    多段数字（如 'R31续修_batch52' 若两种命名法都不中……仍会被 batch(\\d+) 命中）时不再
    取第一个数字了事，而是返回 None 交调用方判定为“解析歧义”。"""
    s = str(s or '')
    m = re.search(r'batch(\d+)', s, re.I) or re.search(r'第(\d+)批', s)
    if m:
        return int(m.group(1))
    nums = re.findall(r'\d+', s)
    if len(nums) == 1:
        return int(nums[0])
    return None


def gate_batch_monotonic(prof, central, batch):
    field = _cfg(prof, 'publish.central_state_fields')['latest_batch']
    cur = central.get(field)
    cur_n = _parse_batch_num(cur)
    if cur_n is None:
        return {'id': 'batch_monotonic', 'level': 'WARN',
                'message': f'中央状态 {field}={cur!r} 无法唯一解析出数字，跳过递增核对'}
    new_n = _parse_batch_num(batch)
    if new_n is None:
        return {'id': 'batch_monotonic', 'level': 'FAIL', 'message': f'--batch {batch!r} 解析不出唯一数字'}
    if new_n <= cur_n:
        return {'id': 'batch_monotonic', 'level': 'FAIL', 'message': f'批次号未递增：中央状态当前 {cur_n}，本批 {new_n}'}
    return {'id': 'batch_monotonic', 'level': 'PASS', 'message': f'{cur_n} → {new_n}'}


def gate_review_entry(ctx, prof, docx_info, pdf_info):
    review, manifest_path = ctx['review'], ctx['manifest_path']
    if not manifest_path.is_file():
        return {'id': 'review_entry', 'level': 'FAIL', 'message': f'审阅清单不存在：{manifest_path}'}, None, [], []
    manifest = load_json(manifest_path, '审阅清单')
    registered = []
    for key in ('docx', 'pdf'):
        v = manifest.get(key)
        if isinstance(v, str) and v:
            registered.append(Path(v).name)
    note_name = _cfg(prof, 'publish.note_file')
    registered.append(note_name)
    registered = list(dict.fromkeys(registered))
    problems = []
    missing = [n for n in registered if not (review / n).is_file()]
    if missing:
        problems.append('清单登记但审阅入口缺失：' + '、'.join(missing))
    for key, name in (('docx', None), ('pdf', None)):
        v = manifest.get(key)
        if isinstance(v, str) and v and Path(v).name not in missing:
            p = review / Path(v).name
            if p.is_file() and sha256_file(p) != manifest.get(f'{key}_sha256'):
                problems.append(f'审阅入口 {key} 与清单 SHA 不一致（可能被人工改过）：{p}')
    already = (manifest.get('docx_sha256') == docx_info['sha256'] and manifest.get('pdf_sha256') == pdf_info['sha256'])
    if already:
        problems.append('审阅入口已是此版（候选 SHA 与清单当前登记一致），无需重新发布')
    preserve = _cfg(prof, 'publish.preserve')
    known = set(registered) | {manifest_path.name}
    unknown = sorted(p.name for p in review.iterdir()
                      if p.name not in known and not match_preserve(p.name, preserve))
    if unknown:
        problems.append('审阅入口有清单外且未在 publish.preserve 里的文件：' + '、'.join(unknown))
    if problems:
        return {'id': 'review_entry', 'level': 'FAIL', 'message': '；'.join(problems)}, manifest, registered, unknown
    return {'id': 'review_entry', 'level': 'PASS', 'message': f'与清单一致，登记 {len(registered)} 项，未知项 {len(unknown)} 个原样保留'}, manifest, registered, unknown


def gate_same_version_identity(prof, docx_path, acc):
    name = _cfg(prof, 'render.identity_file')
    found = find_identity_file(docx_path, name)
    binding = acc.get('same_version_binding') or {}
    if not found:
        return {'id': 'same_version_identity', 'level': 'WARN', 'message': f'附近未找到 {name}，无法交叉核对同版身份'}
    ident = load_json(found, '同版身份记录')
    fields = ('docx_sha256', 'pdf_sha256', 'pdf_pages', 'status')
    mism = [f for f in fields if ident.get(f) != binding.get(f)]
    if mism:
        return {'id': 'same_version_identity', 'level': 'FAIL',
                'message': f'{found} 与验收里的 same_version_binding 不一致：{mism}'}
    return {'id': 'same_version_identity', 'level': 'PASS', 'message': f'与 {found} 一致'}


_REQUIRED_CENTRAL_FIELDS = (
    'working_head', 'working_head_sha256', 'working_head_bytes', 'previous_working_head',
    'latest_batch', 'latest_render', 'latest_render_sha256', 'latest_render_pages', 'updated_at',
    'review_entry', 'review_manifest', 'latest_rendered_docx_sha256', 'latest_rendered_pages',
)
# 'status'／'active_revision_round' 是可选字段：do_apply 第 6 步已经用 `if 'status' in fields`
# 之类的写法优雅跳过缺失的可选字段，不在这里强制要求。


def _precheck_central_state_write(prof, central, batch):
    """修复终审 minor（回执 fix5）：中央状态第 6 步会因几种情况在 --apply 写到一半才失败——
    ①`publish.central_state_fields` 整体覆盖时漏了必需字段名，写入时 KeyError；
    ②`publish.central_state_status_template` 带工具不认识的占位符；
    ③中央状态里现有的 `active_revision_round` 不是 dict（`.update()` 会炸）。
    这三种都能在 dry-run 阶段静态判断，不必等 --apply 真正跑到第 6 步、再靠事务回滚兜底——
    调用方把返回的 problems 汇总进 'write_targets' 门 FAIL（退出 2，不留输出）。"""
    problems = []
    fields = _cfg(prof, 'publish.central_state_fields')
    if not isinstance(fields, dict):
        return [f'publish.central_state_fields 必须是字段名映射（dict），当前是 {type(fields).__name__}']
    missing = [k for k in _REQUIRED_CENTRAL_FIELDS if k not in fields]
    if missing:
        problems.append('publish.central_state_fields 缺少中央状态更新步骤必需的字段名映射：' + '、'.join(missing))
    batch_m = re.search(r'\d+', str(batch))
    batch_n = batch_m.group() if batch_m else str(batch)
    if 'status' in fields:
        status_tpl = _cfg(prof, 'publish.central_state_status_template')
        try:
            if ('{n}' in status_tpl or '{rev}' in status_tpl):
                render_template(status_tpl, {'n': batch_n, 'rev': batch_n}, 'publish.central_state_status_template')
        except Gate as e:
            problems.append(str(e))
    if 'active_revision_round' in fields and isinstance(central, dict):
        cur = central.get(fields['active_revision_round'])
        if cur is not None and not isinstance(cur, dict):
            problems.append(f"中央状态 {fields['active_revision_round']}（active_revision_round）现有值不是对象（是 "
                             f'{type(cur).__name__}），无法 .update()：{cur!r}')
    return problems


def compute_targets(args, prof, ctx, candidate_root, stem, prev_m, central):
    """修复 major#6：dry-run 也要算出并检查全部写入目标（不止 review_entry/workspace_root/
    central_state 三个目录），并给出逐文件 {action,src,dst,sha256} 计划。containment、
    存在性与冻结检查都在这里做，两种模式（dry-run/--apply）之前都跑，不等到 --apply 才发现。
    frozen-hit 与符号链接逃逸直接 GuardRefusal（连 dry-run 也不放过，退出 3）；
    其余问题（如工作区根同名异容覆盖、stem 含路径分隔符、归档目标越界）汇总进返回的
    problems 列表，由调用方包成 'write_targets' 门 FAIL（dry-run 报告，--apply 前中止，退出 2）。
    """
    review, ws, history = ctx['review'], ctx['ws'], ctx['history']
    central_path, manifest_path, note_path = ctx['central_path'], ctx['manifest_path'], ctx['note_path']
    targets = []
    problems = []

    # 修复终审 major#1（回执 fix5）：这里原来是 `_confine(p, [p.parent])`——p.parent 就是拿 p
    # 自己算出来的，对任何 p 恒真，等于没查。改成对 build_context 里记下的"配置原文"再跑一遍
    # 真正的 _confine_no_escape（逐级查符号链接＋最终 realpath 落在项目根内），note_path 借此
    # 第一次真正获得 containment 保护，manifest/central 则是双保险（build_context 已查过一次）。
    for p, configured, what in (
            (central_path, ctx['central_configured'], '中央状态'),
            (manifest_path, ctx['manifest_configured'], '审阅清单'),
            (note_path, ctx['note_configured'], '先看这里')):
        _reject_symlink(p, what)
        _confine_no_escape(ctx['root'], configured, p, what)
        _check_frozen_target(p, what)
    _check_frozen_target(review, '审阅入口')
    if ws:
        _check_frozen_target(ws, '工作区根')
    if history:
        _check_frozen_target(history, '归档历史目录')
    _check_frozen_target(candidate_root, '候选目录（含备份/回执）')

    # 修复终审 minor（回执 fix5）：中央状态第 6 步几种可预见失败（字段映射缺键、status 模板占位符
    # 不认识、active_revision_round 不是 dict）在这里静态判断，不用等 --apply 写到一半才发现。
    problems.extend(_precheck_central_state_write(prof, central, args.batch))

    if stem is None:
        return targets, problems  # naming.docx_stem 缺失，由 stem_problem 单独挡住 --apply

    if any(sep in stem for sep in ('/', '\\')) or '..' in Path(stem).parts:
        problems.append(f'渲染出的文件名（naming.docx_stem／--label）包含路径分隔符或上级目录，拒绝：{stem!r}')
        return targets, problems

    # 修复终审 minor（回执 fix5）：paths.review_history 配了但磁盘上不存在时，dry-run 之前全部门
    # PASS——发布只能在 --apply 里靠 archive_dir.mkdir(parents=True) 顺带把它建出来，一旦中途失败，
    # 这个新建的目录树又不在"本次新建的归档目录"名单里，回滚不会清理。改成 dry-run 阶段直接 FAIL，
    # 要求 review_history 本身必须已经存在（真实 bixiu2/bixiu3 现状都满足）。
    if not history:
        problems.append('配置缺 paths.review_history，无法归档旧版（publish.archive_to 需要它）')
    elif not history.exists():
        problems.append(f'归档历史目录在磁盘上不存在：{history}（paths.review_history 需要事先存在，工具不会自动新建根目录）')
    else:
        archive_tpl = _cfg(prof, 'publish.archive_to')
        archive_ctx = {'review_history': str(history), 'prev': str(prev_m) if prev_m is not None else '0', 'stamp': stamp()}
        try:
            # 修复终审 major#1：升级为 _confine_template_result——旧版只是把逃逸汇总进 problems、
            # 变成退出 2 的普通门 FAIL；现在发现逃逸时是 GuardRefusal（退出 3），dry-run 就报出。
            archive_preview = _confine_template_result(prof, archive_tpl, archive_ctx, history, '归档目录（publish.archive_to）')
        except Gate as e:
            problems.append(str(e))
            archive_preview = None
        if archive_preview is not None:
            _check_frozen_target(archive_preview, '归档目录')
            # 修复 r3verify blocker：归档目录若发布前就已存在（publish.archive_to 模板不含
            # {stamp}，或同一秒内 stamp 撞名），dry-run 就要在这里 FAIL，不能等到 --apply 才
            # 发现——发现得晚，回滚代码还会把这个“已存在的历史归档”当成本次新建的一并删掉。
            if archive_preview.exists():
                problems.append(f'归档目标目录已存在（发布前就有历史归档，拒绝覆盖/回滚时可能被误删）：{archive_preview}')
            targets.append({'action': 'archive_dir', 'dst': str(archive_preview)})

    # 修复终审 major#1（回执 fix5）：之前这里是硬编码猜测的 `候选/发布准备/状态备份`，跟
    # do_apply 实际按 `publish.central_state_backup` 模板渲染出的路径可能对不上（书册若自定义了
    # 这个模板，dry-run 计划里给的路径就是错的），而且这个目标此前只在 --apply 里才检查
    # containment，dry-run 完全没查。现在按同一模板真正渲染＋校验，dry-run 与 --apply 用的是
    # 同一套 containment 判定（_confine_template_result），逃逸一律 GuardRefusal（退出 3）。
    backup_tpl = _cfg(prof, 'publish.central_state_backup')
    try:
        backup_preview = _confine_template_result(
            prof, backup_tpl, {'candidate': str(candidate_root), 'stamp': stamp()},
            candidate_root, '中央状态备份目录（publish.central_state_backup）')
        _check_frozen_target(backup_preview, '中央状态备份目录')
        targets.append({'action': 'write_backup_dir', 'dst': str(backup_preview)})
    except Gate as e:
        problems.append(str(e))

    docx_src, pdf_src = Path(args.docx), Path(args.pdf)
    if ws:
        for label, dst, src in (('workspace_docx', ws / f'{stem}.docx', docx_src),
                                 ('workspace_pdf', ws / f'{stem}.pdf', pdf_src)):
            _reject_symlink_chain(dst, '工作区根写入目标')
            _confine(dst, [ws], '工作区根写入目标')
            sha = sha256_file(src) if src.is_file() else None
            if dst.exists():
                if dst.is_file() and sha and sha256_file(dst) == sha:
                    action = 'skip(已是同内容)'
                else:
                    problems.append(f'工作区根已存在同名但内容不同的文件，拒绝覆盖（人工改稿/旧候选/Word另存都可能是这个）：{dst}')
                    action = 'BLOCKED(exists_diff_sha)'
            else:
                action = 'copy'
            targets.append({'action': f'{label}:{action}', 'src': str(src), 'dst': str(dst), 'sha256': sha})

    for label, dst, src in (('review_docx', review / f'{stem}.docx', docx_src),
                             ('review_pdf', review / f'{stem}.pdf', pdf_src)):
        _reject_symlink_chain(dst, '审阅入口写入目标')
        _confine(dst, [review], '审阅入口写入目标')
        sha = sha256_file(src) if src.is_file() else None
        targets.append({'action': f'{label}:copy', 'src': str(src), 'dst': str(dst), 'sha256': sha})

    targets.append({'action': 'write_manifest', 'dst': str(manifest_path)})
    targets.append({'action': 'write_note', 'dst': str(note_path)})
    targets.append({'action': 'update_central_state', 'dst': str(central_path)})
    receipt_dir = candidate_root / '发布准备'
    _reject_symlink(receipt_dir, '晋升回执目录')
    targets.append({'action': 'write_receipt', 'dst': str(receipt_dir / '晋升回执.json')})
    # write_backup_dir 已经在上面用 _confine_template_result 按真实模板算好、加入 targets，
    # 这里不再用硬编码路径重复 append 一份（旧版硬编码猜测的路径在自定义模板下会跟实际不符）。
    return targets, problems


def gate_health(args, prof, docx_path, pdf_path, acc):
    if not args.health:
        return {'id': 'health', 'level': 'INFO', 'message': '未要求 --health'}
    try:
        rep = bh.run_health(str(docx_path), str(pdf_path) if pdf_path else None, profile=prof)
    except Exception as e:
        return {'id': 'health', 'level': 'FAIL', 'message': f'体检运行失败：{type(e).__name__}: {e}'}
    fail = rep['summary']['FAIL']
    if fail == 0:
        return {'id': 'health', 'level': 'PASS', 'message': '体检 0 FAIL'}
    accepted = set(acc.get('accepted_health_fails') or [])
    unaccepted = [f for f in rep['findings'] if f['level'] == 'FAIL' and f.get('rule') not in accepted]
    if unaccepted:
        return {'id': 'health', 'level': 'FAIL',
                'message': f'体检 {fail} FAIL，验收 JSON 未在 accepted_health_fails 里显式接受：' +
                           '、'.join(sorted({f['rule'] for f in unaccepted}))[:500]}
    return {'id': 'health', 'level': 'WARN', 'message': f'体检 {fail} FAIL，均已在验收 JSON accepted_health_fails 里显式接受'}


# ---------------------------------------------------------------- 主流程
def run(args):
    prof = load_profile(args.profile)
    gates = []
    g = gate_frozen(prof, args.apply)
    gates.append(g)
    frozen_dry_fail = g['level'] == 'FAIL'

    ctx = build_context(args, prof)
    docx_path = Path(args.docx).expanduser().resolve()
    pdf_path = Path(args.pdf).expanduser().resolve()
    if not docx_path.is_file():
        raise Gate(f'候选 DOCX 不存在：{docx_path}')
    if not pdf_path.is_file():
        raise Gate(f'候选 PDF 不存在：{pdf_path}')
    docx_info = file_info(docx_path)
    pdf_info = file_info(pdf_path)
    try:
        from pypdf import PdfReader
        pdf_pages = len(PdfReader(str(pdf_path)).pages)
    except Exception as e:
        raise Gate(f'PDF 无法用 pypdf 读取页数：{e}')
    pdf_info['pdf_pages'] = pdf_pages

    central = load_json(ctx['central_path'], '中央状态')
    g_own, handoff = gate_ownership(ctx, args.actor)
    gates.append(g_own)
    g_acc, acc = gate_acceptance(args, prof, docx_info, pdf_info, pdf_pages, central)
    gates.append(g_acc)
    gates.append(gate_batch_monotonic(prof, central, args.batch))
    g_rev, manifest, registered, unknown = gate_review_entry(ctx, prof, docx_info, pdf_info)
    gates.append(g_rev)
    gates.append(gate_same_version_identity(prof, docx_path, acc))
    gates.append(gate_health(args, prof, docx_path, pdf_path, acc))

    # 修复 major#8：候选目录形态门，在算 stem/targets 之前先做（写权与目录形态无关，任何模式都查）。
    candidate_root = candidate_root_of(docx_path, prof)
    g_cand = gate_candidate_root(prof, candidate_root)
    gates.append(g_cand)

    batch_n_match = re.search(r'\d+', str(args.batch))
    # 修复 r3verify minor：归档目录名里的 {prev} 之前直接取 latest_batch 字符串里的第一个数字，
    # 跟已经修好的 _parse_batch_num 口径（batch(\d+)/第(\d+)批优先，多段数字才判歧义）不一致——
    # 'R31续修_batch51' 会被错读成 31。这里统一改用 _parse_batch_num；解析不出时 prev_m 为
    # None，渲染 archive_to 时退回 '0'，与原先“解析失败退回 0”的兜底行为一致。
    prev_m = _parse_batch_num(central.get(_cfg(prof, 'publish.central_state_fields')['latest_batch']))
    tctx = {
        'n': batch_n_match.group() if batch_n_match else str(args.batch),
        'rev': batch_n_match.group() if batch_n_match else str(args.batch),
        'label': args.label or 'batch',
        'date': dt.date.today().strftime('%Y%m%d'),
        'prev': str(prev_m) if prev_m is not None else '0',
        'stamp': stamp(),
        'candidate': str(candidate_root),
        'review_history': str(ctx['history']) if ctx['history'] else '',
    }
    stem_tpl = prof.get('naming', {}).get('docx_stem')
    stem = None
    stem_problem = None
    if stem_tpl:
        try:
            stem = render_template(stem_tpl, tctx, 'naming.docx_stem')
        except Gate as e:
            stem_problem = str(e)
    else:
        stem_problem = '配置缺 naming.docx_stem'
        PROFILE_FIELDS_USED.add('naming.docx_stem')

    # 修复 major#6：目标计算与 containment/frozen 预检在 dry-run 也要跑（不能等 --apply 才发现）。
    # 冻结命中/符号链接逃逸在这里面直接 GuardRefusal（两种模式都不放过，退出 3）。
    file_targets, target_problems = compute_targets(args, prof, ctx, candidate_root, stem, prev_m, central)
    if target_problems:
        gates.append({'id': 'write_targets', 'level': 'FAIL', 'message': '；'.join(target_problems)})
    elif stem is not None:
        gates.append({'id': 'write_targets', 'level': 'PASS', 'message': f'{len(file_targets)} 个写入目标全部通过 containment/存在性检查'})
    else:
        gates.append({'id': 'write_targets', 'level': 'INFO', 'message': 'naming.docx_stem 缺失，暂不能算出具体文件目标'})

    fail_gates = [x for x in gates if x['level'] == 'FAIL']
    pass_ok = not fail_gates

    plan = {
        'tool': TOOL_NAME, 'version': TOOL_VERSION, 'mode': 'apply' if args.apply else 'dry-run',
        'profile': {'book_id': prof.get('book_id'), 'title': prof.get('title'), 'frozen': bool(prof.get('frozen'))},
        'actor': args.actor, 'batch': args.batch,
        'inputs': {'docx': docx_info, 'pdf': pdf_info, 'acceptance': file_info(args.acceptance),
                   'central_state': file_info(ctx['central_path']), 'handoff': file_info(ctx['handoff_path'])},
        'gates': gates,
        'gates_pass': pass_ok,
        'review_entry_unknown_items': unknown,
        'naming': {'docx_stem_template': stem_tpl, 'rendered': stem, 'problem': stem_problem},
        'candidate_root': str(candidate_root),
        'targets': {
            'workspace_root': str(ctx['ws']) if ctx['ws'] else None,
            'review_entry': str(ctx['review']),
            'central_state': str(ctx['central_path']),
            'files': file_targets,
        },
        'profile_fields_needed': sorted(PROFILE_FIELDS_USED),
        # 修复终审 minor（回执 fix5）：之前只有 apply_result／晋升回执才列
        # central_state_fields_not_updated，dry-run 计划看不出来书册配置漏了 status／
        # active_revision_round 这两个可选字段名映射；这里预先算好，dry-run 也能看到。
        'central_state_fields_not_updated_preview': [
            k for k in ('status', 'active_revision_round')
            if k not in _cfg(prof, 'publish.central_state_fields')],
    }

    if args.note:
        plan['inputs']['note'] = file_info(args.note)

    if not args.apply:
        return plan, 0 if (pass_ok and not frozen_dry_fail) else 2 if fail_gates else 1

    # ---- apply：全部门必须 PASS/WARN（不含 FAIL）----
    if frozen_dry_fail:
        raise GuardRefusal(plan['gates'][0]['message'])
    if fail_gates:
        raise Gate('以下门未通过，拒绝发布：' + '；'.join(f"[{x['id']}] {x['message']}" for x in fail_gates))
    if stem_problem:
        raise Gate(stem_problem)

    result = do_apply(args, prof, ctx, docx_path, pdf_path, docx_info, pdf_info, pdf_pages,
                       manifest, registered, unknown, acc, central, candidate_root, stem, prev_m)
    plan['apply_result'] = result
    return plan, 0


def do_apply(args, prof, ctx, docx_path, pdf_path, docx_info, pdf_info, pdf_pages,
             manifest, registered, unknown, acc, central, candidate_root, stem, prev_m):
    review, ws, history = ctx['review'], ctx['ws'], ctx['history']
    central_path, manifest_path, note_path = ctx['central_path'], ctx['manifest_path'], ctx['note_path']

    # 修复终审 major#1（回执 fix5）：跟 compute_targets 用同一套 _confine_template_result
    # （最终 realpath 落在 candidate_root 内，逃逸 GuardRefusal 退出 3）。
    backup_tpl = _cfg(prof, 'publish.central_state_backup')
    backup_dir = _confine_template_result(
        prof, backup_tpl, {'candidate': str(candidate_root), 'stamp': stamp()},
        candidate_root, '中央状态备份目录（publish.central_state_backup）')
    _reject_symlink(backup_dir, '中央状态备份目录')
    _check_frozen_target(backup_dir, '中央状态备份目录')
    if backup_dir.exists() and any(backup_dir.iterdir()):
        # 修复 minor：真实 bixiu3 模板 publish.central_state_backup 不含 {stamp}
        # （固定 "{candidate}/发布准备/状态备份"），同一候选目录第二次发布/重试会撞上一次的备份。
        # 已有内容就不覆盖，套一层时间戳子目录。
        backup_dir = backup_dir / stamp()
    backup_dir.mkdir(parents=True, exist_ok=True)

    receipt_dir = _confine(candidate_root / '发布准备', [candidate_root], '晋升回执目录')
    _reject_symlink(receipt_dir, '晋升回执目录')
    receipt_path = receipt_dir / '晋升回执.json'

    # 备份点：中央状态、清单、先看这里、（若已存在的）晋升回执，回滚时按这份原样恢复。
    central_before_sha = sha256_file(central_path)
    manifest_before_sha = sha256_file(manifest_path) if manifest_path.is_file() else None
    note_before_sha = sha256_file(note_path) if note_path.is_file() else None
    receipt_before_sha = sha256_file(receipt_path) if receipt_path.is_file() else None
    if sha256_file(docx_path) != docx_info['sha256'] or sha256_file(pdf_path) != pdf_info['sha256']:
        raise Gate('候选文件在门检查之后、写入之前发生变化，中止')
    handoff_now = load_json(ctx['handoff_path'], '接管.json')
    if handoff_now.get('owner') != args.actor or handoff_now.get('phase') != 'owned':
        raise Gate('写权在门检查之后、写入之前发生变化，中止')

    shutil.copy2(central_path, backup_dir / central_path.name)
    if manifest_path.is_file():
        shutil.copy2(manifest_path, backup_dir / manifest_path.name)
    if note_path.is_file():
        shutil.copy2(note_path, backup_dir / note_path.name)
    if receipt_path.is_file():
        receipt_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(receipt_path, backup_dir / receipt_path.name)

    moved = []       # [(dst_in_archive, original_path)]，回滚时移回
    created = []     # 本次全新写出的文件（工作区根/审阅入口新副本、晋升回执），回滚时先删除
    archive_dir = None
    # 修复 r3verify blocker：archive_created 只有本次 mkdir(exist_ok=False) 真正成功之后才置 True。
    # _rollback 只有在 archive_created 为真时才能 rmtree archive_dir——否则 archive_dir 可能指向
    # 一个“发布前就已存在”的历史归档目录（archive_dir 在赋值之后、exists() 检查之前就已经确定，
    # 若这里 raise Gate，旧版整套回滚逻辑会把这个既有归档连同里面的旧审阅稿一起删掉）。
    archive_created = False
    archive_new_ancestors = []  # 本次 mkdir(parents=True) 顺带新建的中间目录（不含 archive_dir 本身）
    receipt_written = False
    try:
        # 1) 归档审阅入口现有登记文件（docx/pdf 物理搬走；manifest 只复制一份存档）
        if not history:
            raise Gate('配置缺 paths.review_history，无法归档旧版（应已在 write_targets 门挡住，此处是防御性复核）')
        archive_tpl = _cfg(prof, 'publish.archive_to')
        archive_ctx = {'review_history': str(history), 'prev': str(prev_m) if prev_m is not None else '0', 'stamp': stamp()}
        # 修复终审 major#1：与 compute_targets 同一套 _confine_template_result，逃逸即
        # GuardRefusal（退出 3），不再是渲染出绝对路径字符串后只拿 _confine 跟自身父目录比。
        archive_dir = _confine_template_result(prof, archive_tpl, archive_ctx, history, '归档目录（publish.archive_to）')
        _reject_symlink(archive_dir, '归档目录')
        _check_frozen_target(archive_dir, '归档目录')
        if archive_dir.exists():
            raise Gate(f'归档目录已存在：{archive_dir}')
        # 修复终审 minor（回执 fix5）：mkdir(parents=True) 会顺带新建 archive_dir 尚不存在的
        # 中间目录（archive_to 模板带子目录、或 paths.review_history 刚新建时更深一级还没有）。
        # 先记下哪些祖先目录现在还不存在——这些是"本次新建"的，回滚时（在 rmtree(archive_dir)
        # 之后）由深到浅逐个 rmdir，不动 archive_dir 之前就已经存在的目录。
        cur = archive_dir.parent
        history_rp = _realpath(history)
        while _realpath(cur) != history_rp and not cur.exists():
            archive_new_ancestors.append(cur)
            cur = cur.parent
        archive_dir.mkdir(parents=True, exist_ok=False)
        archive_created = True
        archived_files = []
        for name in registered:
            src = review / name
            if not src.is_file():
                continue
            dst = archive_dir / name
            shutil.move(str(src), str(dst))
            moved.append((dst, src))
            archived_files.append(file_info(dst))
        if manifest_path.is_file():
            shutil.copy2(manifest_path, archive_dir / manifest_path.name)
        atomic_write_json(archive_dir / '归档实物指纹.json', {
            'archived_at': now_iso(), 'files': archived_files,
            'unknown_review_items_left_at_original_entry': unknown,
        })

        # 2) 复制候选到工作区根（按 naming.docx_stem 命名）。dry-run 阶段的 compute_targets 已经
        #    拒绝了“同名但内容不同”的情况，这里仍做一次防御性复核（时间窗口内被人改动）。
        ws_docx = ws_pdf = None
        if ws:
            # 修复 confirm major#1（同类口子）：_confine 会 realpath 解析后再返回，若在那之后才
            # 查“是不是符号链接”，链接早被解引用、永远查不出来——必须趁 resolve 前先查未解析路径
            # 本身及各级父目录。
            _reject_symlink_chain(ws / f'{stem}.docx', '工作区根写入目标')
            _reject_symlink_chain(ws / f'{stem}.pdf', '工作区根写入目标')
            ws_docx = _confine(ws / f'{stem}.docx', [ws], '工作区根 docx 目标')
            ws_pdf = _confine(ws / f'{stem}.pdf', [ws], '工作区根 pdf 目标')
            for src, dst in ((docx_path, ws_docx), (pdf_path, ws_pdf)):
                if dst.exists():
                    if sha256_file(dst) == sha256_file(src):
                        continue  # 已是同内容，跳过（不算“覆盖”，也不记入 created）
                    raise Gate(f'工作区根已存在同名但内容不同的文件，拒绝覆盖：{dst}（应已在 write_targets 门挡住，此处是防御性复核）')
                shutil.copy2(src, dst)
                created.append(dst)

        # 3) 复制到审阅入口（此时旧登记文件已在第 1 步搬走，同名冲突不会发生）
        # 同上：先在 resolve 前查符号链接，再 _confine（否则 _confine 已经把链接解引用）。
        _reject_symlink_chain(review / f'{stem}.docx', '审阅入口写入目标')
        _reject_symlink_chain(review / f'{stem}.pdf', '审阅入口写入目标')
        rv_docx = _confine(review / f'{stem}.docx', [review], '审阅入口 docx 目标')
        rv_pdf = _confine(review / f'{stem}.pdf', [review], '审阅入口 pdf 目标')
        for src, dst in ((ws_docx or docx_path, rv_docx), (ws_pdf or pdf_path, rv_pdf)):
            is_new = not dst.exists()
            shutil.copy2(src, dst)
            if is_new:
                created.append(dst)
        if sha256_file(rv_docx) != docx_info['sha256'] or sha256_file(rv_pdf) != pdf_info['sha256']:
            raise Gate('复制到审阅入口后 SHA 核对不一致')

        # 4) 写新清单
        batch_m = re.search(r'\d+', str(args.batch))
        batch_label = f'batch{batch_m.group()}' if batch_m else f'batch{args.batch}'
        new_manifest = copy.deepcopy(manifest) if manifest else {}
        new_manifest.update({
            'copied_at': now_iso(), 'published_by': args.actor,
            'source_docx': str(ws_docx or docx_path), 'source_pdf': str(ws_pdf or pdf_path),
            'docx': str(rv_docx), 'docx_sha256': docx_info['sha256'], 'bytes': docx_info['bytes'],
            'pdf': str(rv_pdf), 'pdf_sha256': pdf_info['sha256'], 'pdf_pages': pdf_pages,
            'latest_batch': batch_label,
            'status': 'stage_review_copy_not_final',
        })
        # 修复 major#7：本次归档写进 previous_review_archive；source_state 显式指向中央状态文件；
        # 继承旧清单里本工具无法判定真伪的键（body_changed/verified 等）时标注来源，不假装是本次结论。
        carried_over = {k: v for k, v in (manifest or {}).items()
                        if k not in new_manifest and k not in ('validation', 'previous_review_archive', 'source_state')}
        if carried_over:
            new_manifest['carried_over_from_previous_manifest'] = sorted(carried_over)
            new_manifest.update(carried_over)
        new_manifest['previous_review_archive'] = str(archive_dir)
        new_manifest['source_state'] = str(central_path)
        new_manifest['validation'] = {
            'acceptance': {'path': str(Path(args.acceptance).resolve()), 'sha256': sha256_file(args.acceptance)},
            'same_version_binding': acc.get('same_version_binding'),
            'archive': {'path': str(archive_dir), 'files': archived_files, 'unknown_items_untouched': unknown},
            'central_state_backup': str(backup_dir),
        }
        atomic_write_json(manifest_path, new_manifest)

        # 5) 更新先看这里（有 --note 用其原文，没有则只写机器生成的最小链接页，不编造审阅说明）
        if args.note:
            note_text = Path(args.note).expanduser().read_text(encoding='utf-8')
        else:
            hint_tpl = prof.get('naming', {}).get('feedback_hint', '请按“批次＋PDF页码”提意见')
            hint_n = batch_m.group() if batch_m else str(args.batch)
            hint = render_template(hint_tpl, {'n': hint_n, 'rev': hint_n}, 'naming.feedback_hint') \
                if ('{n}' in hint_tpl or '{rev}' in hint_tpl) else hint_tpl
            note_text = (f'# {prof.get("title", "")} 审阅入口\n\n更新时间：{now_iso()}（发布者 {args.actor}）\n\n'
                         f'本轮发布未提供 --note，未生成审查说明正文（工具不编造教研结论）。\n\n'
                         f'- [打开Word]({rv_docx})\n- [打开同版PDF]({rv_pdf})\n\n{hint}\n')
        atomic_write_text(note_path, note_text)

        # 6) 更新中央状态（修复 major#7：补 review_entry/review_manifest/latest_rendered_*）
        fields = _cfg(prof, 'publish.central_state_fields')
        new_central = json.loads(central_path.read_text(encoding='utf-8'))
        if sha256_file(central_path) != central_before_sha:
            raise Gate('中央状态在写入过程中被外部改动，中止')
        old_head_sha = new_central.get(fields['working_head_sha256'])
        if old_head_sha != docx_info['sha256']:
            new_central[fields['previous_working_head']] = {
                'revision': new_central.get(fields['latest_batch']),
                'docx': new_central.get(fields['working_head']),
                'docx_sha256': old_head_sha,
                # 修复终审 minor（回执 fix5）：前身 publish_b52 与真实中央状态里
                # previous_working_head 都带 pdf_pages，本工具之前遗漏；取覆盖前的旧
                # latest_render_pages（下面几行才会把它改写成本批新页数，这里必须在改写之前取）。
                'pdf_pages': new_central.get(fields['latest_render_pages']),
            }
        new_central[fields['working_head']] = str(ws_docx or rv_docx)
        new_central[fields['working_head_sha256']] = docx_info['sha256']
        new_central[fields['working_head_bytes']] = docx_info['bytes']
        new_central[fields['latest_batch']] = new_manifest['latest_batch']
        new_central[fields['latest_render_sha256']] = docx_info['sha256']
        new_central[fields['latest_render_pages']] = pdf_pages
        new_central[fields['latest_rendered_docx_sha256']] = docx_info['sha256']
        new_central[fields['latest_rendered_pages']] = pdf_pages
        new_central[fields['review_entry']] = str(rv_docx)
        new_central[fields['review_manifest']] = str(manifest_path)
        lr = copy.deepcopy(new_central.get(fields['latest_render']) or {})
        lr.update({'docx': str(ws_docx or rv_docx), 'docx_sha256': docx_info['sha256'],
                   'pdf': str(ws_pdf or rv_pdf), 'pdf_sha256': pdf_info['sha256'], 'pages': pdf_pages})
        new_central[fields['latest_render']] = lr
        # 修复 r3verify major：前身 publish_b52 还更新 status 与 active_revision_round，本工具
        # 之前遗漏——latest_batch/working_head 已经是新批次时，status 与 active_revision_round
        # 仍是旧批次文字/旧字段会误导读中央状态判断当前轮次的主代理和 collab。
        # 书册配置若不写这两个字段名（自定义 central_state_fields 整体覆盖时可能没有），就跳过，
        # 并在计划/回执里列进“未更新字段”，不假装已经更新。
        not_updated_central_fields = []
        batch_n = batch_m.group() if batch_m else str(args.batch)
        if 'status' in fields:
            status_tpl = _cfg(prof, 'publish.central_state_status_template')
            new_status = render_template(status_tpl, {'n': batch_n, 'rev': batch_n}, 'publish.central_state_status_template') \
                if ('{n}' in status_tpl or '{rev}' in status_tpl) else status_tpl
            new_central[fields['status']] = new_status
        else:
            not_updated_central_fields.append('status')
        if 'active_revision_round' in fields:
            active_round = copy.deepcopy(new_central.get(fields['active_revision_round']) or {})
            active_round.update({
                'revision': new_manifest['latest_batch'], 'owner': args.actor,
                'docx': str(ws_docx or rv_docx), 'docx_sha256': docx_info['sha256'],
                'pdf': str(ws_pdf or rv_pdf), 'pdf_sha256': pdf_info['sha256'], 'pages': pdf_pages,
                'status': 'completed_for_human_review_not_final',
                # 修复终审 minor（回执 fix5）：之前 summary 沿用旧值，改批次后仍指向上一批的说明
                # 文件，误导读中央状态的人。这里改成指向"先看这里"——不管有没有给 --note，
                # 第 5 步都会把它更新成本轮内容（有 --note 用其原文，没有则是机器生成的最小
                # 链接页），是唯一保证"指向本轮说明"的文件。
                'summary': str(note_path),
            })
            new_central[fields['active_revision_round']] = active_round
        else:
            not_updated_central_fields.append('active_revision_round')
        new_central[fields['updated_at']] = now_iso()
        atomic_write_json(central_path, new_central)

        # 7) 写后复核（修复 major#4：复核放在写回执之前，回执只在复核通过后才写，
        #    不留 status=PROMOTED 但实际半成品的回执；修复代码与文档细节：manifest 复核
        #    改成有意义的比较，而不是文件与自身比较的恒真式）
        recheck = {
            'review_docx_sha256_ok': sha256_file(rv_docx) == docx_info['sha256'],
            'review_pdf_sha256_ok': sha256_file(rv_pdf) == pdf_info['sha256'],
            'manifest_matches_candidate': (json.loads(manifest_path.read_text(encoding='utf-8')).get('docx_sha256') == docx_info['sha256']
                                            and json.loads(manifest_path.read_text(encoding='utf-8')).get('pdf_sha256') == pdf_info['sha256']),
            'central_state_head_ok': json.loads(central_path.read_text(encoding='utf-8')).get(fields['working_head_sha256']) == docx_info['sha256'],
            'unknown_items_untouched': all((review / n).exists() for n in unknown),
        }
        if not all(recheck.values()):
            raise Gate(f'写后复核未全部通过：{recheck}')

        # 8) 晋升回执（复核通过后才写，是本次事务的最后一步）
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt = {
            'status': 'PROMOTED', 'at': now_iso(), 'actor': args.actor, 'batch': args.batch,
            'archive': str(archive_dir), 'backup': str(backup_dir),
            'new_docx': str(rv_docx), 'new_docx_sha256': docx_info['sha256'],
            'new_pdf': str(rv_pdf), 'new_pdf_sha256': pdf_info['sha256'], 'pdf_pages': pdf_pages,
            'recheck': recheck,
            'central_state_fields_not_updated': not_updated_central_fields,
        }
        atomic_write_json(receipt_path, receipt)
        receipt_written = True
        return {'receipt': str(receipt_path), 'archive': str(archive_dir),
                'backup': str(backup_dir), 'recheck': recheck,
                'central_state_fields_not_updated': not_updated_central_fields}
    except GuardRefusal as e:
        rollback_note, rollback_incomplete = _rollback(
            central_path, manifest_path, note_path, receipt_path, backup_dir,
            central_before_sha, manifest_before_sha, note_before_sha, receipt_before_sha,
            moved, created, archive_dir, archive_created, receipt_written, archive_new_ancestors)
        if rollback_incomplete:
            # 修复终审 major#2：回滚本身也失败时不能再包成 GuardRefusal（退出 3）文案——那条文案
            # 的措辞是"已回滚"，会误导人以为只是拒绝写出、什么都没动过。改用 RollbackIncomplete
            # （main() 映射到新退出码 4），逐项列出未恢复的路径与原因。
            raise RollbackIncomplete(str(e), rollback_incomplete, rollback_note)
        raise GuardRefusal(f'{e}；已回滚：{rollback_note}')
    except BaseException as e:
        rollback_note, rollback_incomplete = _rollback(
            central_path, manifest_path, note_path, receipt_path, backup_dir,
            central_before_sha, manifest_before_sha, note_before_sha, receipt_before_sha,
            moved, created, archive_dir, archive_created, receipt_written, archive_new_ancestors)
        if rollback_incomplete:
            # 修复终审 major#2：以前 _rollback 内部（shutil.move/copy2 缺 try）再抛一次异常时，
            # 这里的 `except BaseException` 根本接不到——异常直接冒出 do_apply/run，落进 main() 的
            # 通用 `except Exception` 分支，打印成"输入或配置错误"。现在 _rollback 自己不再抛出，
            # 只通过 incomplete 列表报告，这里据此改抛 RollbackIncomplete（退出码 4），不再是
            # Gate（退出码 2，"发布中途失败，已回滚"——已回滚这个措辞在回滚不完整时是错的）。
            raise RollbackIncomplete(f'{type(e).__name__}: {e}', rollback_incomplete, rollback_note)
        raise Gate(f'发布中途失败，已回滚：{type(e).__name__}: {e}；回滚详情：{rollback_note}')


def _rollback(central_path, manifest_path, note_path, receipt_path, backup_dir,
              central_before_sha, manifest_before_sha, note_before_sha, receipt_before_sha,
              moved, created, archive_dir, archive_created, receipt_written, archive_new_ancestors=()):
    """修复 blocker#2 + major#4：顺序改成先撤销本次写入（含晋升回执），再把归档文件移回原位，
    最后整体删除本次新建的归档目录；同名场景下"移回"不会再被"随后又被删"打断。
    回滚完成后逐一核对 SHA，回滚不完整时在返回文案里明确写出来，不假装“已复原”。
    修复 r3verify blocker：archive_dir 只有在 archive_created 为真（本次 mkdir(exist_ok=False)
    真正成功）时才可能被删除——archive_dir 这个局部变量在 do_apply 里赋值早于“是否已存在”的判定，
    若该判定失败（发布前就有同名历史归档），archive_dir 指向的是别人的旧归档，绝不能 rmtree。

    修复终审 major#2（回执 fix5）：以前只有 rmtree（第 3 步）和"删除新建文件"（第 1 步）两处
    有 try/except；第 2 步的 shutil.move（把归档文件移回）和第 4 步的 shutil.copy2（从备份恢复
    中央状态/清单/先看这里）完全没有保护——回滚途中只要再有一次 IO 故障（比如磁盘满），这两处
    会直接把异常抛出 _rollback 本身，后面几步（包括第 5 步核对、乃至整个"回滚不完整"汇总）都不会
    跑，异常会一路冒到 main() 的通用 `except Exception` 分支，打印成"输入或配置错误"——让人以为
    失败发生在任何写入之前。现在每一步（每一次 move / copy2 / unlink / rmtree）各自 try，失败
    只记入 incomplete 并继续跑下一步，_rollback 本身保证不再抛出异常。

    返回 (steps_text, incomplete_list)：incomplete_list 非空时，调用方（do_apply）改为抛
    `RollbackIncomplete`（main() 里映射到退出码 4，见文件头“退出码”一节），不再假装退出码 2/3
    的"已回滚"文案。"""
    steps = []
    incomplete = []

    # 1) 先撤销本次这一轮写出的新文件（含新审阅入口 docx/pdf、工作区根新副本、晋升回执）。
    #    这一步必须先于"移回归档"执行：新 stem 与旧登记文件同名时，只有先删掉这里的新内容，
    #    原路径才会空出来，移回才能成功。
    for p in list(created):
        try:
            if p.is_file():
                p.unlink()
                steps.append(f'删除新建 {p}')
        except OSError as e:
            steps.append(f'警告：删除新建 {p} 失败：{e}')
            incomplete.append(f'未删除新建文件({p})：{e}')

    if receipt_written or receipt_path.is_file():
        try:
            if receipt_before_sha is None:
                if receipt_path.is_file():
                    receipt_path.unlink()
                    steps.append(f'删除本次新写的晋升回执 {receipt_path}')
            else:
                bak = backup_dir / receipt_path.name
                if bak.is_file():
                    shutil.copy2(bak, receipt_path)
                    steps.append(f'恢复晋升回执 {receipt_path}')
        except OSError as e:
            steps.append(f'警告：回执回滚失败：{e}')
            incomplete.append(f'晋升回执未能回滚({receipt_path})：{e}')

    # 2) 把归档文件移回原位（此时原路径应已因第 1 步腾空）。注意：先看这里/审阅清单即使也在
    #    registered 里被物理搬进过归档目录，它们各自有独立的 backup_dir 备份+还原（第 4 步），
    #    不依赖这里的“移回”；这里的 exists() 早于第 4 步执行，此时它们多半已被步骤 5 写过新内容，
    #    "已存在" 是预期状态，不算回滚不完整——只有 docx/pdf 这类没有独立备份机制的文件才靠这一步。
    #    修复终审 major#2：shutil.move 本身现在有 try/except，失败只记入 incomplete、继续下一个
    #    文件，不再让整个 _rollback 在这里中断。
    backed_up_separately = {central_path, manifest_path, note_path}
    for dst_in_archive, original_path in moved:
        if not dst_in_archive.is_file():
            continue
        if original_path in backed_up_separately:
            continue  # 交给下面第 4 步用 backup_dir 还原，归档里的这份留给第 3 步整体删除
        if original_path.exists():
            incomplete.append(str(original_path))
            steps.append(f'警告：无法移回 {original_path}（目标已存在，回滚不完整）')
            continue
        try:
            shutil.move(str(dst_in_archive), str(original_path))
            steps.append(f'移回 {original_path}')
        except OSError as e:
            steps.append(f'警告：移回 {original_path} 失败：{e}')
            incomplete.append(f'未移回({original_path})：{e}')

    # 3) 整个删除本次新建的归档目录（含清单副本、归档实物指纹.json 等，不只在“空目录”时才删）。
    #    只有 archive_created 为真——即本次 mkdir(exist_ok=False) 确实新建了这个目录——才允许
    #    rmtree；否则说明失败发生在创建归档目录之前（例如“归档目录已存在”），archive_dir 指向
    #    的是发布前就有的历史归档，绝不能删，原样留着。
    # 修复终审 major#2（回执 fix5，故障注入 F5e 才发现）：上面第 2 步某个文件"移回"失败时，
    # 它此刻仍然原样躺在 archive_dir 里——这是它唯一的副本（docx/pdf 没有独立的 backup_dir
    # 备份，只是被"移动"进了归档）。如果这里不分青红皂白地对 archive_dir 做 rmtree，会把这个
    # 刚刚才因为"移不回去"而记入 incomplete 的文件连同归档目录一起删掉，回滚不完整就从"文件还在
    # 归档里，人工能找回"变成了"文件彻底丢了"。所以：archive_dir 里只要还留着任何一个未能移回
    # 原位的登记文件，就不删——原样保留整个归档目录作为人工找回的位置，并把这一点写进 steps。
    archive_has_unrecovered = any(
        dst_in_archive.is_file() for dst_in_archive, original_path in moved
        if original_path not in backed_up_separately)
    if not archive_created:
        if archive_dir and archive_dir.exists():
            steps.append(f'归档目录 {archive_dir} 不是本次新建，原样保留，未删除')
    elif archive_has_unrecovered:
        steps.append(f'归档目录 {archive_dir} 里还有未能移回原位的文件，保留整个目录不删，供人工核查/找回')
    elif archive_dir and archive_dir.exists():
        try:
            shutil.rmtree(archive_dir)
            steps.append(f'删除本次新建的归档目录 {archive_dir}')
        except OSError as e:
            steps.append(f'警告：归档目录 {archive_dir} 未能完全删除：{e}')
            incomplete.append(f'归档目录未删净({archive_dir})：{e}')

    # 3b) 修复终审 minor（回执 fix5）：archive_dir.mkdir(parents=True) 顺带新建的中间目录
    #     （archive_new_ancestors，由深到浅）此前回滚不会清理，沙盒全树会多出这些空目录。
    #     只删本次新建的：do_apply 记录时已经排除了发布前就存在的祖先，这里逐个 rmdir（非
    #     rmtree），确保只删空目录、不误删别的内容；某一级删不掉（非空/权限）就停止往上删，
    #     并记入 incomplete，不强行 rmtree 掉可能混入的其他内容。
    for anc in archive_new_ancestors:
        try:
            if anc.exists():
                if not any(anc.iterdir()):
                    anc.rmdir()
                    steps.append(f'删除本次新建的中间目录 {anc}')
                else:
                    steps.append(f'警告：本次新建的中间目录 {anc} 非空，未删除（可能混入其他内容），停止继续向上删')
                    incomplete.append(f'中间目录未删净({anc})：目录非空')
                    break
        except OSError as e:
            steps.append(f'警告：删除中间目录 {anc} 失败：{e}')
            incomplete.append(f'中间目录未删净({anc})：{e}')
            break

    # 4) 恢复中央状态 / 清单 / 先看这里。修复终审 major#2：shutil.copy2 现在有 try/except，
    #    某一份恢复失败不影响其余两份继续恢复，也不会打断后面第 5 步的核对。
    for p, before_sha, name in ((central_path, central_before_sha, central_path.name),
                                 (manifest_path, manifest_before_sha, manifest_path.name),
                                 (note_path, note_before_sha, note_path.name)):
        bak = backup_dir / name
        if before_sha is None:
            continue
        if bak.is_file():
            try:
                shutil.copy2(bak, p)
                steps.append(f'恢复 {p}')
            except OSError as e:
                steps.append(f'警告：恢复 {p} 失败：{e}')
                incomplete.append(f'{p}：恢复失败（{e}）')
        else:
            try:
                changed = p.is_file() and sha256_file(p) != before_sha
            except OSError as e:
                steps.append(f'警告：核对 {p} 是否需要恢复时读取失败：{e}')
                incomplete.append(f'{p}：回滚核对读失败（{e}）')
                continue
            if changed:
                incomplete.append(str(p))
                steps.append(f'警告：{p} 无备份可恢复，回滚不完整')

    # 5) 逐一核对：回滚后是否真的等于发布前，不一致就在返回文案里明确报告（不含糊）。
    # 修复 confirm minor：sha256_file 读取失败（回滚核对读故障）要计入"回滚不完整"，不能让
    # OSError 冒出 _rollback 被外层当成"输入或配置错误"（退出码 2），且不能因此跳过其余项。
    for p, before_sha, label in ((central_path, central_before_sha, '中央状态'),
                                  (manifest_path, manifest_before_sha, '审阅清单'),
                                  (note_path, note_before_sha, '先看这里')):
        if before_sha is None:
            continue
        try:
            now_sha = sha256_file(p) if p.is_file() else None
        except OSError as e:
            steps.append(f'警告：核对 {p} 回滚结果时读取失败：{e}')
            incomplete.append(f'{label}({p})：回滚核对读失败（{e}）')
            continue
        if now_sha != before_sha:
            incomplete.append(f'{label}({p})')
    for original_path in [o for _, o in moved if o not in backed_up_separately]:
        if not original_path.exists():
            incomplete.append(f'未移回({original_path})')

    incomplete = sorted(set(incomplete))
    if incomplete:
        steps.append('回滚不完整，以下未能恢复到发布前状态，需要人工核查：' + '、'.join(incomplete))

    note_text = '；'.join(steps) if steps else '（无需改动，失败发生在任何写入之前）'
    return note_text, incomplete




def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--profile', required=True)
    ap.add_argument('--batch', required=True)
    ap.add_argument('--docx', required=True)
    ap.add_argument('--pdf', required=True)
    ap.add_argument('--acceptance', required=True)
    ap.add_argument('--actor', required=True)
    ap.add_argument('--note')
    ap.add_argument('--label')
    ap.add_argument('--health', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--report')
    ap.add_argument('--debug', action='store_true')
    args = ap.parse_args(argv)

    try:
        plan, code = run(args)
    except RollbackIncomplete as e:
        # 修复终审 major#2（回执 fix5）：新退出码 4，见文件头“退出码”一节。不能落进下面
        # `except Exception` 的"输入或配置错误"——那会让人误以为失败发生在任何写入之前；这里
        # 的意思是“已经动手写了，中途失败，回滚也没能完全复原，需要人工核查磁盘现状”。
        msg = (f'发布中途失败：{e.original}；回滚不完整，需要人工核查：' + '、'.join(e.incomplete))
        print(msg, file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        if args.report:
            try:
                prof = load_profile(args.profile)
            except Exception:
                prof = None
            report_obj = {
                'tool': TOOL_NAME, 'version': TOOL_VERSION, 'mode': 'apply',
                'error': msg, 'original_error': e.original,
                'rollback_incomplete': e.incomplete, 'rollback_log': e.note,
            }
            try:
                out = dl.guard_write(args.report, prof, inputs=[args.docx, args.pdf, args.acceptance], kind='.json', overwrite=True)
                out.write_text(json.dumps(report_obj, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
            except dl.GuardError as ge:
                print(f'（另外）拒绝写出 --report：{ge}', file=sys.stderr)
        return 4
    except GuardRefusal as e:
        print(f'拒绝写出：{e}', file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 3
    except Gate as e:
        print(f'门未通过，中止：{e}', file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 2
    except Exception as e:
        print(f'输入或配置错误：{type(e).__name__}: {e}', file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 2

    text = json.dumps(plan, ensure_ascii=False, indent=2, default=str)
    print(text)
    if args.report:
        try:
            prof = load_profile(args.profile)
        except Exception:
            prof = None
        try:
            out = dl.guard_write(args.report, prof, inputs=[args.docx, args.pdf, args.acceptance], kind='.json', overwrite=True)
            out.write_text(text, encoding='utf-8')
        except dl.GuardError as e:
            # 修复 minor：--report 路径被 guard_write 拒绝时不应打印 traceback、退出码 1；
            # 与其余“拒绝写出”场景一致：中文提示、退出码 3。计划已经打印在上面的 stdout 里了。
            print(f'拒绝写出 --report：{e}', file=sys.stderr)
            if args.debug:
                traceback.print_exc()
            return 3
    return code


if __name__ == '__main__':
    sys.exit(main())
