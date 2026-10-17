"""Coherent mobile targets retain budgets and reject partial/unknown images."""
from pathlib import Path
import ctypes
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import graphics_profile as base
import mobile_graphics_profile as mobile


class MobileGraphicsProfile(unittest.TestCase):
    def original(self):
        data = bytearray(0x182e000)
        for off, old, _, reg, _ in base.SITES:
            struct.pack_into('<I', data, off, base.mov_w(reg, old))
        for off, old, *_ in base.SELECTORS:
            struct.pack_into('<I', data, off, old)
        for off, values, *_ in base.TABLES:
            struct.pack_into('<8I', data, off, *values)
        return data

    def test_mobile_sizes_and_budgets(self):
        original = self.original()
        for width, height, aligned in ((1280,720,768),(1568,720,768),(1600,896,896)):
            output = mobile.configure(original,width,height)
            self.assertEqual(mobile.parameters(width,height)['aligned_height'],aligned)
            # Decode MOVZ from its machine word independently of mov_w.
            for off,old,_,reg,purpose in base.SITES:
                word = struct.unpack_from('<I',output,off)[0]
                value = ((word >> 5) & 0xffff) << (((word >> 21) & 3) * 16)
                expected = (old if off in (0x69d164,0x69d16c) else
                            aligned if off == 0x69c6f4 else
                            width if off in mobile.WIDTH_SITES else height)
                self.assertEqual(value,expected,purpose)
            for off,values,_,purpose in base.TABLES:
                self.assertEqual(struct.unpack_from('<8I',output,off),
                                 (width if 'widths' in purpose else height,
                                  *(min(value,width if 'widths' in purpose else height) for value in values[1:])))
            self.assertEqual(len(output),len(original))

    def test_atomic_guards_and_only_declared_words_change(self):
        source=self.original(); output=mobile.configure(source)
        allowed=({i for o,*_ in (*base.SITES,*base.SELECTORS) for i in range(o,o+4)} |
                 {i for o,*_ in base.TABLES for i in range(o,o+32)})
        # Sparse iteration bounds output changes to instructions and bank0 only.
        changed={i for i,(a,b) in enumerate(zip(source,output)) if a!=b}
        self.assertLessEqual(changed,allowed)
        for off,*_ in (*base.SITES,*base.SELECTORS,*base.TABLES):
            damaged=bytearray(source);damaged[off]^=1;before=bytes(damaged)
            with self.assertRaises(ValueError):mobile.configure(damaged)
            self.assertEqual(damaged,before)
        # Every bank is guarded, even when only bank zero is replaced.
        for off,*_ in base.TABLES:
            damaged=bytearray(source);damaged[off+28]^=1
            with self.assertRaises(ValueError):mobile.configure(damaged)
        with self.assertRaises(ValueError):mobile.configure(output)

    def test_conservative_size_policy(self):
        for width,height in ((1920,1080),(1567,720),(1568,719),(1568,900),
                             (1280.0,720),(True,720),(0,0)):
            with self.assertRaises(ValueError):mobile.parameters(width,height)
        self.assertEqual(mobile.parameters()['width'],1568)
        self.assertEqual(mobile.parameters()['height'],720)

    def test_mobile_does_not_change_mac_policy(self):
        source=self.original()
        mobile.configure(source)
        output=base.configure(source)
        self.assertEqual(struct.unpack_from('<I',output,0x70a740)[0],base.mov_w(8,1920))
        self.assertEqual(struct.unpack_from('<I',output,0x70a748)[0],base.mov_w(8,1080))

    def test_preinitialized_drs_aliases_fit_base_storage(self):
        # The real boot loop constructs all eight banks, not just selected bank
        # zero. The game compares each alias's NVN size against base storage.
        # Call the production Tegra layout to catch tile/pitch rounding effects,
        # rather than equating storage to width * height.
        root=Path(__file__).resolve().parents[1]
        nvn=root/'third_party/blade2-mobile/dm/gfx/nvn'
        with tempfile.TemporaryDirectory(prefix='mobile-layout-') as tmp:
            tmp=Path(tmp); helper=tmp/'layout.c'; library=tmp/'layout.dylib'
            helper.write_text('#include "nvn_tex.h"\n'
                'uint64_t footprint(unsigned w,unsigned h,unsigned f){'
                'nvn_texdesc d={.target=1,.format=f,.flags=12,.samples=1,'
                '.width=w,.height=h,.depth=1,.levels=1};'
                'nvn_texlayout out;nvn_tex_layout(&d,&out);return out.size;}\n')
            subprocess.run(['clang','-shared','-fPIC','-DDM_BAYONETTA3=1',
                            '-I'+str(nvn),str(helper),str(nvn/'nvn_tex.c'),
                            '-o',str(library)],check=True,capture_output=True)
            size=ctypes.CDLL(str(library)).footprint
            size.argtypes=[ctypes.c_uint]*3;size.restype=ctypes.c_uint64
            # This old inactive bank triggered the real device's init failure:
            # a 1600x896 alias cannot fit the new 1568x720 color allocation.
            self.assertGreater(size(1600,896,0x25),size(1568,720,0x25))
            for width in range(1280,1601,32):
                for height in range(720,897,8):
                    entries={purpose:mobile.configured_table(values,maximum)
                             for _,values,maximum,purpose in mobile.tables(width,height)}
                    for mode in ('handheld','docked'):
                        for w,h in zip(entries[mode+' DRS widths'],entries[mode+' DRS heights']):
                            for divisor in (1,2):
                                for fmt in (0x25,0x2a,0x2e,0x32,0x35):
                                    self.assertLessEqual(size(w//divisor,h//divisor,fmt),
                                                         size(width//divisor,height//divisor,fmt),
                                                         (width,height,mode,w,h,divisor,fmt))
