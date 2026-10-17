"""Directory bounds/traversal and nested resource inventory, using owned fixtures."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rom_scan', ROOT/'tools/scan_rom.py')
scan=importlib.util.module_from_spec(spec);spec.loader.exec_module(scan)


class RomInventory(unittest.TestCase):
    def test_pkz_extent_and_unsafe_names(self):
        def fixture(name, offset=128):
            names=name+b'\0None\0'
            data=bytearray(132)
            struct.pack_into('<4sIQ4I',data,0,b'pkzl',0x20000,len(data),1,32,len(names),4096)
            struct.pack_into('<IIQQQ',data,32,0,len(name)+1,4,offset,4)
            data[64:64+len(names)]=names
            return data
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'owned.pkz';p.write_bytes(fixture(b'owned.dat'))
            self.assertEqual(scan.pkz_directory(p)[0]['size'],4)
            for name,off in ((b'../owned.dat',128),(b'owned.dat',130),(b'owned.dat',32)):
                p.write_bytes(fixture(name,off))
                with self.assertRaises(ValueError):scan.pkz_directory(p)

    def test_dat_child_extent_and_payload_identity(self):
        data=bytearray(128)
        struct.pack_into('<4s6I',data,0,b'DAT\0',1,32,36,40,60,0)
        struct.pack_into('<I',data,32,96);data[36:40]=b'own\0'
        struct.pack_into('<I',data,40,16);data[44:54]=b'owned.own\0'
        struct.pack_into('<I',data,60,4);data[96:100]=b'OURS'
        rows=list(scan.dat_leaves(data,'owned.dat'))
        self.assertEqual([(r['offset'],r['size'],r['magic']) for r in rows],[(96,4,'4f555253')])
        struct.pack_into('<I',data,60,1000)
        with self.assertRaises(ValueError):list(scan.dat_leaves(data,'owned.dat'))

    def test_shader_unknown_layout_remains_visible(self):
        with self.assertRaises((ValueError,struct.error)):
            scan.shader_record(bytes(64))

if __name__=='__main__':unittest.main()
