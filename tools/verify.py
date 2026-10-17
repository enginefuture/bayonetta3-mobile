#!/usr/bin/env python3
"""Independent LLVM structural and randomized Unicorn rewrite checks."""
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
    p.add_argument('--work',type=Path,default=ROOT/'work')
    p.add_argument('--llvm-bin',type=Path,default=Path('/opt/homebrew/opt/llvm/bin'))
    p.add_argument('--module',action='append',choices=['main','sdk','subsdk0'])
    a = p.parse_args()
    work = a.work.resolve()
    report = dict(modules={}, limitations=['Equivalence harness replaces exclusives on both sides; monitor/concurrency semantics require separate native tests.',
                                         'Rewrite correctness does not prove SDK ABI, shader or gameplay compatibility.'])
    for name in a.module or ['main','subsdk0','sdk']:
        result = {}
        for script,extra in [('structck.py',[]),('equiv.py',['--jobs','4','--seed','1','--mutate','100'])]:
            log = work/'rewrite'/f'{name}.{script}.log'
            print(f'{name}: {script}',flush=True)
            with log.open('w') as f:
                status = subprocess.run([sys.executable,ROOT/'third_party/blade2-mobile/dm/verify'/script,
                                         work/'rewrite',name,work/'game/ExeFS'/name,*extra],stdout=f,stderr=subprocess.STDOUT,
                                        env=dict(os.environ,LLVM_BIN=str(a.llvm_bin),DM_ROOT=str(work))).returncode
            result[script] = status
            if status:
                print(f'Failed: {log}',flush=True)
        for suffix in ('patched.bin','fixups.tsv','gates.tsv','sites.tsv','cuts.tsv'):
            src = work/'rewrite'/f'{name}.{suffix}'
            result[suffix+'_sha256'] = hashlib.sha256(src.read_bytes()).hexdigest()
        report['modules'][name] = result
    report['passed'] = all(m['structck.py']==0 and m['equiv.py']==0 for m in report['modules'].values())
    (work/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
