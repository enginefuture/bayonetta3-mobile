"""Bounded mobile camera policy and independent execution of its real math."""
import importlib
from pathlib import Path
import shutil
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
m = importlib.import_module('mobile_camera_profile')


class MobileCameraProfile(unittest.TestCase):
    def source(self):
        # Synthetic image with only the individually inventoried instructions.
        data = bytearray(0xcc9000)
        for offset, word in ((0x624e08, 0x5280a001), (0x624e0c, 0x52805a02),
                             (0x69d15c, 0xd280a008), (0x69d160, 0xf2c05a08),
                             (0x646b3c, 0x52802001), (0x646b60, 0x52802002),
                             (0xc04af8, 0x5280a001), (0x706b70, 0x5291c728),
                             (0xc826e8, 0x5291c728), (0xca8dd4, 0x5291c728)):
            struct.pack_into('<I', data, offset, word)
        # Actual original setter arithmetic/store slice; independently inventoried.
        struct.pack_into('<13I', data, 0xcba91c,
            0x1e220023, 0x910f0109, 0x1e220044, 0xf901e11f,
            0xb903c901, 0xb9000d22, 0xbd03d101, 0x1e241861, 0xbd001522,
            0x52800029, 0xbd03dd00, 0xb903f509, 0xbd03d901)
        struct.pack_into('<I', data, 0xcc8df0, 0x1e211881)
        struct.pack_into('<I', data, 0xcb9aa8, 0x1e201881)
        return data

    def test_four_changes_only_preserve_ui_normalizers_and_auxiliary_cameras(self):
        source = self.source()
        for width, height in ((1280, 720), (1568, 720), (1600, 896)):
            configured = m.configure(source, width, height)
            self.assertIsInstance(configured, bytes)
            restored = bytearray(configured)
            for offset, original, _, _ in m.sites(width, height):
                struct.pack_into('<I', restored, offset, original)
            self.assertEqual(restored, source)
            self.assertEqual(struct.unpack_from('<I', configured, 0x624e08)[0],
                             0x52800001 | width << 5)
            self.assertEqual(struct.unpack_from('<I', configured, 0x69d160)[0],
                             0xf2c00008 | height << 5)

    def test_guards_are_atomic_and_reject_already_configured_image(self):
        source = self.source()
        for offset in (0x624e08, 0x624e0c, 0x69d15c, 0x69d160):
            damaged = bytearray(source)
            damaged[offset] ^= 1
            before = bytes(damaged)
            with self.assertRaisesRegex(ValueError, 'guard failed'):
                m.configure(damaged)
            self.assertEqual(damaged, before)
        with self.assertRaisesRegex(ValueError, 'guard failed'):
            m.configure(m.configure(source))
        with self.assertRaisesRegex(ValueError, 'guard failed'):
            m.configure(bytes(16))

    def test_dimensions_follow_conservative_render_allocation_policy(self):
        for width, height in ((1569, 720), (1248, 720), (1632, 720),
                              (1568, 712), (1568, 904), (1568, 721),
                              (True, 720), (1568, 720.0)):
            with self.assertRaises(ValueError):
                m.configure(bytes(), width, height)

    def test_llvm_and_unicorn_verify_real_setter_and_projection(self):
        llvm = shutil.which('llvm-mc') or '/opt/homebrew/opt/llvm/bin/llvm-mc'
        if not Path(llvm).exists():
            self.skipTest('Independent LLVM decoder is unavailable')
        report = m.verify(self.source(), llvm)
        self.assertTrue(report['passed'])
        self.assertEqual(report['unicorn_instruction_states'], 96)
        self.assertEqual(report['unicorn_camera_and_packed_sequences'], 64)
        self.assertEqual(report['unicorn_actual_aspect_setter_states'], 48)
        self.assertEqual(report['unicorn_actual_projection_pairs'], 64)
        # Reject unknown math even if the four editable configuration guards match.
        damaged = self.source()
        damaged[0xcba938] ^= 1
        with self.assertRaisesRegex(ValueError, 'aspect setter evidence guard'):
            m.verify(damaged, llvm)


if __name__ == '__main__':
    unittest.main()
