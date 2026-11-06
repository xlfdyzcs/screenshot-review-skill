"""Regressions for excluding captures, encoded images and unapproved release files."""

import importlib.util
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
