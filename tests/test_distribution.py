"""Regressions for excluding captures, encoded images and unapproved release files."""

import importlib.util
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('distribution', ROOT / 'scripts/check_distribution.py')
distribution = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(distribution)


class DistributionTest(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / 'build/distribution-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_unknown_capture_path_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unapproved'):
            distribution.validate_paths(self.root, ['captures/design.png'], require_all=False)

    def test_embedded_image_and_personal_path_rejected_even_in_readme(self):
        for content in [b'<img src="data:' + b'image/png;base64,AAAA">',
                        b'example C:' + b'/Us' + b'ers/private-person/Downloads/design.png']:
            with self.assertRaises(ValueError):
                distribution.validate_text('README.md', content)

    def test_binary_and_large_encoded_payload_rejected(self):
        for content in [b'\x89PNG\0raw', b'payload: ' + b'A' * 2100]:
            with self.assertRaises(ValueError):
                distribution.validate_text('README.md', content)

    def write_archive(self, extra=False):
        path = self.root / 'skill.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            for name in distribution.SKILL_FILES:
                archive.writestr('screenshot-review/' + name, (ROOT / 'screenshot-review' / name).read_bytes())
            if extra:
                archive.writestr('screenshot-review/hidden-design.png', b'not allowed')
        return path

    def test_only_exact_skill_text_allowlist_can_be_packaged(self):
        self.assertEqual(distribution.validate_archive(self.write_archive()), len(distribution.SKILL_FILES))
        with self.assertRaisesRegex(ValueError, 'exactly'):
            distribution.validate_archive(self.write_archive(extra=True))

    def copy_documentation_fixture(self):
        name = 'docs/images/annotations.jpg'
        for relative in [name, 'docs/images/provenance.json', 'examples/fictional-app.html']:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, path)
        return name

    def test_only_documented_image_with_matching_source_and_hash_is_allowed(self):
        name = self.copy_documentation_fixture()
        self.assertEqual(distribution.validate_paths(self.root, [name], require_all=False), 1)
        path = self.root / name
        path.write_bytes(path.read_bytes()[:-2] + b'XX')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            distribution.validate_paths(self.root, [name], require_all=False)

    def test_image_metadata_rejected_even_when_inventory_hash_matches(self):
        name = self.copy_documentation_fixture()
        path = self.root / name
        content = path.read_bytes()
        content = content[:2] + b'\xff\xe1\x00\x08Exif\x00\x00' + content[2:]
        path.write_bytes(content)
        provenance = self.root / 'docs/images/provenance.json'
        inventory = json.loads(provenance.read_text(encoding='utf-8'))
        inventory['images'][name]['sha256'] = hashlib.sha256(content).hexdigest()
        provenance.write_text(json.dumps(inventory), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'metadata'):
            distribution.validate_paths(self.root, [name], require_all=False)

    def test_changed_demo_source_requires_new_image_provenance(self):
        name = self.copy_documentation_fixture()
        source = self.root / 'examples/fictional-app.html'
        source.write_bytes(source.read_bytes() + b'<!-- changed -->')
        with self.assertRaisesRegex(ValueError, 'source hash'):
            distribution.validate_paths(self.root, [name], require_all=False)

    def test_build_release_is_repeatable_and_contains_no_capture(self):
        command = [sys.executable, str(ROOT / 'scripts/build_release.py'), '--output', str(self.root)]
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True)
        archive = next(self.root.glob('*.zip'))
        original = archive.read_bytes()
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True)
        self.assertEqual(archive.read_bytes(), original)
        self.assertEqual(distribution.validate_archive(archive), len(distribution.SKILL_FILES))


if __name__ == '__main__':
    unittest.main()
