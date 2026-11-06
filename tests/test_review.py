"""Behavioral checks for the portable review builder; no external packages."""

import importlib.util
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib
from argparse import Namespace
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'screenshot-review/scripts/review.py'
spec = importlib.util.spec_from_file_location('review_builder', MODULE)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def make_png(path, width=3, height=4):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    path.parent.mkdir(parents=True, exist_ok=True)
    pixels = b''.join(b'\0' + b'\xff\0\0' * width for _ in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))


class ReviewTest(unittest.TestCase):
    def setUp(self):
        workspace = Path(__file__).resolve().parents[1]
        temporary_root = (workspace / 'build/qa/ui-review-tests').resolve()
        if not temporary_root.is_relative_to(workspace):
            raise ValueError('Temporary test directory leaves the workspace')
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temporary_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        make_png(self.root / 'captures/before.png')
        make_png(self.root / 'captures/after.png', 5, 6)
        self.data = {
            'review': {'project':'demo', 'revision':'v2', 'title':'demo </script> <test> & Hindi हिन्दी'},
            'cases': [
                {'id':'A01','title':'Start','before':['captures/before.png'],'after':['captures/after.png']},
                {'id':'S01','title':'Added page','before':[],'after':['captures/after.png']},
            ],
        }
        self.manifest = self.root / 'captures.json'
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.data), encoding='utf-8')

    def args(self, **changes):
        options = dict(manifest=self.manifest, output=self.root / 'output', project=None,
                       revision=None, title=None, date=None, before_label=None, after_label=None,
                       capture_note=None, storage_key=None, pdf=None, zip=self.root / 'review.zip')
        options.update(changes)
        return Namespace(**options)

    def test_roundtrip_keeps_pixels_metadata_missing_sides_and_zip(self):
        result = review.build(self.args())
        self.assertEqual((result['cases'],result['pairs'],result['screenshots']), (2,2,3))
        output = self.root / 'output'
        self.assertEqual((output / 'raw/before/A01-01.png').read_bytes(), (self.root / 'captures/before.png').read_bytes())
        saved = review.read_json(output / 'manifest.json')
        self.assertEqual(saved['cases'][0]['after'][0]['pixelSize'], [5,6])
        self.assertEqual(saved['cases'][1]['before'], [])
        page = (output / 'index.html').read_text(encoding='utf-8')
        embedded = re.search(r'<script id="review-data" type="application/json">(.*?)</script>', page, re.S).group(1)
        self.assertEqual(json.loads(embedded), saved)
        self.assertNotIn('</script>', embedded)
        with zipfile.ZipFile(self.root / 'review.zip') as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn('raw/after/S01-01.png', archive.namelist())
            self.assertNotIn('captures.json', archive.namelist())

    def test_new_revision_isolated_and_old_output_is_not_overwritten(self):
        review.build(self.args())
        original = (self.root / 'output/index.html').read_bytes()
        with self.assertRaisesRegex(ValueError, 'not empty'):
            review.build(self.args())
        self.assertEqual((self.root / 'output/index.html').read_bytes(), original)
        review.build(self.args(output=self.root / 'v3', revision='v3', zip=None))
        one = review.read_json(self.root / 'output/manifest.json')['review']['storageKey']
        two = review.read_json(self.root / 'v3/manifest.json')['review']['storageKey']
        self.assertNotEqual(one, two)

    def test_viewer_refresh_preserves_capture_bytes_manifest_and_annotation_identity(self):
        review.build(self.args())
        output = self.root / 'output'
        manifest = (output / 'manifest.json').read_bytes()
        screenshot = (output / 'raw/after/A01-01.png').read_bytes()
        (output / 'index.html').write_text('Previous viewer', encoding='utf-8')
        result = review.refresh(output)
        self.assertEqual(result['updated'], 'viewer only')
        self.assertEqual((output / 'manifest.json').read_bytes(), manifest)
        self.assertEqual((output / 'raw/after/A01-01.png').read_bytes(), screenshot)
        page = (output / 'index.html').read_text(encoding='utf-8')
        embedded = re.search(r'<script id="review-data" type="application/json">(.*?)</script>', page, re.S).group(1)
        self.assertEqual(json.loads(embedded), json.loads(manifest))

    def test_source_escape_rejected_before_output_is_created(self):
        self.data['cases'][0]['before'] = ['../outside.png']
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'escapes'):
            review.build(self.args())
        self.assertFalse((self.root / 'output').exists())

    def test_duplicate_id_and_empty_case_rejected(self):
        self.data['cases'][1]['id'] = 'A01'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            review.build(self.args())
        self.data['cases'][1] = {'id':'S01','title':'No screenshots','before':[],'after':[]}
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'at least one'):
            review.build(self.args())

    def test_hash_validation_detects_changed_screenshot(self):
        review.build(self.args())
        make_png(self.root / 'output/raw/after/A01-01.png', 9, 10)
        with self.assertRaisesRegex(ValueError, 'integrity'):
            review.validate(self.root / 'output')

    def test_existing_pdf_is_optional_and_bad_pdf_rejected(self):
        invalid = self.root / 'bad.pdf'
        invalid.write_text('not a PDF')
        with self.assertRaisesRegex(ValueError, 'valid PDF'):
            review.build(self.args(pdf=invalid))
        self.assertFalse((self.root / 'output').exists())

    def test_standalone_skill_builds_from_two_unrelated_project_directories(self):
        skill = self.root / 'standalone-skill'
        shutil.copytree(MODULE.parents[1], skill, ignore=shutil.ignore_patterns('__pycache__'))
        keys = []
        for project in ['catalog-app', 'studio-web']:
            project_root = self.root / project
            make_png(project_root / 'captures/old.png')
            make_png(project_root / 'captures/new.png')
            source = {
                'review': {'project':project, 'revision':'v2'},
                'cases': [{'id':'checkout', 'title':'Checkout',
                           'before':['old.png'], 'after':['new.png']}],
            }
            (project_root / 'captures/manifest.json').write_text(json.dumps(source), encoding='utf-8')
            completed = subprocess.run(
                [sys.executable, str(skill / 'scripts/review.py'), 'build',
                 '--manifest', 'captures/manifest.json', '--output', 'reviews/v2'],
                cwd=project_root, capture_output=True, text=True, encoding='utf-8', check=True,
            )
            self.assertEqual(json.loads(completed.stdout)['cases'], 1)
            metadata = review.read_json(project_root / 'reviews/v2/manifest.json')
            self.assertEqual(metadata['review']['project'], project)
            keys.append(metadata['review']['storageKey'])
            self.assertEqual(review.validate(project_root / 'reviews/v2')['screenshots'], 2)
        self.assertNotEqual(keys[0], keys[1])


if __name__ == '__main__':
    unittest.main()
