#!/usr/bin/env python3
"""Inspect actual BX2 blocks; maintain counts/numbering and cached PAGEREF pages.

Does not generate teaching text, choose classification, or promote a revision.
Only document.xml changes; all other ZIP members remain byte-identical.
"""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from lxml import etree as E

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
Q = lambda n: '{' + W + '}' + n
COUNT = re.compile(r'（(\d+)题）$')
EXAMPLE = re.compile(r'^(?:拓展)?例题\s*(\d+)\s*(.+)$')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text(node):
    return ''.join(node.xpath('.//w:t/text()', namespaces=NS))


def style(node):
    vals = node.xpath('./w:pPr/w:pStyle/@w:val', namespaces=NS)
    return vals[0] if vals else ''


def anchor(node):
    names = node.xpath('./w:bookmarkStart/@w:name', namespaces=NS)
    return next((n for n in names if n.startswith('BX2')), names[0] if names else None)


def question_key(title):
    """Observed heading identity for comparison; full source registry remains authoritative."""
    m = EXAMPLE.match(title)
    title = m.group(2) if m else title
    return re.sub(r'\s+', '', title).replace('（跨模块）', '')


def replace_span(node, start, end, replacement):
    """Edit character span without rebuilding runs or removing bookmarks/hyperlinks."""
    assert 0 <= start <= end <= len(text(node))
    pos = 0
    inserted = False
    for t in node.xpath('.//w:t', namespaces=NS):
        s = t.text or ''
        left, right = pos, pos + len(s)
        pos = right
        if right <= start or left >= end:
            continue
        a, b = max(0, start-left), min(len(s), end-left)
        t.text = s[:a] + (replacement if not inserted else '') + s[b:]
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        inserted = True
    assert inserted, (start, end)


def load(path):
    z = zipfile.ZipFile(path)
    return z, E.fromstring(z.read('word/document.xml'))


def inventory(root):
    nodes = list(root.find('w:body', NS))
    scopes, all_examples = [], []
    for i, node in enumerate(nodes):
        s, t = style(node), text(node)
        m = EXAMPLE.match(t)
        if m and s.startswith('Heading'):
            all_examples.append({'body_index': i, 'anchor': anchor(node),
                                 'key': question_key(t), 'title': t})
        c = COUNT.search(t)
        if not c or not (s == 'HBMethod' or s.startswith('Heading')):
            continue
        examples, end = [], len(nodes)
        for j in range(i+1, len(nodes)):
            ss, tt = style(nodes[j]), text(nodes[j])
            mm = EXAMPLE.match(tt)
            if mm and ss.startswith('Heading'):
                examples.append({'body_index': j, 'title': tt,
                                 'number': int(mm.group(1)), 'key': question_key(tt)})
                continue
            # Count-bearing categories and non-example outline headings delimit scopes.
            if ss == 'HBMethod' or ss.startswith('Heading'):
                end = j
                break
        keys = [x['key'] for x in examples]
        scopes.append({'body_index': i, 'anchor': anchor(node), 'title': t,
                       'end_body_index': end, 'printed_count': int(c.group(1)),
                       'actual_blocks': len(examples), 'unique_questions': len(set(keys)),
                       'duplicate_keys': sorted({k for k in keys if keys.count(k)>1}),
                       'examples': examples})
    return {'scopes': scopes, 'example_blocks': all_examples,
            'example_block_count': len(all_examples),
            'unique_example_heading_keys': len({x['key'] for x in all_examples})}


def refresh(root, selected=None, renumber=False):
    data = inventory(root)
    nodes = list(root.find('w:body', NS))
    changes = []
    for scope in data['scopes']:
        if selected and scope['anchor'] not in selected:
            continue
        # A duplicate needs human source/placement judgment, never silently count or remove it.
        if scope['duplicate_keys']:
            raise ValueError('Duplicate within classification: ' + scope['title'])
        if not scope['examples']:
            raise ValueError('Empty or unrecognized classification: ' + scope['title'])
        p = nodes[scope['body_index']]
        m = COUNT.search(text(p))
        old, new = m.group(1), str(scope['unique_questions'])
        if old != new:
            replace_span(p, m.start(1), m.end(1), new)
            changes.append({'kind': 'count', 'anchor': scope['anchor'], 'old': old, 'new': new})
        for number, ex in enumerate(scope['examples'] if renumber else [], 1):
            if number != ex['number']:
                p = nodes[ex['body_index']]
                m = EXAMPLE.match(text(p))
                replace_span(p, m.start(1), m.end(1), str(number))
                changes.append({'kind': 'example_number', 'key': ex['key'],
                                'old': ex['number'], 'new': number})
    if selected:
        found = {s['anchor'] for s in data['scopes']}
        assert set(selected) <= found, 'Unknown classification bookmark'
    return changes


def sync_pages(root, pdf):
    from pypdf import PdfReader
    reader = PdfReader(pdf)
    norm = lambda s: re.sub(r'\s+', '', s)
    outlines = {}
    def walk(items):
        for x in items:
            if isinstance(x, list):
                walk(x)
            else:
                outlines.setdefault(norm(x.title), []).append(reader.get_destination_page_number(x)+1)
    walk(reader.outline)
    changes = []
    for field in root.xpath('//w:fldSimple[contains(@w:instr,"PAGEREF")]', namespaces=NS):
        name = re.search(r'PAGEREF\s+(\S+)', field.get(Q('instr'))).group(1)
        targets = root.xpath('//w:bookmarkStart[@w:name=$name]', namespaces=NS, name=name)
        assert len(targets) == 1, (name, len(targets))
        p = targets[0]
        while p.tag != Q('p'):
            p = p.getparent()
        title = norm(text(p))
        pages = outlines.get(title, [])
        assert len(pages) == 1, (name, title, pages)
        vals = field.xpath('.//w:t', namespaces=NS)
        assert len(vals) == 1, (name, len(vals))
        old, new = vals[0].text, str(pages[0])
        if old != new:
            vals[0].text = new
            changes.append({'kind': 'page_cache', 'anchor': name, 'old': old, 'new': new})
    return changes


def write(z, root, dest):
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as out:
        for info in z.infolist():
            data = (E.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
                    if info.filename == 'word/document.xml' else z.read(info.filename))
            out.writestr(info, data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['inspect', 'refresh', 'sync-pages'])
    p.add_argument('docx', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--expected-sha')
    p.add_argument('--scope', action='append', help='Stable classification bookmark; repeat as needed')
    p.add_argument('--renumber', action='store_true', help='Renumber only explicitly selected scopes')
    p.add_argument('--pdf', type=Path)
    a = p.parse_args()
    original_sha = sha(a.docx)
    if a.command != 'inspect':
        assert a.expected_sha == original_sha, 'Input differs from expected parent'
        assert a.output and a.output.resolve() != a.docx.resolve(), 'Write a separate candidate'
        assert not a.output.exists(), 'Output already exists; choose a new candidate'
    z, root = load(a.docx)
    report = {'input': str(a.docx), 'input_sha256': original_sha, 'command': a.command}
    if a.command == 'inspect':
        report.update(inventory(root))
    else:
        if a.command == 'refresh':
            assert not a.renumber or a.scope, 'Renumbering needs explicit affected scopes'
            changes = refresh(root, a.scope, a.renumber)
        else:
            assert a.pdf and a.pdf.is_file(), 'A PDF rendered from this candidate is required'
            changes = sync_pages(root, a.pdf)
            report['pdf_sha256'] = sha(a.pdf)
        write(z, root, a.output)
        report.update({'changes': changes, 'output': str(a.output), 'output_sha256': sha(a.output)})
    a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('scopes','example_blocks','changes')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
