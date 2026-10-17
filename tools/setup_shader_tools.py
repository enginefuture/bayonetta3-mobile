#!/usr/bin/env python3
"""Build the open-source shader translator locally; never fetch game content."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dotnet', type=Path, help='Path to a .NET 10 SDK dotnet executable')
    a = p.parse_args()
    w = ROOT / 'work'
    runtime = w / 'toolchains/dotnet'
    dotnet = a.dotnet or (runtime / 'dotnet' if (runtime / 'dotnet').is_file() else shutil.which('dotnet'))
    if not dotnet:
        p.exit(1, 'Install the .NET 10 SDK, or supply --dotnet /path/to/dotnet\n')
    dotnet = Path(dotnet).resolve(strict=True)
    version = subprocess.check_output([str(dotnet), '--version'], text=True).strip()
    if not version.startswith('10.'):
        p.exit(1, f'.NET 10 SDK required; selected SDK is {version}\n')
    if runtime.exists() and runtime.resolve() != dotnet.parent:
        p.exit(1, 'work/toolchains/dotnet already selects another runtime; use its dotnet executable\n')
    cross = shutil.which('spirv-cross')
    if not cross:
        p.exit(1, 'Install spirv-cross and make it available on PATH\n')
    runtime.parent.mkdir(parents=True, exist_ok=True)
    if not runtime.exists():
        runtime.symlink_to(dotnet.parent, target_is_directory=True)
    bindir = w / 'toolchains/bin'
    bindir.mkdir(parents=True, exist_ok=True)
    target = bindir / 'spirv-cross'
    if not target.exists():
        shutil.copy2(cross, target)
    project = ROOT / 'third_party/blade2-mobile/dm/gfx/tools/dmsh_xlate/dmsh_xlate.csproj'
    out = w / 'build/gfx/dmsh_xlate'
    env = dict(os.environ, DOTNET_ROOT=str(runtime), DOTNET_CLI_TELEMETRY_OPTOUT='1')
    subprocess.run([str(dotnet), 'publish', str(project), '-c', 'Release',
                    '--artifacts-path', str(w / 'build/dotnet'), '-o', str(out)], env=env, check=True)
    subprocess.run([str(out / 'dmsh_xlate'), '--source-sha'], env=env, check=True)
    print('Shader translator built from vendored source. No game shaders are included.')


if __name__ == '__main__':
    main()
