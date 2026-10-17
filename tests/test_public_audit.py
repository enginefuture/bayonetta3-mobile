"""Publication boundaries must hold even when a file is renamed or force-added."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / 'tools/audit_public.py'
spec = importlib.util.spec_from_file_location('public_audit', PATH)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class PublicAudit(unittest.TestCase):
    def test_private_paths_and_case_variants(self):
        for path in ('test.NSP', 'nested/prod.keys', 'work/x.txt', 'ExeFS/main', '.env.local', 'build/x.metallib'):
            self.assertIsNotNone(audit.path_error(path), path)
        self.assertIsNone(audit.path_error('docs/BUILD.md'))

    def test_content_cannot_be_hidden_by_renaming(self):
        for data in (b'PFS0'+bytes(32), b'NSO0'+bytes(32), b'\x7fELF'+bytes(32),
                     b'header_key = '+b'1'*64, b'gh' + b'p_' + b'x'*36):
            self.assertIsNotNone(audit.content_error('example.txt', data))
        self.assertIsNone(audit.content_error('example.c', b'int main(void) { return 0; }\n'))

    def test_force_added_and_deleted_history_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            def git(*args):
                subprocess.run(['git', '-C', tmp, *args], check=True, capture_output=True)
            git('init', '-q')
            git('config', 'user.name', 'Synthetic Test')
            git('config', 'user.email', 'synthetic@example.invalid')
            p = Path(tmp)
            (p/'.gitignore').write_text('*.NSP\n')
            (p/'bad.NSP').write_bytes(b'PFS0'+bytes(32))
            git('add', '.gitignore')
            git('add', '-f', 'bad.NSP')
            def check(*args):
                return subprocess.run(['python3', str(PATH), *args], cwd=tmp, capture_output=True).returncode
            self.assertNotEqual(check(), 0)
            git('commit', '-qm', 'Synthetic forbidden fixture')
            git('rm', 'bad.NSP')
            git('commit', '-qm', 'Remove fixture')
            self.assertEqual(check(), 0)
            self.assertNotEqual(check('--all-history'), 0)


if __name__ == '__main__':
    unittest.main()
