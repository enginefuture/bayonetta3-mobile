"""Graphics policy is an intentional configuration, independently decode/execute it."""
import importlib.util
from pathlib import Path
import random
import struct
import unittest
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_NZCV
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('graphics',ROOT/'tools/graphics_profile.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class GraphicsProfile(unittest.TestCase):
    def original(self):
        data=bytearray(0x182e000)
        for off,old,new,reg,purpose in m.SITES:struct.pack_into('<I',data,off,m.mov_w(reg,old))
        for off,old,new,reg,purpose in m.SELECTORS:struct.pack_into('<I',data,off,old)
        for off,values,new,purpose in m.TABLES:struct.pack_into('<8I',data,off,*values)
        return data
    def test_guards_are_atomic_and_configured_differences_are_bounded(self):
        source=self.original();output=m.configure(source)
        allowed={i for o,*_ in (*m.SITES,*m.SELECTORS) for i in range(o,o+4)}|{i for o,*_ in m.TABLES for i in range(o,o+32)}
        self.assertTrue(all(a==b or i in allowed for i,(a,b) in enumerate(zip(source,output))))
        for off,*_ in (*m.SITES,*m.SELECTORS,*m.TABLES):
            damaged=bytearray(source);damaged[off]^=1;before=bytes(damaged)
            with self.assertRaises(ValueError):m.configure(damaged)
            self.assertEqual(damaged,before)
        for off,values,new,purpose in m.TABLES:self.assertEqual(struct.unpack_from('<8I',output,off),(new,*values[1:]))
    def test_mov_configuration_changes_only_its_declared_register(self):
        cs=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);rng=random.Random(20261017)
        uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM);uc.mem_map(0x10000,0x1000)
        for off,old,new,reg,purpose in (*m.SITES,*m.SELECTORS):
            for immediate in ((old,new) if (off,old,new,reg,purpose) in m.SITES else (new,)):
                word=struct.pack('<I',m.mov_w(reg,immediate));ins=list(cs.disasm(word,0x10000))
                self.assertEqual(len(ins),1);self.assertEqual(ins[0].mnemonic,'mov')
                self.assertEqual(ins[0].op_str,f'w{reg}, #0x{immediate:x}' if immediate else f'w{reg}, #0')
                for _ in range(12):
                    values=[rng.getrandbits(64) for _ in range(29)]
                    for r,v in enumerate(values):uc.reg_write(UC_ARM64_REG_X0+r,v)
                    flags=rng.randrange(16)<<28;uc.reg_write(UC_ARM64_REG_NZCV,flags)
                    uc.mem_write(0x10000,word);uc.ctl_remove_cache(0x10000,0x10004);uc.emu_start(0x10000,0x10004,count=1)
                    for r,v in enumerate(values):self.assertEqual(uc.reg_read(UC_ARM64_REG_X0+r),immediate if r==reg else v)
                    self.assertEqual(uc.reg_read(UC_ARM64_REG_NZCV),flags)
