import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare',ROOT/'tools/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class PackageBounds(unittest.TestCase):
    def check_package(self,name,off=0,size=4,payload=b'data'):
        names = name.encode()+b'\0'
        data = struct.pack('<4sIII',b'PFS0',1,len(names),0)+struct.pack('<QQII',off,size,0,0)+names+payload
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'fixture.nsp'
            path.write_bytes(data)
            return prepare.members(path)

    def test_valid_member(self):
        self.assertEqual(self.check_package('program.nca')[0]['size'],4)

    def test_rejects_traversal(self):
        with self.assertRaises(ValueError): self.check_package('../escape.nca')

    def test_rejects_truncation(self):
        with self.assertRaises(ValueError): self.check_package('program.nca',size=5)


if __name__ == '__main__': unittest.main()
