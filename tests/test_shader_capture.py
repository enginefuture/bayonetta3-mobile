import hashlib
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'third_party/blade2-mobile/dm/gfx/tools'))
from nvn_capture import capture_stage

class CaptureTests(unittest.TestCase):
    def sample(self,kind=1):
        control=bytearray(0x850);code=bytearray(0x100)
        struct.pack_into('<3I',control,0,0x98761234,1,15)
        struct.pack_into('<I',control,0x20,len(control))
        struct.pack_into('<2I',control,0x700,0x100,len(code))
        struct.pack_into('<I',code,0,0x12345678)
        struct.pack_into('<I',code,0x30,kind<<10)
        return hashlib.sha256(control).hexdigest()[:16],control,code
    def test_truncated_code_never_becomes_compute(self):
        key,control,code=self.sample()
        for broken in (b'',code[:-1],code+bytes(8)):
            with self.assertRaisesRegex(ValueError,'incomplete code'):capture_stage(key,control,broken)
        self.assertEqual(capture_stage(key,control,code),'vs')
    def test_tessellation_is_identified_explicitly(self):
        for kind,stage in ((2,'tcs'),(3,'tes')):
            self.assertEqual(capture_stage(*self.sample(kind)),stage)
    def test_hash_and_control_layout(self):
        key,control,code=self.sample()
        with self.assertRaisesRegex(ValueError,'hash'):capture_stage('0'*16,control,code)
        control[8]=17
        with self.assertRaisesRegex(ValueError,'layout'):capture_stage(key,control,code)
