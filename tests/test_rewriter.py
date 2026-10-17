"""Synthetic regressions for the two new instruction/control-flow shapes."""
import ast
from itertools import combinations
from pathlib import Path
import re
import struct
import unittest
from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM
from unicorn.arm64_const import UC_ARM64_REG_SP,UC_ARM64_REG_PC,UC_ARM64_REG_TPIDRRO_EL0,UC_ARM64_REG_X0

ROOT = Path(__file__).resolve().parents[1]


def library():
    # Load actual production emitter definitions without rewriting a game binary.
    tree = ast.parse((ROOT/'third_party/blade2-mobile/dm/tools/patch_nso.py').read_text())
    defs = [n for n in tree.body if isinstance(n,ast.FunctionDef)]
    md = Cs(CS_ARCH_ARM64,CS_MODE_ARM); md.detail=True
    ns = dict(re=re,struct=struct,combinations=combinations,md=md,patch=bytearray(),fix=[],gates=[],stats={},
              PATCH_OFF=0x3000,KEY_PAGE_OFF=0x2000,KEY_INDEX={'K18':0},MEASURING=False,NOP=0xd503201f,
              EXCL_LD=('ldaxp','ldaxr','ldxr'),EXCL_ST=('stlxp','stlxr','stxr'))
    exec(compile(ast.Module(body=defs,type_ignores=[]),'production-emitter','exec'),ns)
    return ns


class RewriteRegressions(unittest.TestCase):
    def test_dynamic_sp_restores_every_borrowed_register(self):
        ns = library()
        # add sp,x18,#0 == mov sp,x18, from a synthetic alloca function.
        ins = next(ns['md'].disasm(struct.pack('<I',0x9100025f),0x1000))
        ns['site_plain'](ins)
        for new_sp in (0x81000,0x7f000,0x80000):
            uc = Uc(UC_ARCH_ARM64,UC_MODE_ARM)
            uc.mem_map(0,0x100000)
            uc.mem_write(0x3000,bytes(ns['patch']))
            uc.mem_write(0x2000,struct.pack('<Q',32))
            uc.mem_write(0x60020,struct.pack('<Q',new_sp))
            uc.reg_write(UC_ARM64_REG_TPIDRRO_EL0,0x60000)
            uc.reg_write(UC_ARM64_REG_SP,0x80000)
            for i in range(16): uc.reg_write(UC_ARM64_REG_X0+i,0x100+i)
            uc.emu_start(0x3000,0x1004,count=100)
            self.assertEqual(uc.reg_read(UC_ARM64_REG_SP),new_sp)
            self.assertEqual(uc.reg_read(UC_ARM64_REG_PC),0x1004)
            for i in range(16): self.assertEqual(uc.reg_read(UC_ARM64_REG_X0+i),0x100+i)

    def test_backward_cas_store_and_internal_entry_share_a_window(self):
        ns=library()
        # b load; store: stlxp w17,x16,x13,[x14]; cbz w17,exit;
        # load: ldaxp x17,x18,[x14]; eor/eor/orr; cbz x17,store.
        words=[0x14000003,0xc831b5d0,0x34000111,0xc87fc9d1,
               0xca0f0252,0xca100231,0xaa120231,0xb4ffff51]
        ins=list(ns['md'].disasm(b''.join(struct.pack('<I',w) for w in words),0x1000))
        windows=ns['find_windows'](ins)
        self.assertEqual(len(windows),1)
        self.assertEqual((windows[0][0].address,windows[0][-1].address),(0x1000,0x101c))
        ns['site_window'](windows[0])  # Internal unconditional branches must be relocatable.

    def test_neighboring_previous_store_is_not_mistaken_for_retry(self):
        ns=library()
        words=[0xc831b5d0,0xc87fc9d1,0xca0f0252,0xaa120231,0xc831b5d0,0x35ffff91]
        ins=list(ns['md'].disasm(b''.join(struct.pack('<I',w) for w in words),0x1000))
        windows=ns['find_windows'](ins)
        self.assertEqual(len(windows),1)
        self.assertEqual(windows[0][0].address,0x1004)


if __name__ == '__main__': unittest.main()
