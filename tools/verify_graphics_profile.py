#!/usr/bin/env python3
"""Independent local LLVM decode and Unicorn DRS-selection checks (no game upload)."""
import argparse
import json
from pathlib import Path
import random
import struct
import subprocess
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X8, UC_ARM64_REG_X9, UC_ARM64_REG_X29, UC_ARM64_REG_X30, UC_ARM64_REG_SP, UC_ARM64_REG_NZCV
from graphics_profile import configure, SITES, SELECTORS, mov_w

def verify(original, llvm, *, configurator=configure, sites=None):
    configured=configurator(original)
    sites=tuple(sites) if sites is not None else (*SITES,*SELECTORS)
    code=b''.join(configured[o:o+4] for o,*_ in sites)
    result=subprocess.run([str(llvm),'--disassemble','--triple=aarch64'],input=' '.join(f'0x{x:02x}' for x in code),text=True,capture_output=True,check=True)
    decoded=[line.split('//')[0].strip().replace('\t',' ') for line in result.stdout.splitlines() if line.strip() and not line.lstrip().startswith('.')]
    assert len(decoded)==len(sites),(len(decoded),len(sites))
    for line,(offset,old,new,reg,purpose) in zip(decoded,sites):
        assert line.startswith(f'mov w{reg}, #'),(hex(offset),line)
        assert int(line.split('#')[1].split()[0],0)==new,(hex(offset),line,new)
    # Execute each emitted MOV independently. Check all integer registers and
    # flags, not just the destination, using state independent of the encoder.
    single=Uc(UC_ARCH_ARM64,UC_MODE_ARM);single.mem_map(0x10000,0x1000)
    rng=random.Random(20261017);mov_cases=0
    registers=(*(UC_ARM64_REG_X0+r for r in range(29)),UC_ARM64_REG_X29,UC_ARM64_REG_X30)
    for offset,old,new,reg,purpose in sites:
        single.mem_write(0x10000,configured[offset:offset+4])
        single.ctl_remove_cache(0x10000,0x10004)
        for _ in range(12):
            values=[rng.getrandbits(64) for _ in registers]
            for r,v in zip(registers,values):single.reg_write(r,v)
            stack=0x20000+rng.randrange(256)*16;single.reg_write(UC_ARM64_REG_SP,stack)
            flags=rng.randrange(16)<<28;single.reg_write(UC_ARM64_REG_NZCV,flags)
            single.emu_start(0x10000,0x10004,count=1)
            for index,(r,v) in enumerate(zip(registers,values)):
                assert single.reg_read(r)==(new if index==reg else v),(hex(offset),index)
            assert single.reg_read(UC_ARM64_REG_NZCV)==flags,hex(offset)
            assert single.reg_read(UC_ARM64_REG_SP)==stack,hex(offset)
            mov_cases+=1
    # Exercise the actual selector's control flow up to the first resource-bank
    # lookup, with randomized SDK settings, debug settings, and adaptive levels.
    uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
    uc.mem_map(0x600000,0x100000);uc.mem_write(0x6d3bb4,configured[0x6d3bb4:0x6d45bc])
    uc.mem_map(0x183b000,0x1000);uc.mem_write(0x183b000,original[0x183b000:0x183c000])
    uc.mem_map(0x2400000,0x300000);uc.mem_map(0x3000000,0x400000);uc.mem_map(0x4000000,0x10000)
    def write(address,value,kind='I'):uc.mem_write(address,struct.pack('<'+kind,value))
    for address,value in [(0x249c4a8,0x3000000),(0x249e980,0x3100000),(0x249d0d8,0x3200000),(0x249c388,0x3300000)]:write(address,value,'Q')
    reached=set();uc.hook_add(UC_HOOK_CODE,lambda u,a,s,d:reached.add(a))
    rng=random.Random(20261017);cases=0
    for debug in (0,1):
      for special in (0,1):
       for forced in (0,1):
        for override in (0,1):
         for _ in range(64):
            for offset,value in [(0xd6a0,debug),(0xd6a4,rng.randrange(2)),(0x4a44,forced),(0x4a38,override),(0x4a34,rng.randrange(-8,9)&0xffffffff),(0xd610,rng.randrange(-8,9)&0xffffffff)]:write(0x3000000+offset,value)
            write(0x3200330,special);write(0x31016d4,rng.randrange(-8,9)&0xffffffff);write(0x3300024,rng.randrange(256))
            uc.reg_write(UC_ARM64_REG_SP,0x4008000);uc.emu_start(0x6d3bb4,0x6d3cec,count=1000)
            assert uc.reg_read(UC_ARM64_REG_X8)==0 and uc.reg_read(UC_ARM64_REG_X9)==0,'DRS selector escaped fixed bank'
            cases+=1
    # The original index-seven bank is unreachable after pinning its producers.
    required={0x6d3c00,0x6d3c14,0x6d3c28,0x6d3ccc,0x6d45ac,0x6d3ce8}
    assert required<=reached,sorted(hex(x) for x in required-reached)
    return {'passed':True,'llvm_configuration_instructions':len(sites),'unicorn_configuration_states':mov_cases,'unicorn_actual_drs_paths':cases,'selected_scene_bank':0,'selected_secondary_bank':0,'limitations':['Intentional graphics policy; not equivalence to original resolution or proof of rendering quality.']}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,default=Path(__file__).resolve().parents[1]/'work');p.add_argument('--llvm',type=Path,default=Path('/opt/homebrew/opt/llvm/bin/llvm-mc'));a=p.parse_args()
    report=verify((a.work/'rewrite/main.patched.bin').read_bytes(),a.llvm)
    (a.work/'graphics-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
