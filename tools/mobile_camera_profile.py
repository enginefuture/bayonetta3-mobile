"""Exact-build iOS camera and logical HUD dimensions, applied after render policy.

The camera initializer passes its viewport to main+0xcba90c. That setter divides
width by height into camera+0x3d8; the perspective builder main+0xcc8cb0 divides
its vertical cotangent by this aspect at +0xcc8df0. Increasing width therefore
expands horizontal FOV while preserving vertical FOV. The packed renderer
logical size feeds main+0xd02d70/80, including existing UI aspect compensation.
Keep authored 16:9 UI normalizers and unidentified auxiliary cameras unchanged.
This is intentional graphics configuration, not equivalence to original output.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import struct
import subprocess

from mobile_graphics_profile import DEFAULT_WIDTH, DEFAULT_HEIGHT, parameters

# Exact original words, rather than a search for all 1280/720 constants.
SITES = (
    (0x624e08, 0x5280a001, 'camera width'),
    (0x624e0c, 0x52805a02, 'camera height'),
    (0x69d15c, 0xd280a008, 'logical HUD width'),
    (0x69d160, 0xf2c05a08, 'logical HUD height in upper 32 bits'),
)
LIMITATIONS = (
    'Intentional camera configuration; not semantic equivalence to the original viewport.',
    'Static camera/projection evidence does not prove all gameplay or cutscene cameras use this initializer.',
    'Existing UI aspect compensation is preserved; HUD anchors and safe areas require on-device validation.',
    'Independent auxiliary cameras and authored 16:9 UI normalizers are unchanged.',
)


def sites(width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT):
    parameters(width, height)
    words = (0x52800001 | (width << 5), 0x52800002 | (height << 5),
             0xd2800008 | (width << 5), 0xf2c00008 | (height << 5))
    return tuple((offset, original, configured, purpose)
                 for (offset, original, purpose), configured in zip(SITES, words))


def configure(data, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT):
    """Atomically validate four original instructions and return a new copy."""
    selected = sites(width, height)
    for offset, original, _, purpose in selected:
        if offset + 4 > len(data) or struct.unpack_from('<I', data, offset)[0] != original:
            raise ValueError(f'Mobile camera guard failed at main+{offset:#x}: {purpose}')
    result = bytearray(data)
    for offset, _, configured, _ in selected:
        struct.pack_into('<I', result, offset, configured)
    return bytes(result)


def verify(original, llvm, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT):
    """Decode with LLVM and execute configuration plus original math in Unicorn."""
    from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
    from unicorn.arm64_const import (UC_ARM64_REG_X0, UC_ARM64_REG_X29,
        UC_ARM64_REG_X30, UC_ARM64_REG_SP, UC_ARM64_REG_NZCV,
        UC_ARM64_REG_S0, UC_ARM64_REG_CPACR_EL1)
    configured = configure(original, width, height)
    selected = sites(width, height)
    code = b''.join(configured[o:o + 4] for o, *_ in selected)
    result = subprocess.run([str(llvm), '--disassemble', '--triple=aarch64'],
        input=' '.join(f'0x{x:02x}' for x in code), text=True, capture_output=True, check=True)
    decoded = [' '.join(line.split('//')[0].split()) for line in result.stdout.splitlines()
               if line.strip() and not line.lstrip().startswith('.')]
    expected = (f'mov w1, #{width}', f'mov w2, #{height}',
                f'mov x8, #{width}', f'movk x8, #{height}, lsl #32')
    if tuple(decoded) != expected:
        raise ValueError(f'Independent LLVM camera decode failed: {decoded}')
    registers = (*(UC_ARM64_REG_X0 + r for r in range(29)),
                 UC_ARM64_REG_X29, UC_ARM64_REG_X30)
    rng = random.Random(20261018)
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    uc.mem_map(0x10000, 0x1000)
    uc.mem_map(0x20000, 0x1000)
    uc.reg_write(UC_ARM64_REG_CPACR_EL1, 3 << 20)

    def run(code, count):
        uc.mem_write(0x10000, bytes(code))
        uc.ctl_remove_cache(0x10000, 0x10000 + len(code))
        uc.emu_start(0x10000, 0x10000 + len(code), count=count)

    def state():
        values = [rng.getrandbits(64) for _ in registers]
        for r, value in zip(registers, values):
            uc.reg_write(r, value)
        stack = 0x30000 + rng.randrange(256) * 16
        flags = rng.randrange(16) << 28
        uc.reg_write(UC_ARM64_REG_SP, stack)
        uc.reg_write(UC_ARM64_REG_NZCV, flags)
        return values, stack, flags

    def unchanged(values, stack, flags, changed):
        for index, (r, value) in enumerate(zip(registers, values)):
            assert uc.reg_read(r) == changed.get(index, value), (index, changed)
        assert uc.reg_read(UC_ARM64_REG_SP) == stack
        assert uc.reg_read(UC_ARM64_REG_NZCV) == flags

    instruction_cases = 0
    for index, (offset, _, _, _) in enumerate(selected):
        for _ in range(24):
            values, stack, flags = state()
            reg = (1, 2, 8, 8)[index]
            value = (width, height, width,
                     (values[8] & ~(0xffff << 32)) | (height << 32))[index]
            run(configured[offset:offset + 4], 1)
            unchanged(values, stack, flags, {reg: value})
            instruction_cases += 1
    for _ in range(32):
        values, stack, flags = state()
        run(configured[0x624e08:0x624e10], 2)
        unchanged(values, stack, flags, {1: width, 2: height})
        values, stack, flags = state()
        run(configured[0x69d15c:0x69d164], 2)
        unchanged(values, stack, flags, {8: width | (height << 32)})

    # Execute this exact original setter slice, not a Python substitute for its
    # division. Guard every instruction before accepting the data-flow proof.
    setter_words = (0x1e220023, 0x910f0109, 0x1e220044, 0xf901e11f,
        0xb903c901, 0xb9000d22, 0xbd03d101, 0x1e241861, 0xbd001522,
        0x52800029, 0xbd03dd00, 0xb903f509, 0xbd03d901)
    setter = struct.pack('<13I', *setter_words)
    if original[0xcba91c:0xcba950] != setter:
        raise ValueError('Original camera aspect setter evidence guard failed')
    # These two real perspective paths have the same horizontal divide, with
    # aspect in s1 and s0 respectively; neither changes the vertical cotangent.
    projections = ((0xcc8df0, 0x1e211881, 1), (0xcb9aa8, 0x1e201881, 0))
    for offset, word, _ in projections:
        if original[offset:offset + 4] != struct.pack('<I', word):
            raise ValueError(f'Original projection evidence guard failed at {offset:#x}')
    f32 = lambda value: struct.unpack('<f', struct.pack('<f', value))[0]
    bits = lambda value: struct.unpack('<I', struct.pack('<f', value))[0]
    float_at = lambda offset: struct.unpack('<f', bytes(uc.mem_read(0x20000 + offset, 4)))[0]
    aspect_cases = 0
    for w, h in ((1280, 720), (width, height), (1600, 896)):
        for _ in range(16):
            uc.mem_write(0x20000, bytes([0xa5]) * 0x1000)
            uc.reg_write(UC_ARM64_REG_X0 + 8, 0x20000)
            uc.reg_write(UC_ARM64_REG_X0 + 1, w)
            uc.reg_write(UC_ARM64_REG_X0 + 2, h)
            fov = f32(rng.uniform(0.3, 1.7))
            near = f32(rng.uniform(0.01, 1))
            far = f32(rng.uniform(100, 30000))
            for index, value in enumerate((fov, near, far)):
                uc.reg_write(UC_ARM64_REG_S0 + index, bits(value))
            run(setter, 13)
            assert struct.unpack('<2I', bytes(uc.mem_read(0x203c8, 8))) == (w, h)
            assert float_at(0x3d8) == f32(w / h)
            assert float_at(0x3dc) == fov
            assert float_at(0x3d0) == near and float_at(0x3d4) == far
            aspect_cases += 1
    projection_cases = 0
    for offset, _, aspect_register in projections:
        for _ in range(32):
            cotangent = f32(rng.uniform(0.5, 8))
            horizontal = []
            for aspect in (f32(1280 / 720), f32(width / height)):
                uc.reg_write(UC_ARM64_REG_S0 + 4, bits(cotangent))
                uc.reg_write(UC_ARM64_REG_S0 + aspect_register, bits(aspect))
                run(original[offset:offset + 4], 1)
                assert uc.reg_read(UC_ARM64_REG_S0 + 4) == bits(cotangent)
                value = struct.unpack('<f', struct.pack('<I', uc.reg_read(UC_ARM64_REG_S0 + 1)))[0]
                assert value == f32(cotangent / aspect)
                horizontal.append(value)
            if width / height > 1280 / 720:
                assert horizontal[1] < horizontal[0]
            projection_cases += 1
    return {'passed': True, 'width': width, 'height': height,
        'input_sha256': hashlib.sha256(original).hexdigest(),
        'configured_sha256': hashlib.sha256(configured).hexdigest(),
        'llvm_decoded': decoded, 'unicorn_instruction_states': instruction_cases,
        'unicorn_camera_and_packed_sequences': 64,
        'unicorn_actual_aspect_setter_states': aspect_cases,
        'unicorn_actual_projection_pairs': projection_cases,
        'evidence': {'setter': 'main+0xcba91c..0xcba950',
                     'projection_divides': ['main+0xcc8df0', 'main+0xcb9aa8']},
        'limitations': list(LIMITATIONS)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, default=Path(__file__).resolve().parents[1] / 'work')
    p.add_argument('--llvm', type=Path, default=Path('/opt/homebrew/opt/llvm/bin/llvm-mc'))
    p.add_argument('--width', type=int, default=DEFAULT_WIDTH)
    p.add_argument('--height', type=int, default=DEFAULT_HEIGHT)
    a = p.parse_args()
    report = verify((a.work / 'rewrite/main.patched.bin').read_bytes(), a.llvm, a.width, a.height)
    destination = a.work / 'analysis/ios-wide/camera-profile-verification.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
