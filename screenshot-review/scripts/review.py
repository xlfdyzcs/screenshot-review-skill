#!/usr/bin/env python3
"""Build and serve portable screenshot reviews using only Python's standard library."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import struct
import sys
import zipfile
from datetime import date
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
SIDES = ('before', 'after')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def png_size(path):
    with Path(path).open('rb') as stream:
        header = stream.read(24)
    if header[:8] != b'\x89PNG\r\n\x1a\n' or header[12:16] != b'IHDR':
        raise ValueError(f'Expected a PNG screenshot: {path}')
    return struct.unpack('>II', header[16:24])


def safe_source(base, name):
    if not isinstance(name, str) or not name:
        raise ValueError('Screenshot file must be a nonempty relative path')
    path = (base / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(base.resolve()):
        raise ValueError(f'Screenshot path escapes the manifest directory: {name}')
    if not path.is_file():
        raise ValueError(f'Screenshot does not exist: {path}')
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_viewer(data):
    meta = data['review']
    template = (ASSETS / 'review.html').read_text(encoding='utf-8')
    substitutions = {
        '__TITLE__': html.escape(meta['title']), '__DATE__': html.escape(str(meta['date'])),
        '__BEFORE_LABEL__': html.escape(meta['beforeLabel']),
        '__AFTER_LABEL__': html.escape(meta['afterLabel']),
        '__STYLE__': (ASSETS / 'review.css').read_text(encoding='utf-8'),
        '__SCRIPT__': (ASSETS / 'review-state.js').read_text(encoding='utf-8') + '\n' + (ASSETS / 'review.js').read_text(encoding='utf-8'),
        '__DATA__': json.dumps(data, ensure_ascii=False).replace('<', r'\u003c'),
    }
    for token, value in substitutions.items():
        template = template.replace(token, value)
    return template


def validate(root):
    root = Path(root).resolve()
    data = read_json(root / 'manifest.json')
    count = 0
    for case in data['cases']:
        for side in SIDES:
            for shot in case[side]:
                path = safe_source(root, shot['file'])
                if list(png_size(path)) != shot['pixelSize'] or digest(path) != shot['sha256']:
                    raise ValueError(f'Screenshot integrity check failed: {shot["file"]}')
                count += 1
    if not (root / 'index.html').is_file():
        raise ValueError('Review has no index.html')
    return {'cases': len(data['cases']), 'pairs': data['pairs'], 'screenshots': count}


def refresh(root):
    root = Path(root).resolve()
    result = validate(root)
    data = read_json(root / 'manifest.json')
    temporary = root / 'index.html.new'
    temporary.write_text(render_viewer(data), encoding='utf-8')
    temporary.replace(root / 'index.html')
    return {**result, 'output': str(root), 'updated': 'viewer only'}


def bundle(root, target):
    root, target = Path(root).resolve(), Path(target).resolve()
    if target.is_relative_to(root):
        raise ValueError('ZIP must be outside the review directory')
    if target.exists():
        raise ValueError(f'Archive already exists; choose a new revision: {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(root).as_posix())
    with zipfile.ZipFile(target) as archive:
        if archive.testzip():
            raise ValueError('ZIP integrity check failed')


def build(args):
    source = args.manifest.resolve()
    data = read_json(source)
    meta = data.get('review', {})
    project = args.project or meta.get('project')
    revision = args.revision or meta.get('revision')
    if not project or not revision:
        raise ValueError('Set --project and --revision, or review.project/revision in the manifest')
    for value in (project, revision):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', value):
            raise ValueError('Project and revision must use letters, digits, dots, hyphens or underscores')
    meta.update({
        'project': project,
        'revision': revision,
        'title': args.title or meta.get('title') or f'{project} · {revision} · 截图对照',
        'date': args.date or meta.get('date') or data.get('version') or date.today().isoformat(),
        'beforeLabel': args.before_label or meta.get('beforeLabel', '修改前'),
        'afterLabel': args.after_label or meta.get('afterLabel', '修改后'),
        'captureNote': args.capture_note if args.capture_note is not None else meta.get('captureNote', '实际页面截图；采集环境与验证范围见各项备注。'),
        'storageKey': args.storage_key or meta.get('storageKey') or f'screenshot-review:{project}:{revision}',
    })
    cases = data.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('Manifest must contain a nonempty cases array')
    ids, screenshots = set(), []
    normalized = []
    for item in cases:
        case = dict(item)
        case_id = case.get('id', '')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', case_id) or case_id in ids:
            raise ValueError(f'Invalid or duplicate case id: {case_id}')
        ids.add(case_id)
        if not case.get('title'):
            raise ValueError(f'Case needs a title: {case_id}')
        case.setdefault('group', '页面与状态')
        case.setdefault('note', '')
        case.setdefault('width', '?')
        case.setdefault('height', '?')
        for side in SIDES:
            shots = item.get(side, [])
            if not isinstance(shots, list):
                raise ValueError(f'{case_id}.{side} must be an array')
            case[side] = []
            for index, raw in enumerate(shots):
                shot = {'file': raw} if isinstance(raw, str) else dict(raw)
                path = safe_source(source.parent, shot.get('file'))
                pixel_size = list(png_size(path))
                target = f'raw/{side}/{case_id}-{index + 1:02}.png'
                case[side].append({**shot, 'file': target, 'page': index + 1,
                                   'sha256': digest(path), 'pixelSize': pixel_size})
                screenshots.append((path, target))
        if not case['before'] and not case['after']:
            raise ValueError(f'Case needs at least one screenshot: {case_id}')
        normalized.append(case)
    pdf = args.pdf.resolve() if args.pdf else None
    if pdf and (not pdf.is_file() or pdf.read_bytes()[:5] != b'%PDF-'):
        raise ValueError('PDF must be an existing valid PDF artifact')
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f'Output is not empty; create a new revision: {output}')
    if args.zip and args.zip.exists():
        raise ValueError(f'Archive already exists: {args.zip}')
    if args.zip and args.zip.resolve().is_relative_to(output):
        raise ValueError('ZIP must be outside the review directory')
    output.mkdir(parents=True, exist_ok=True)
    for path, target in screenshots:
        destination = output / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    meta['pdfFile'] = 'review.pdf' if pdf else None
    if pdf:
        shutil.copy2(pdf, output / 'review.pdf')
    data = {**data, 'version': meta['date'], 'review': meta, 'cases': normalized,
            'pairs': sum(max(len(case[s]) for s in SIDES) for case in normalized)}
    (output / 'manifest.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'index.html').write_text(render_viewer(data), encoding='utf-8')
    (output / 'README.md').write_text(
        f'# {meta["title"]}\n\n左：{meta["beforeLabel"]}；右：{meta["afterLabel"]}。\n\n'
        '双击 index.html 可离线打开；整个目录必须一起保留。\n'
        '批注按项目和版本保存在当前浏览器；使用“导出修改意见”发送 Markdown，'
        '使用“备份批注”保存 JSON，以便换机器或端口后导入恢复。\n'
        '长页按原始滚动分段；某侧无截图会明确说明，不补造对照图。\n\n'
        f'{meta["captureNote"]}\n', encoding='utf-8')
    result = validate(output)
    if args.zip:
        bundle(output, args.zip)
    return {**result, 'output': str(output), 'zip': str(args.zip) if args.zip else None}


class ReviewHandler(SimpleHTTPRequestHandler):
    """Serve only the requested artifact; reject symlink and parent escapes."""

    def send_head(self):
        path = Path(self.translate_path(self.path)).resolve()
        root = Path(self.directory).resolve()
        if not path.is_relative_to(root) or any(part.startswith('.') for part in path.relative_to(root).parts):
            self.send_error(403)
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404)
        return None


def serve(args):
    root = args.root.resolve()
    validate(root)
    with ThreadingHTTPServer(('127.0.0.1', args.port), partial(ReviewHandler, directory=str(root))) as server:
        print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}/', 'root': str(root)}), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    builder = commands.add_parser('build', help='Build a standalone review from PNG paths and case metadata')
    builder.add_argument('--manifest', type=Path, required=True)
    builder.add_argument('--output', type=Path, required=True)
    for name in ['project', 'revision', 'title', 'date', 'before-label', 'after-label', 'capture-note', 'storage-key']:
        builder.add_argument('--' + name)
    builder.add_argument('--pdf', type=Path, help='Include an already generated and checked PDF')
    builder.add_argument('--zip', type=Path)
    server = commands.add_parser('serve', help='Serve one saved review on loopback; Ctrl+C stops it')
    server.add_argument('--root', type=Path, required=True)
    server.add_argument('--port', type=int, default=0,
                        help='Local port; default 0 selects an available port')
    checker = commands.add_parser('validate', help='Verify screenshot sizes, hashes and artifact structure')
    checker.add_argument('--root', type=Path, required=True)
    refresher = commands.add_parser('refresh', help='Update only the viewer, preserving screenshots, metadata and annotation identity')
    refresher.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'serve':
            serve(args)
        else:
            result = build(args) if args.command == 'build' else refresh(args.root) if args.command == 'refresh' else validate(args.root)
            print(json.dumps(result, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'Review error: {error}\n')


if __name__ == '__main__':
    main()
