#!/usr/bin/env python3
"""Build a deterministic, text-only Codex skill installation archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

from check_distribution import ROOT, SKILL_FILES, validate_archive, validate_source


def build(output):
    validate_source()
    version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('VERSION must be MAJOR.MINOR.PATCH')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / f'screenshot-review-v{version}.zip'
    staging = output / (archive_path.name + '.tmp')
    try:
        with zipfile.ZipFile(staging, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name in sorted(SKILL_FILES):
                info = zipfile.ZipInfo('screenshot-review/' + name, date_time=(2020, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, (ROOT / 'screenshot-review' / name).read_bytes())
        count = validate_archive(staging)
        staging.replace(archive_path)
    finally:
        staging.unlink(missing_ok=True)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    (output / 'SHA256SUMS.txt').write_text(f'{digest}  {archive_path.name}\n', encoding='utf-8')
    return {'version': version, 'archive': str(archive_path), 'files': count, 'sha256': digest}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.output)))
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        parser.exit(1, f'Release build failed: {error}\n')
