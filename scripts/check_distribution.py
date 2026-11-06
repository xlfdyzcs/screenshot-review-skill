#!/usr/bin/env python3
"""Validate the explicit source and skill-archive distribution boundaries."""

from __future__ import annotations

import argparse
import json
import re
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SKILL_FILES = frozenset({
    'SKILL.md', 'agents/openai.yaml', 'assets/review.html', 'assets/review.css',
    'assets/review.js', 'assets/review-state.js', 'references/capture.md',
    'scripts/review.py', 'scripts/open_review.ps1',
})
SOURCE_FILES = frozenset({
    '.gitignore', '.gitattributes', '.github/workflows/verify.yml',
    'README.md', 'VERSION', 'CONTRIBUTING.md', 'docs/USAGE.md', 'docs/PRIVACY.md',
    'examples/create_demo.py', 'scripts/check_distribution.py',
    'scripts/build_release.py', 'tests/test_review.py',
    'tests/test_review_state.cjs', 'tests/test_distribution.py',
}) | frozenset('screenshot-review/' + name for name in SKILL_FILES)
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
