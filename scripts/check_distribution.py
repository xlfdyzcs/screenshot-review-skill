#!/usr/bin/env python3
"""Validate the explicit source and skill-archive distribution boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import struct
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SKILL_FILES = frozenset({
    'SKILL.md', 'agents/openai.yaml', 'assets/review.html', 'assets/review.css',
    'assets/review.js', 'assets/review-state.js', 'references/capture.md',
    'scripts/review.py', 'scripts/open_review.ps1',
})
DOCUMENTATION_IMAGES = frozenset({
    'docs/images/compare-desktop.jpg', 'docs/images/annotations.jpg',
    'docs/images/overlay.jpg', 'docs/images/overview.jpg',
    'docs/images/mobile-review.jpg', 'docs/images/mobile-notes.jpg',
})
SOURCE_FILES = frozenset({
    '.gitignore', '.gitattributes', '.github/workflows/verify.yml',
    'README.md', 'VERSION', 'CONTRIBUTING.md', 'docs/USAGE.md', 'docs/PRIVACY.md',
    'examples/create_demo.py', 'scripts/check_distribution.py',
    'scripts/build_release.py', 'tests/test_review.py',
    'tests/test_review_state.cjs', 'tests/test_distribution.py',
    'examples/fictional-app.html', 'docs/SCREENSHOTS.md', 'docs/images/provenance.json',
}) | frozenset('screenshot-review/' + name for name in SKILL_FILES) | DOCUMENTATION_IMAGES
GENERATED_DIRS = frozenset({'.git', '__pycache__', '.venv', 'build', 'output', 'dist', '.review-server'})


def validate_text(name, content):
    if len(content) > 150_000:
        raise ValueError(f'Oversized distribution file: {name}')
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError as error:
        raise ValueError(f'Only UTF-8 text is distributed: {name}') from error
    if '\0' in text:
        raise ValueError(f'Binary content: {name}')
    checks = {
        'embedded image or PDF': r'data:(?:image/[^;,\s]+|application/pdf)[;,]',
        'personal user directory': r'(?:[A-Za-z]:[\\/]Users[\\/][A-Za-z0-9_.-]+[\\/]|/(?:Users|home)/[A-Za-z0-9_.-]+/)',
        'private key material': r'-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----',
        'inline binary payload': r'[A-Za-z0-9+/]{2000,}={0,2}',
    }
    for reason, pattern in checks.items():
        if re.search(pattern, text, re.IGNORECASE):
            raise ValueError(f'{reason} in {name}')


def safe_member(name):
    path = PurePosixPath(name)
    return not path.is_absolute() and '..' not in path.parts and '\\' not in name and name == path.as_posix()


def jpeg_size(content):
    if len(content) > 2_000_000 or not content.startswith(b'\xff\xd8') or not content.endswith(b'\xff\xd9'):
        raise ValueError('Expected a bounded JPEG documentation screenshot')
    offset, size = 2, None
    while offset < len(content):
        if content[offset] != 0xff:
            raise ValueError('Invalid JPEG marker')
        while offset < len(content) and content[offset] == 0xff:
            offset += 1
        if offset >= len(content):
            raise ValueError('Truncated JPEG')
        marker = content[offset]
        offset += 1
        if marker in (0xe1, 0xed, 0xfe):
            raise ValueError('Documentation screenshot contains EXIF/IPTC/comment metadata')
        if marker == 0xda:
            if size is None:
                raise ValueError('JPEG has no dimensions')
            return size
        if offset + 2 > len(content):
            raise ValueError('Truncated JPEG segment')
        length = struct.unpack('>H', content[offset:offset + 2])[0]
        if length < 2 or offset + length > len(content):
            raise ValueError('Invalid JPEG segment length')
        if marker in (0xc0, 0xc1, 0xc2):
            if length < 8:
                raise ValueError('Invalid JPEG frame')
            height, width = struct.unpack('>HH', content[offset + 3:offset + 7])
            size = [width, height]
        offset += length
    raise ValueError('JPEG has no image data')


def validate_documentation_image(root, name):
    inventory = json.loads((root / 'docs/images/provenance.json').read_text(encoding='utf-8'))
    if inventory.get('kind') != 'fictional-demo' or set(inventory.get('images', {})) != DOCUMENTATION_IMAGES:
        raise ValueError('Documentation image inventory must name exactly the fictional demo screenshots')
    source = inventory.get('source', {})
    if source.get('file') != 'examples/fictional-app.html':
        raise ValueError('Documentation images must originate from the dedicated fictional demo')
    if hashlib.sha256((root / source['file']).read_bytes()).hexdigest() != source.get('sha256'):
        raise ValueError('Fictional demo source hash does not match image provenance')
    content = (root / name).read_bytes()
    record = inventory['images'][name]
    if hashlib.sha256(content).hexdigest() != record.get('sha256'):
        raise ValueError(f'Documentation screenshot hash mismatch: {name}')
    if jpeg_size(content) != record.get('pixelSize'):
        raise ValueError(f'Documentation screenshot size mismatch: {name}')


def validate_paths(root, names, require_all=True):
    names = list(names)
    if len(names) != len(set(names)):
        raise ValueError('Duplicate distribution path')
    unknown = set(names) - SOURCE_FILES
    if unknown:
        raise ValueError('Unapproved distribution paths: ' + ', '.join(sorted(unknown)))
    if require_all and set(names) != SOURCE_FILES:
        raise ValueError('Missing distribution paths: ' + ', '.join(sorted(SOURCE_FILES - set(names))))
    for name in names:
        path = root / name
        if not safe_member(name) or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f'Unsafe distribution path: {name}')
        if not path.is_file():
            raise ValueError(f'Missing distribution file: {name}')
        if name in DOCUMENTATION_IMAGES:
            validate_documentation_image(root, name)
        else:
            validate_text(name, path.read_bytes())
    return len(names)


def validate_source(root=ROOT):
    root = Path(root).resolve()
    actual = [path.relative_to(root).as_posix() for path in root.rglob('*')
              if not any(part in GENERATED_DIRS for part in path.relative_to(root).parts)
              and (path.is_file() or path.is_symlink())]
    count = validate_paths(root, actual)
    if (root / '.git').exists():
        result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'], capture_output=True, check=True)
        tracked = [name for name in result.stdout.decode('utf-8').split('\0') if name]
        validate_paths(root, tracked, require_all=False)
    return count


def validate_archive(path):
    expected = {'screenshot-review/' + name for name in SKILL_FILES}
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [item.filename for item in entries]
        if len(names) != len(expected) or set(names) != expected:
            raise ValueError('Skill ZIP must contain exactly the approved skill text files')
        for item in entries:
            if not safe_member(item.filename) or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Unsafe archive entry')
            validate_text(item.filename, archive.read(item))
        if archive.testzip():
            raise ValueError('ZIP integrity check failed')
    return len(entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    try:
        result = {'sourceFiles': validate_source()}
        if args.archive:
            result['archiveFiles'] = validate_archive(args.archive)
        print(json.dumps(result))
    except (ValueError, OSError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Distribution check failed: {error}\n')


if __name__ == '__main__':
    main()
