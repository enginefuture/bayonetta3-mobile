#!/usr/bin/env python3
"""Prepare local Bayonetta 3 dumps. No downloads, uploads, or source-dump changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TITLE = '01004a4010fea000'


def members(path):
    """Bounded PFS0 directory parser; reject traversal and overlapping extents."""
    total = path.stat().st_size
    with path.open('rb') as f:
        header = f.read(16)
        if len(header) != 16:
            raise ValueError('Truncated PFS0 header')
        magic, count, size, _ = struct.unpack('<4sIII', header)
        if magic != b'PFS0' or count * 24 + size > 16 * 1024 * 1024:
            raise ValueError('Invalid/oversized PFS0 header')
        table = f.read(count * 24)
        strings = f.read(size)
        if len(table) != count*24 or len(strings) != size:
            raise ValueError('Truncated PFS0 directory')
        start = 16 + count * 24 + size
        rows, names = [], set()
        for i in range(count):
            off, length, nameoff, _ = struct.unpack_from('<QQII', table, i * 24)
            end = strings.find(b'\0', nameoff)
            if nameoff >= size or end < 0:
                raise ValueError('Invalid PFS0 filename offset')
            name = strings[nameoff:end].decode('utf-8')
            if not name or name in names or '/' in name or '\\' in name or name in ('.', '..'):
                raise ValueError('Unsafe/duplicate PFS0 member')
            if start + off + length > total:
                raise ValueError('PFS0 extent exceeds input')
            names.add(name)
            rows.append(dict(name=name, offset=start + off, size=length))
        ranges = sorted((r['offset'], r['offset'] + r['size']) for r in rows if r['size'])
        if any(a[1] > b[0] for a, b in zip(ranges, ranges[1:])):
            raise ValueError('Overlapping PFS0 members')
        return rows


def unpack(path, out):
    out.mkdir(mode=0o700)
    with path.open('rb') as f:
        for r in members(path):
            if not r['name'].endswith(('.nca', '.tik')):
                continue
            f.seek(r['offset'])
            remain = r['size']
            with (out / r['name']).open('xb') as dst:
                os.chmod(dst.name, 0o600)
                while remain:
                    chunk = f.read(min(remain, 8 * 1024 * 1024))
                    if not chunk:
                        raise ValueError('Truncated member')
                    dst.write(chunk)
                    remain -= len(chunk)


def execute(cmd, log):
    with log.open('w') as f:
        p = subprocess.run([str(x) for x in cmd], stdout=f, stderr=subprocess.STDOUT)
    if p.returncode:
        raise RuntimeError(f'Tool failed ({p.returncode}); see local log: {log}')
    return log.read_text(errors='replace')


def prepare(args):
    args.work.mkdir(parents=True, exist_ok=True)
    final = args.work / 'game'
    if final.exists():
        raise ValueError(f'Output already exists: {final}')
    stage = args.work / 'game.partial'
    stage.mkdir(mode=0o700, exist_ok=args.resume)
    logs = stage / 'logs'
    logs.mkdir(exist_ok=args.resume)
    # Some local keysets contain malformed extra fields. Filter, never print values.
    with tempfile.TemporaryDirectory(prefix='bayo3-keys-') as td:
        os.chmod(td, 0o700)
        keycopy = Path(td) / 'prod.keys'
        with keycopy.open('x') as f:
            os.chmod(keycopy, 0o600)
            for line in args.keys.read_text().splitlines():
                if re.fullmatch(r'\s*[A-Za-z0-9_]+\s*=\s*(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{64}|[0-9a-fA-F]{512}|[0-9a-fA-F]{1056})\s*', line):
                    f.write(line + '\n')
        packages = [('base', args.base)] + ([('update', args.update)] if args.update else [])
        selected = {}
        for kind, pkg in packages:
            out = stage / kind
            print(f'Unpacking {kind}: {pkg.name}', flush=True)
            if not (args.resume and out.is_dir()):
                unpack(pkg, out)
            else:
                for row in members(pkg):
                    if row['name'].endswith(('.nca', '.tik')):
                        p = out / row['name']
                        if not p.is_file() or p.stat().st_size != row['size']:
                            raise ValueError('Incomplete staged NSP; use a fresh --work directory')
            tickets = list(out.glob('*.tik'))
            opts = [args.nstool, '-k', keycopy]
            if len(tickets) > 1:
                raise ValueError('Multiple tickets: select a single-title NSP')
            if tickets:
                opts += ['--tik', tickets[0]]
            programs = []
            for nca in sorted(out.glob('*.nca')):
                info = execute(opts + [nca], logs / f'{kind}-{nca.stem}.log')
                if re.search(r'Content\s*Type:\s*Program', info):
                    if not re.search(r'(?:Title\s*Id|Program\s*Id|ProgID):\s*(?:0x)?' + TITLE, info, re.I):
                        continue  # Other Program indices (e.g. A001) are not the main application.
                    programs.append(nca)
            if len(programs) != 1:
                raise ValueError(f'Expected one {kind} Program NCA; found {len(programs)}; see {logs}')
            selected[kind] = (programs[0], opts)
        nca, opts = selected.get('update', selected['base'])
        if 'update' in selected:
            opts = opts + ['--basenca', selected['base'][0]]
        print('Extracting ExeFS and merged RomFS', flush=True)
        execute(opts + ['-x', '/0', stage / 'ExeFS', '-x', '/1', stage / 'RomFS', nca], logs / 'extract.log')
    for name in ('main', 'sdk', 'rtld', 'main.npdm'):
        if not (stage / 'ExeFS' / name).is_file():
            raise ValueError(f'Extraction missing {name}')
    if not (stage / 'RomFS').is_dir() or not any((stage / 'RomFS').iterdir()):
        raise ValueError('Extraction missing RomFS')
    identity = dict(title_id=TITLE, base=str(args.base), update=str(args.update) if args.update else None,
                    nca={k:v[0].name for k,v in selected.items()}, source='local NSP and NSTool; not a gameplay claim')
    (stage / 'source.json').write_text(json.dumps(identity, indent=2) + '\n')
    stage.rename(final)
    print(f'Prepared: {final}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--update', type=Path)
    p.add_argument('--keys', type=Path, required=True)
    p.add_argument('--nstool', type=Path, required=True)
    p.add_argument('--work', type=Path, default=ROOT / 'work')
    p.add_argument('--resume', action='store_true', help='Reuse fully unpacked staged NSP members after an interrupted attempt')
    a = p.parse_args()
    for name in ('base', 'keys', 'nstool', 'update'):
        value = getattr(a, name)
        if value:
            setattr(a, name, value.resolve(strict=True))
    a.work = a.work.resolve()
    try:
        prepare(a)
    except (OSError, ValueError, RuntimeError) as e:
        p.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
