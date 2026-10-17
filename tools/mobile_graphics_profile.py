"""Guarded mobile render dimensions; camera and HUD policy are separate.

Use a private copy of the exact verified rewrite, retaining the original render
allocation budgets. This sets coherent render targets only: it does not by itself
expand the camera's field of view or prove that game UI supports the aspect ratio.
"""
import hashlib
import json
from pathlib import Path
import struct

import graphics_profile as base

DEFAULT_WIDTH = 1568
DEFAULT_HEIGHT = 720
WIDTH_SITES = frozenset((0x69c6d0, 0x69c6d4, 0x69c720, 0x69c73c,
                        0x69ecb4, 0x69f0b8, 0x69fde4, 0x69fde8,
                        0x70a740, 0x70a760))
BUDGET_SITES = frozenset((0x69d164, 0x69d16c))
ALIGNED_HEIGHT_SITE = 0x69c6f4
SELECTORS = base.SELECTORS


def parameters(width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT):
    """Conservative mobile sizes fitting the original 1600 x 1024 allocation."""
    if type(width) is not int or type(height) is not int:
        raise ValueError('Mobile render dimensions must be integers')
    if not (1280 <= width <= 1600 and width % 32 == 0):
        raise ValueError('Mobile width must be 32-aligned and between 1280 and 1600')
    if not (720 <= height <= 896 and height % 8 == 0):
        raise ValueError('Mobile height must be 8-aligned and between 720 and 896')
    return {'width': width, 'height': height,
            'aligned_height': (height + 63) // 64 * 64,
            'primary_allocation_bytes': 0x10400000,
            'secondary_allocation_bytes': 0x2a00000}


def sites(width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT):
    p = parameters(width, height)
    return tuple((offset, old,
                  old if offset in BUDGET_SITES else
                  p['aligned_height'] if offset == ALIGNED_HEIGHT_SITE else
                  width if offset in WIDTH_SITES else height,
                  reg, purpose)
                 for offset, old, _, reg, purpose in base.SITES)


def tables(width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT):
    parameters(width, height)
    return tuple((offset, values, width if 'widths' in purpose else height, purpose)
                 for offset, values, _, purpose in base.TABLES)


def configured_table(values, maximum):
    """All eight aliases are constructed at boot, even when DRS selects zero.

    Inactive banks must fit the resized base texture's storage. Keep their
    original smaller dimensions; only clamp components exceeding the new base.
    """
    return (maximum, *(min(value, maximum) for value in values[1:]))


def configure(data, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT):
    """Validate every original word/table before producing a configured copy."""
    selected_sites = sites(width, height)
    selected_tables = tables(width, height)
    for offset, old, _, reg, purpose in selected_sites:
        if offset + 4 > len(data) or struct.unpack_from('<I', data, offset)[0] != base.mov_w(reg, old):
            raise ValueError(f'Mobile configuration guard failed at main+{offset:#x}: {purpose}')
    for offset, old, _, _, purpose in SELECTORS:
        if offset + 4 > len(data) or struct.unpack_from('<I', data, offset)[0] != old:
            raise ValueError(f'Mobile selector guard failed at main+{offset:#x}: {purpose}')
    for offset, values, _, purpose in selected_tables:
        if offset + 32 > len(data) or struct.unpack_from('<8I', data, offset) != values:
            raise ValueError(f'Mobile table guard failed at main+{offset:#x}: {purpose}')
    output = bytearray(data)
    for offset, _, new, reg, _ in (*selected_sites, *SELECTORS):
        struct.pack_into('<I', output, offset, base.mov_w(reg, new))
    for offset, values, new, _ in selected_tables:
        struct.pack_into('<8I', output, offset, *configured_table(values, new))
    return bytes(output)


def launch_directory(work, destination, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT):
    """Package only this graphics copy; leave the verified source unchanged."""
    p = parameters(width, height)
    work = Path(work)
    destination = Path(destination)
    profile = json.loads((base.ROOT / 'config/bayonetta3-1.2.0.json').read_text())['modules']['main']
    nso = (work / 'game/ExeFS/main').read_bytes()
    if nso[0x40:0x60].hex() != profile['build_id'] or hashlib.sha256(nso).hexdigest() != profile['sha256']:
        raise ValueError('Mobile configuration requires the exact inventoried Bayonetta 3 1.2.0 NSO')
    original = (work / 'rewrite/main.patched.bin').read_bytes()
    verified = json.loads((work / 'verification.json').read_text())
    source_hash = hashlib.sha256(original).hexdigest()
    if not verified.get('passed') or source_hash != verified['modules']['main']['patched.bin_sha256']:
        raise ValueError('Mobile configuration requires an unchanged verified rewrite')
    configured = configure(original, width, height)
    destination.mkdir(parents=True, exist_ok=False)
    for path in (work / 'rewrite').iterdir():
        if path.is_file() and path.name != 'main.patched.bin':
            (destination / path.name).symlink_to(path.resolve())
    (destination / 'main.patched.bin').write_bytes(configured)
    receipt = {
        'mode': 'mobile-coherent-render', 'parameters': p,
        'build_id': profile['build_id'], 'nso_sha256': profile['sha256'],
        'verified_rewrite_sha256': source_hash,
        'configured_sha256': hashlib.sha256(configured).hexdigest(),
        'sites': [{'offset': hex(o), 'original': a, 'configured': b,
                   'register': r, 'purpose': purpose} for o, a, b, r, purpose in sites(width, height)],
        'selectors': [{'offset': hex(o), 'original_word': hex(a), 'configured': b,
                       'register': r, 'purpose': purpose} for o, a, b, r, purpose in SELECTORS],
        'tables': [{'offset': hex(o), 'original': v, 'configured': list(configured_table(v, n)),
                    'purpose': purpose} for o, v, n, purpose in tables(width, height)],
        'limitations': ['Intentional graphics configuration, not equivalence to original resolution.',
                        'Render targets only; camera field of view and HUD require separate adaptation.',
                        'Requires on-device rendering validation.'],
    }
    (destination / 'graphics.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return destination
