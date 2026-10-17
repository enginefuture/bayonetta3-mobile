"""Exact-build graphics configuration, separate from instruction rewriting.

Never edit the verified rewrite in place. A launch directory contains symlinks to
the verified tables and a private copy of main with only the declared graphics constants and DRS selections
changed. Both original NSO identity and every original instruction are required.
"""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
# offset, original immediate, 1080p immediate, destination W register, purpose.
SITES = (
    (0x69d164,0x10400000,0x20800000,10,'primary render allocation budget'),
    (0x69d16c,0x2a00000,0x5400000,8,'secondary render allocation budget'),
    (0x69c6d0,1280,1920,8,'scene minimum width'),
    (0x69c6d4,1600,1920,0,'renderer maximum width'),
    (0x69c6dc,720,1080,8,'scene minimum height'),
    (0x69c6e0,896,1080,9,'scene maximum height'),
    (0x69c6f0,900,1080,1,'renderer maximum height'),
    (0x69c6f4,1024,1088,8,'aligned allocation height'),
    (0x69c720,1600,1920,4,'output target width'),
    (0x69c728,900,1080,5,'output target height'),
    (0x69c73c,1600,1920,0,'scene target width'),
    (0x69c740,896,1080,1,'scene target height'),
    (0x69ecb4,1360,1920,25,'handheld index-zero HDR width'),
    (0x69ecc4,768,1080,3,'handheld index-zero HDR height'),
    (0x69ecf0,768,1080,3,'handheld index-zero AO height'),
    (0x69f0b8,1600,1920,25,'docked index-zero HDR width'),
    (0x69f0c8,896,1080,3,'docked index-zero HDR height'),
    (0x69f0f4,896,1080,3,'docked index-zero AO height'),
    (0x69fde4,1280,1920,8,'rebuild minimum width'),
    (0x69fde8,1600,1920,19,'rebuild maximum width'),
    (0x69fdf4,720,1080,8,'rebuild minimum height'),
    (0x69fdf8,896,1080,9,'rebuild maximum height'),
    (0x69fe08,896,1080,1,'rebuild scene height'),
    (0x70a740,1600,1920,8,'docked width getter'),
    (0x70a748,900,1080,8,'docked height getter'),
    (0x70a760,1280,1920,8,'handheld width getter'),
    (0x70a768,720,1080,8,'handheld height getter'),
)

# Pin both DRS selectors to bank zero. Original resolution used independent
# depth/HDR tables and hard-coded HDR/AO constructors: changing every depth-table
# entry alone leaves alternating HDR banks at their original dimensions.
# Preserve control flow, flags, instruction length, and all other registers.
# offset, exact original word, configured immediate, W register, purpose.
SELECTORS = (
    (0x6d3c00,0x1a9f07e9,0,9,'debug DRS selector'),
    (0x6d3c14,0x528000e9,0,9,'special DRS selector'),
    (0x6d3c28,0x52800029,0,9,'forced DRS selector'),
    (0x6d3cb0,0x528000e9,0,9,'special bank selector'),
    (0x6d3cb4,0x528000e8,0,8,'special secondary bank selector'),
    (0x6d3ccc,0x52800029,0,9,'override DRS selector'),
    (0x6d45ac,0xb868d929,0,9,'adaptive DRS table selector'),
    (0x6d45b4,0x52800069,0,9,'adaptive DRS fallback selector'),
    (0x6d3ce8,0x1a8db108,0,8,'secondary DRS selector clamp'),
)

TABLES = (
    (0x182d450,(768,720,544,496,448,400,368,360),1080,'handheld DRS heights'),
    (0x182d4d0,(1360,1280,960,896,800,704,640,640),1920,'handheld DRS widths'),
    (0x182d570,(896,896,848,816,768,720,576,360),1080,'docked DRS heights'),
    (0x182d670,(1600,1600,1504,1440,1360,1280,1024,640),1920,'docked DRS widths'),
)

def mov_w(reg, immediate):
    shift=0 if immediate<=0xffff else 16
    if immediate & ((1<<shift)-1) or immediate>>shift>0xffff:raise ValueError("MOVZ immediate out of range")
    return 0x52800000 | ((shift//16)<<21) | ((immediate>>shift)<<5) | reg

def configure(data):
    """Validate all sites before applying any configuration; reject unknown code."""
    for off, old, new, reg, purpose in SITES:
        if off+4 > len(data) or struct.unpack_from('<I',data,off)[0] != mov_w(reg,old):
            raise ValueError(f'1080p configuration guard failed at main+{off:#x}: {purpose}')
    for off, old, new, reg, purpose in SELECTORS:
        if off+4 > len(data) or struct.unpack_from('<I',data,off)[0] != old:
            raise ValueError(f'1080p selector guard failed at main+{off:#x}: {purpose}')
    for off, values, new, purpose in TABLES:
        if off+len(values)*4>len(data) or struct.unpack_from('<8I',data,off)!=values:
            raise ValueError(f'1080p table guard failed at main+{off:#x}: {purpose}')
    out=bytearray(data)
    for off, old, new, reg, purpose in SITES:
        struct.pack_into('<I',out,off,mov_w(reg,new))
    for off, old, new, reg, purpose in SELECTORS:
        struct.pack_into('<I',out,off,mov_w(reg,new))
    for off, values, new, purpose in TABLES:
        struct.pack_into('<8I',out,off,new,*values[1:])
    return bytes(out)

def launch_directory(work, destination):
    work=Path(work); destination=Path(destination)
    profile=json.loads((ROOT/'config/bayonetta3-1.2.0.json').read_text())['modules']['main']
    nso=(work/'game/ExeFS/main').read_bytes()
    if nso[0x40:0x60].hex()!=profile['build_id'] or hashlib.sha256(nso).hexdigest()!=profile['sha256']:
        raise ValueError('1080p configuration requires the exact inventoried Bayonetta 3 1.2.0 NSO')
    source=work/'rewrite/main.patched.bin'; original=source.read_bytes()
    verified=json.loads((work/'verification.json').read_text())
    if not verified.get('passed') or hashlib.sha256(original).hexdigest()!=verified['modules']['main']['patched.bin_sha256']:
        raise ValueError('1080p configuration requires an unchanged verified rewrite')
    configured=configure(original)
    destination.mkdir(parents=True,exist_ok=False)
    for path in (work/'rewrite').iterdir():
        if path.is_file() and path.name!='main.patched.bin':
            (destination/path.name).symlink_to(path.resolve())
    (destination/'main.patched.bin').write_bytes(configured)
    receipt={'mode':'fixed-1080p','build_id':profile['build_id'],'nso_sha256':profile['sha256'],
        'verified_rewrite_sha256':hashlib.sha256(original).hexdigest(),
        'configured_sha256':hashlib.sha256(configured).hexdigest(),
        'sites':[{'offset':hex(o),'original':a,'configured':b,'register':r,'purpose':p} for o,a,b,r,p in SITES],
        'selectors':[{'offset':hex(o),'original_word':hex(a),'configured':b,'register':r,'purpose':p} for o,a,b,r,p in SELECTORS],
        'tables':[{'offset':hex(o),'original':v,'configured':[n,*v[1:]],'purpose':p} for o,v,n,p in TABLES],
        'limitations':['Intentional graphics configuration, not semantic equivalence to original resolution.',
                        '1080p scene/output targets require native runtime validation.']}
    (destination/'graphics.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return destination
