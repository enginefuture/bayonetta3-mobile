#!/usr/bin/env python3
"""Apply the pinned upstream rewriter only to an exact inventoried game build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, default=ROOT/'work')
    p.add_argument('--exefs', type=Path)
    p.add_argument('--module', choices=['main','sdk','subsdk0'], action='append')
    a = p.parse_args()
    profile = json.loads((ROOT/'config/bayonetta3-1.2.0.json').read_text())
    exefs = a.exefs or a.work/'game/ExeFS'
    out = a.work/'rewrite'
    out.mkdir(parents=True, exist_ok=True)
    env = {k:v for k,v in os.environ.items() if not k.startswith('DM_')}
    for name in a.module or profile['modules']:
        src = exefs/name
        data = src.read_bytes()
        expect = profile['modules'][name]
        if data[0x40:0x60].hex() != expect['build_id'] or hashlib.sha256(data).hexdigest() != expect['sha256']:
            p.exit(1, f'{name}: version/hash mismatch; analyze this build before adding a profile\n')
        print(f'Rewriting {name}', flush=True)
        with (out/f'{name}.log').open('w') as log:
            result = subprocess.run([sys.executable, ROOT/'third_party/blade2-mobile/dm/tools/patch_nso.py',src,out,name],
                                    stdout=log,stderr=subprocess.STDOUT,env=env)
        if result.returncode:
            p.exit(result.returncode, f'{name}: rewriter stopped; see {out/name}.log\n')
    print('Rewrite finished; structural/equivalence verification still required.')


if __name__ == '__main__':
    main()
