"""Validate the complete separate-stage varying ABI; game-derived receipts stay private."""
import hashlib
import importlib.util
from functools import lru_cache
import json
from pathlib import Path
import re


def varyings(source, direction, entry='main0'):
    match = re.search(r'\bstruct\s+'+re.escape(entry+'_'+direction)+r'\s*\{(.*?)\};', source, re.S)
    if not match:
        return {}
    result = {}
    for kind, number in re.findall(r'\b(\w+)\s+\w+\s*\[\[user\(locn(\d+)\)', match[1]):
        loc = int(number)
        if loc in result:
            raise ValueError(f'Duplicate varying location {loc}')
        result[loc] = kind
    if match[1].count('user(locn') != len(result):
        raise ValueError('Unsupported varying declaration')
    return result


def check_coverage(vertices, fragments):
    required = {}
    for key, inputs in fragments.items():
        for loc, kind in inputs.items():
            if loc in required and required[loc] != kind:
                raise ValueError(f'Fragment varying type conflict at {loc}: {key}')
            required[loc] = kind
    if not vertices or not fragments or not required:
        raise ValueError('Incomplete graphics interface inventory')
    for key, outputs in vertices.items():
        missing = [str(loc) for loc, kind in required.items() if outputs.get(loc) != kind]
        if missing:
            raise ValueError(f'{key}: incomplete vertex varying ABI at '+','.join(missing))
    return dict(sorted(required.items()))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


@lru_cache(maxsize=1)
def variant_builder():
    path = Path(__file__).resolve().parents[1]/'third_party/blade2-mobile/dm/gfx/tools/dmsh_fetch.py'
    spec = importlib.util.spec_from_file_location('interface_fetch', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.variant


def build_receipt(directory, chain):
    directory = Path(directory)
    vertices, fragments, files = {}, {}, {}
    for p in sorted(directory.glob('*.json')):
        if p.name.startswith('_'):
            continue
        data = json.loads(p.read_text())
        if data.get('stage') not in ('vs', 'ps'):
            continue
        if data.get('chain') != chain:
            raise ValueError(f'{p.name}: shader chain mismatch')
        msl, lib = p.with_suffix('.metal'), p.with_suffix('.metallib')
        direction = 'out' if data['stage'] == 'vs' else 'in'
        target = vertices if data['stage'] == 'vs' else fragments
        target[p.stem] = varyings(msl.read_text(), direction, data.get('entry', 'main0'))
        for item in (p, msl, lib):
            files[item.name] = digest(item)
        if data['stage'] == 'ps' and p.stem.endswith('_b'):
            variant = directory/(p.stem+'f.metallib')
            if variant.exists():
                # The build intentionally removes temporary variant MSL. Recreate
                # it with the same chain-pinned production function and reflection.
                source, metadata = variant_builder()(msl.read_text(), data['bindings'], om_only_ok=True)
                if not source or metadata != data.get('fetch'):
                    raise ValueError(f'{variant.name}: variant metadata mismatch')
                fragments[variant.stem] = varyings(source, 'in', data.get('entry', 'main0'))
                files[variant.name] = digest(variant)
    required = check_coverage(vertices, fragments)
    files['_b_build.json'] = digest(directory/'_b_build.json')
    files['_varying_scan.json'] = digest(directory/'_varying_scan.json')
    report = {'schema': 1, 'chain': chain, 'vertices': len(vertices), 'fragments': len(fragments),
              'required': required, 'files': files, 'scope': 'All captured graphics libraries, including variants; interface coverage only, not gameplay'}
    tmp = directory/'_interfaces.json.tmp'
    tmp.write_text(json.dumps(report, indent=2)+'\n')
    tmp.replace(directory/'_interfaces.json')
    return report


def verify_receipt(directory, chain):
    directory = Path(directory)
    report = json.loads((directory/'_interfaces.json').read_text())
    if report.get('schema') != 1 or report.get('chain') != chain:
        raise ValueError('Shader interface receipt chain/schema mismatch')
    if not report.get('vertices') or not report.get('fragments') or not report.get('required') or not report.get('files'):
        raise ValueError('Incomplete shader interface receipt')
    for meta in directory.glob('*.json'):
        if meta.name.startswith('_'): continue
        if json.loads(meta.read_text()).get('stage') in ('vs', 'ps') and meta.name not in report['files']:
            raise ValueError(f'Unverified graphics library: {meta.name}')
    if any(p.name not in report['files'] for p in directory.glob('*_bf.metallib')):
        raise ValueError('Unverified fragment variant library')
    for name, expected in report['files'].items():
        if Path(name).name != name or digest(directory/name) != expected:
            raise ValueError(f'Shader interface receipt is stale: {Path(name).name}')
    return report
